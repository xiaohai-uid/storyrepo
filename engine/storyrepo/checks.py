# -*- coding: utf-8 -*-
"""机检(机器检查):collect_checks 十一项检查 + AI 红线正则表。
机制来源:webnovel-writer review 机检清单 / oh-story 机检(自研轻量实现)。
约定:纯标准库、UTF-8、函数带 root: str;错误 raise FileNotFoundError/ValueError + 中文提示。
collect_checks 始终返回全部 11 项 check(不过滤 stage),由 gates.gate 决定只看哪些。"""
import os
import re
from collections import Counter
from typing import Dict, List, Optional, Tuple

from storyrepo import config, state as st

STAGES = ("prewrite", "precommit", "postcommit")

# ── AI 红线正则表(启发式;章末总结体/预告体/万能比喻/抽象升华) ──
# 含 templates/doctor.py 既有五条;learn/report 复用本表,redlines(root) 动态并入本书反例库
REDLINES = [
    (r"他终于明白", "章末总结体·终于明白"),
    (r"这一夜[^。]*注定", "章末总结体·这一夜注定"),
    (r"无人入眠", "章末总结体·无人入眠"),
    (r"(?:本章|这一章|本章节|这一回).{0,12}(?:讲述|讲了|写到|写了|展现|描写)", "章末总结体"),
    (r"他不知道的是", "预告体"),
    (r"(?:下一章|下一回|且听下回分解|欲知后事|敬请期待|未完待续)", "预告体"),
    (r"像潮水般|如闪电般|仿佛春风", "万能比喻"),
    (r"(?:宛如|犹如|恰如|仿佛)(?:一幅|一场|一首)?(?:画卷|史诗|乐章|诗篇|梦境)", "万能比喻"),
    (r"(?:或许|也许|可能).{0,4}(?:这|那)?就?是(?:人生|命运|生活|成长|一切)", "抽象升华"),
]

_PLACEHOLDER = re.compile(r"TODO|占位|待补|待写|XXX|\{[A-Za-z_]+\}")


COUNTEREXAMPLES_FILE = os.path.join("文风", "审查反例库.md")


def redlines(root: Optional[str] = None) -> List[Tuple[str, str]]:
    """AI 红线正则表:[(pattern, name)]。root 给定时动态并入本书 文风/审查反例库.md 的短语
    (re.escape 转义为字面正则,命名「反例库·<短语>」);反例库缺失时仅内置表。"""
    out = list(REDLINES)
    if root:
        p = os.path.join(root, COUNTEREXAMPLES_FILE)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as fh:
                for ln in fh.read().splitlines():
                    ln = ln.strip()
                    if ln and not ln.startswith("#"):
                        out.append((re.escape(ln), "反例库·%s" % ln))
    return out


# ── 内部工具 ──
def _target_chapters(root: str, chapter) -> List[Tuple[int, str]]:
    """按 chapter_num 排序返回 [(num, 正文路径)];chapter 为 None → 全部。"""
    fs = sorted(st.chapter_files(root), key=st.chapter_num)
    if chapter is None:
        return [(st.chapter_num(f), os.path.join(root, "定稿", "正文", f)) for f in fs]
    n = int(chapter)
    for f in fs:
        if st.chapter_num(f) == n:
            return [(n, os.path.join(root, "定稿", "正文", f))]
    return []


def _per_chapter(root: str, chapter, fn) -> Tuple[bool, str]:
    """逐章跑 fn(num, path) -> (ok, detail);聚合为 (全过, "; " 拼接 detail)。"""
    targets = _target_chapters(root, chapter)
    if not targets:
        if chapter is None:
            return True, "无章节"
        return False, "第%d章 不存在" % int(chapter)
    results = [fn(n, p) for n, p in targets]
    return all(ok for ok, _ in results), "; ".join(d for _, d in results)


def _snippet(text: str, start: int, end: int, pad: int = 6) -> str:
    a, b = max(0, start - pad), min(len(text), end + pad)
    return ("…" if a > 0 else "") + text[a:b] + ("…" if b < len(text) else "")


# ── 11 项检查(每项返回 (ok, detail),与 gate 序号 1..11 对应) ──
def _check_numbering(root: str, chapter, stage: str) -> Tuple[bool, str]:
    """1. 编号连续且唯一:chapter_files 按 chapter_num 排序 == 1..N。"""
    nums = sorted(st.chapter_num(f) for f in st.chapter_files(root))
    if not nums:
        return True, "无章节(空书)"
    expect = list(range(1, len(nums) + 1))
    if nums != expect:
        return False, "编号不连续或重复: 现有 %s,应为 %s" % (nums, expect)
    return True, "编号 1..%d 连续唯一" % len(nums)


def _check_words(root: str, chapter, stage: str) -> Tuple[bool, str]:
    """2. 字数窗口:hanzi(body) in [min_words-400, max_words+200]。"""
    cfg = config.load_config(root)
    lo = max(0, cfg["min_words_per_chapter"] - 400)
    hi = cfg["max_words_per_chapter"] + 200

    def fn(n, p):
        c = st.hanzi(st.body(p))
        if c < lo:
            return False, "第%d章 %d 字,低于下限 %d" % (n, c, lo)
        if c > hi:
            return False, "第%d章 %d 字,超出上限 %d" % (n, c, hi)
        return True, "第%d章 %d 字" % (n, c)

    return _per_chapter(root, chapter, fn)


def _check_placeholder(root: str, chapter, stage: str) -> Tuple[bool, str]:
    """3. 占位符:正文含 TODO|占位|待补|待写|XXX|{标识} → fail。"""
    def fn(n, p):
        m = _PLACEHOLDER.search(st.body(p))
        if m:
            return False, "第%d章 含占位符「%s」" % (n, m.group(0))
        return True, "第%d章 无占位符" % n

    return _per_chapter(root, chapter, fn)


def _check_leaks(root: str, chapter, stage: str) -> Tuple[bool, str]:
    """4. 泄密扫描:未曝光信息差 S-id 出现在正文(仅 st.body,front matter 除外)→ fail。
    只扫描 n >= plant_ch 的章节(埋设章之前的章节不存在泄密,避免时序误报)。"""
    try:
        s = st.load_state(root)
    except (FileNotFoundError, ValueError) as e:
        return False, "缺追踪状态,无法扫描泄密(%s)" % e
    gaps = [(g, v.get("plant_ch", 1) or 1) for g, v in s.get("info_gaps", {}).items() if not v.get("revealed")]
    if not gaps:
        return True, "无未曝光信息差"
    targets = _target_chapters(root, chapter)
    if not targets:
        if chapter is None:
            return True, "无章节"
        return False, "第%d章 不存在" % int(chapter)
    bad = []
    for n, p in targets:
        hit = [g for g, plant in gaps if n >= plant and g in st.body(p)]
        if hit:
            bad.append("第%d章 正文出现未曝光信息差 %s" % (n, "、".join(hit)))
    if bad:
        return False, "; ".join(bad)
    return True, "正文未泄密"


def _check_entities(root: str, chapter, stage: str) -> Tuple[bool, str]:
    """5. 实体登记:entities_new 每项须出现在 定稿/设定/名册.md。"""
    roster = os.path.join(root, "定稿", "设定", "名册.md")

    def fn(n, p):
        ents = st.fm_list(st.frontmatter(p), "entities_new")
        if not ents:
            return True, "第%d章 无新实体" % n
        if not os.path.exists(roster):
            return False, "第%d章 实体 %s 未登记(缺 定稿/设定/名册.md)" % (n, "、".join(ents))
        with open(roster, encoding="utf-8") as f:
            content = f.read()
        missing = [e for e in ents if e not in content]
        if missing:
            return False, "第%d章 实体未登记于名册: %s" % (n, "、".join(missing))
        return True, "第%d章 实体均已登记" % n

    return _per_chapter(root, chapter, fn)


def _check_files(root: str, chapter, stage: str) -> Tuple[bool, str]:
    """6. 每章 front matter 存在 + 定稿/记忆/章摘要/{NNN}.md 存在。"""
    def fn(n, p):
        if not st.frontmatter(p):
            return False, "第%d章 缺 front matter" % n
        sp = os.path.join(root, "定稿", "记忆", "章摘要", "%03d.md" % n)
        if not os.path.exists(sp):
            return False, "第%d章 缺章摘要 %s" % (n, os.path.relpath(sp, root))
        return True, "第%d章 文件齐全" % n

    return _per_chapter(root, chapter, fn)


def _check_redlines(root: str, chapter, stage: str) -> Tuple[bool, str]:
    """7. AI 红线:redlines() 每 pattern 扫 st.body,命中 → fail(注明位置片段)。"""
    def fn(n, p):
        body = st.body(p)
        for pat, name in redlines(root):
            m = re.search(pat, body)
            if m:
                return False, "第%d章 红线「%s」命中: 片段 %s" % (n, name, _snippet(body, m.start(), m.end()))
        return True, "第%d章 无红线命中" % n

    return _per_chapter(root, chapter, fn)


def _in_quotes(text: str, frag: str) -> bool:
    """frag 是否完全位于一对中文引号/直引号内。"""
    for open_, close_ in (('"', '"'), ('“', '”'), ('「', '」')):
        depth = 0
        i = 0
        while i < len(text):
            ch = text[i]
            if ch == open_:
                depth += 1
            elif ch == close_ and depth:
                depth -= 1
            elif depth and text.startswith(frag, i):
                return True
            i += 1
    return False


def _common5(a: str, b: str) -> Optional[str]:
    """两段去空白后是否存在 ≥5 字公共子串;返回任一公共 5 字片段或 None。
    对话回环(角色重复同一短语)是修辞手法:公共子串在两段都位于引号内则不算复读。"""
    if len(a) < 5 or len(b) < 5:
        return None
    if len(a) > len(b):
        a, b = b, a
    grams = {b[i:i + 5] for i in range(len(b) - 4)}
    for i in range(len(a) - 4):
        g = a[i:i + 5]
        if g in grams:
            if _in_quotes(a, g) and _in_quotes(b, g):
                continue
            return g
    return None


def _check_repeat(root: str, chapter, stage: str) -> Tuple[bool, str]:
    """8. 复读检测:相邻两段 ≥5 字公共子串(去空白)→ fail;或同一 4-gram ≥6 次 → fail。"""
    def fn(n, p):
        body = st.body(p)
        paras = ["".join(seg.split()) for seg in body.split("\n\n") if seg.strip()]
        for a, b in zip(paras, paras[1:]):
            g = _common5(a, b)
            if g:
                return False, "第%d章 相邻段落存在重复片段「%s」" % (n, g)
        flat = "".join(paras)
        if len(flat) >= 4:
            cnt = Counter(flat[i:i + 4] for i in range(len(flat) - 3))
            # 过滤句首/句末名句式误报:4-gram 含句读标点(如「。陆沉舟」)是正常句式,不计复读
            PUNC = "。！？；，、”」)}"
            cnt = {g: k for g, k in cnt.items() if g[-1] not in PUNC and g[0] not in PUNC}
            # 过滤对话归属误报:含引号的 4-gram(如「"陆沉舟」)是角色对白属性,不计复读
            cnt = {g: k for g, k in cnt.items() if '"' not in g and '“' not in g and '”' not in g and '「' not in g and '」' not in g}
            if cnt:
                g, k = max(cnt.items(), key=lambda t: t[1])
                if k >= 6:
                    return False, "第%d章 4字片段「%s」出现 %d 次" % (n, g, k)
        return True, "第%d章 无复读" % n

    return _per_chapter(root, chapter, fn)


def _check_contract(root: str, chapter, stage: str) -> Tuple[bool, str]:
    """9. 合同断言:must_cover 词正文须全部包含;forbidden 词正文不得含。"""
    def fn(n, p):
        fm = st.frontmatter(p)
        body = st.body(p)
        miss = [w for w in st.fm_list(fm, "must_cover") if w not in body]
        hit = [w for w in st.fm_list(fm, "forbidden") if w in body]
        bad = []
        if miss:
            bad.append("未覆盖必含词 %s" % "、".join(miss))
        if hit:
            bad.append("命中禁区词 %s" % "、".join(hit))
        if bad:
            return False, "第%d章 %s" % (n, "; ".join(bad))
        return True, "第%d章 合同满足" % n

    return _per_chapter(root, chapter, fn)


def _check_fresh(root: str, chapter, stage: str) -> Tuple[bool, str]:
    """10. 追踪新鲜:state_path mtime ≥ 最新正文 mtime(prewrite 跳过);状态卡 ≤ 12KB。"""
    if stage == "prewrite":
        return True, "跳过(prewrite 不查状态新鲜)"
    sp = st.state_path(root)
    if not os.path.exists(sp):
        return False, "缺追踪状态(%s)" % sp
    fs = st.chapter_files(root)
    if fs:
        body_dir = os.path.join(root, "定稿", "正文")
        # 正在提交的目标章除外(该章的 commit 本身就是刷新动作)
        cand = [f for f in fs if st.chapter_num(f) != (int(chapter) if chapter else -1)]
        if cand:
            latest = max(os.path.getmtime(os.path.join(body_dir, f)) for f in cand)
            if os.path.getmtime(sp) < latest:
                return False, "追踪状态早于最新正文(先重跑 state 合并/保存)"
    card = os.path.join(st.tracking_path(root), "上下文.md")
    if not os.path.exists(card):
        return False, "缺状态卡 %s" % os.path.relpath(card, root)
    size = os.path.getsize(card)
    if size > st.MAX_CARD_BYTES:
        return False, "状态卡 %s %d 字节,超过上限 %d" % (os.path.relpath(card, root), size, st.MAX_CARD_BYTES)
    # L4:状态卡必须不早于状态文件(commit 在 save 与 views 之间崩溃会留下“状态新、卡旧”中间态)
    if os.path.getmtime(card) < os.path.getmtime(sp):
        return False, "状态卡早于状态文件(派生视图未重建,重跑 commit 或 views 重建)"
    return True, "追踪新鲜,状态卡 %d 字节" % size


def _check_summary(root: str, chapter, stage: str) -> Tuple[bool, str]:
    """11. 占位符之外:章节 front matter summary 非空。"""
    def fn(n, p):
        fm = st.frontmatter(p)
        s = str(fm.get("summary", "") or "").strip()
        if not s:
            return False, "第%d章 summary 为空" % n
        return True, "第%d章 summary 非空" % n

    return _per_chapter(root, chapter, fn)


# 序号即 gate 的检查项编号(1..11),顺序固定
_CHECKS: List[Tuple[str, object]] = [
    ("编号连续且唯一", _check_numbering),
    ("字数窗口", _check_words),
    ("占位符", _check_placeholder),
    ("泄密扫描", _check_leaks),
    ("实体登记", _check_entities),
    ("章文件齐全", _check_files),
    ("AI红线", _check_redlines),
    ("复读检测", _check_repeat),
    ("合同断言", _check_contract),
    ("追踪新鲜", _check_fresh),
    ("摘要非空", _check_summary),
]


def collect_checks(root: str, stage: str = "precommit", chapter=None) -> List[Dict]:
    """返回全部 11 项 check(不按 stage 过滤,由 gates 决定只看哪些)。

    每项: {"ok": bool, "name": str, "detail": str}。
    stage ∈ prewrite|precommit|postcommit;chapter 为 None → 逐章全查。
    仅第 10 项(追踪新鲜)在 prewrite 跳过。"""
    if stage not in STAGES:
        raise ValueError("stage 非法: %s" % stage)
    if chapter is not None:
        try:
            chapter = int(chapter)
        except (TypeError, ValueError):
            raise ValueError("chapter 非法: %r" % (chapter,))
    out = []
    for name, fn in _CHECKS:
        ok, detail = fn(root, chapter, stage)
        out.append({"ok": ok, "name": name, "detail": detail})
    return out
