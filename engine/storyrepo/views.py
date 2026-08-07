# -*- coding: utf-8 -*-
"""派生视图:续写状态卡(7 栏)与全部追踪视图的唯一定点重建。
机制来源:oh-story tracking 双视图(作者真相/读者已知)与续写状态卡。
只写 追踪/ 下的派生文件;状态本体写入只经 state.py。
幂等:重复调用不炸;state 缺字段一律容错。"""
import os
import re

from storyrepo import config
from storyrepo import state as st

CARD_TITLE = "# 续写状态卡(7 栏)"
NEXT_PLACEHOLDER = "（无未勾选细纲行,续写依总纲自由发挥）"
STYLE_ANCHOR = (
    "一、拒绝抽象升华与万能比喻,写具体动作与可感细节。\n"
    "二、每章必有推进:情节、人物或伏笔至少一项向前。\n"
    "三、章末留钩:悬念、转折或新伏笔,让读者想翻下一页。"
)
CHAPTER_LOG_TARGET = 1536   # 逐章记录目标大小(字节)
CHAPTER_LOG_MAX = 3072      # 逐章记录截断上限(字节)


def _cut(text, limit):
    """按字节截断(UTF-8 安全),超限截断末尾。"""
    b = text.encode("utf-8")
    if len(b) <= limit:
        return text
    return b[:limit].decode("utf-8", "ignore")


def _write(root, folder, name, content):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
        f.write(content)


def _num(v):
    return "" if v is None else v


def _next_contract_line(root):
    """大纲/细纲蓝图.md 第一个未勾选行([ ] 未勾选或普通行),无则 None。"""
    p = os.path.join(root, "大纲", "细纲蓝图.md")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        for line in f:
            t = line.strip()
            if not t or t.startswith("#"):
                continue
            m = re.match(r"^[-*]?\s*\[([ xX])\]\s*(.*)$", t)
            if m:
                if m.group(1).lower() == "x":
                    continue                      # 已勾选,跳过
                return m.group(2).strip()         # 未勾选
            if "[" not in t:
                return t                          # 无勾选标记的普通行视为未勾选
    return None


def _last_endings(root, n=3, limit=150):
    """最近 n 章正文末段(跳过 —— 横幅段),各 ≤limit 字。"""
    files = st.chapter_files(root)
    nums = sorted(st.chapter_num(f) for f in files)[-n:]
    out = []
    for num in nums:
        f = [x for x in files if st.chapter_num(x) == num][0]
        body = st.body(os.path.join(root, "定稿", "正文", f))
        paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        para = ""
        for p in reversed(paras):
            if p.startswith("——"):
                continue
            para = p
            break
        out.append((num, para[:limit]))
    return out


def card7(root, state) -> str:
    """续写状态卡 7 栏(固定顺序/固定标题),≤12KB,超限截断末尾。"""
    try:
        cfg = config.load_config(root)
    except FileNotFoundError:
        cfg = config.DEFAULTS
    latest = st.latest_chapter(root)
    planned = int(cfg.get("total_chapters", 330))
    actives = st.active_promises(state)
    gaps = st.unrevealed_gaps(state)
    contract = _next_contract_line(root)
    entities = list(state.get("entity_states", {}).items())[:6]
    endings = _last_endings(root)

    L = [CARD_TITLE, ""]
    # 1 当前进度
    L += ["## 1. 当前进度",
          "最新章: %d / 计划: %d | 活跃承诺: %d | 未曝光信息差: %d"
          % (latest, planned, len(actives), len(gaps)), ""]
    # 2 下一章合同
    L += ["## 2. 下一章合同",
          (contract[:120] if contract else NEXT_PLACEHOLDER), ""]
    # 3 活跃伏笔
    L.append("## 3. 活跃伏笔")
    if actives:
        for pid, v in actives[:10]:
            note = str(v.get("note", "")).strip()
            L.append("- %s %s" % (pid, note) if note else "- %s" % pid)
    else:
        L.append("（无）")
    L.append("")
    # 4 核心角色状态
    L.append("## 4. 核心角色状态")
    if entities:
        for name, v in entities:
            first = v.get("first_ch")
            if first is None:
                L.append("- %s: 首现章未知" % name)
                continue
            where = str(v.get("where", "")).strip()
            if where:
                L.append("- %s: 首现第%d章 %s" % (name, first, where))
            else:
                L.append("- %s: 首现第%d章" % (name, first))
    else:
        L.append("（无）")
    L.append("")
    # 5 最近章节结尾
    L.append("## 5. 最近章节结尾")
    if endings:
        for num, para in endings:
            L.append("- 第%d章: %s" % (num, para))
    else:
        L.append("（无正文,待首章落笔）")
    L.append("")
    # 6 未曝光信息差
    L.append("## 6. 未曝光信息差")
    if gaps:
        for gid, v in gaps[:8]:
            note = str(v.get("note", "")).strip()
            L.append("- %s %s" % (gid, note) if note else "- %s" % gid)
    else:
        L.append("（无）")
    L.append("")
    # 7 风格锚点
    L += ["## 7. 风格锚点", STYLE_ANCHOR, ""]
    return _cut("\n".join(L), st.MAX_CARD_BYTES)


def card_size_ok(root) -> bool:
    """上下文卡是否 ≤12KB;缺文件视为不通过。"""
    p = os.path.join(st.tracking_path(root), "上下文.md")
    return os.path.exists(p) and os.path.getsize(p) <= st.MAX_CARD_BYTES


def write_views(root, state) -> None:
    """重建全部派生视图(幂等;state 缺字段容错)。"""
    tk = st.tracking_path(root)
    _write(root, tk, "上下文.md", card7(root, state))
    _write(root, tk, "伏笔.md", _vault_table(state))
    _write(root, tk, "作者真相.md", _author_truth(state))
    _write(root, tk, "读者已知.md", _reader_known(state))
    _write(root, tk, "时间线.md", _timeline_table(state))
    _write_entity_files(root, tk, state)
    _write_chapter_logs(root, tk, state)


# ── 追踪/伏笔.md ──
def _vault_table(state):
    lines = ["# 伏笔与信息差台账", "",
             "## 伏笔",
             "| ID | 状态 | 埋设章 | 最近推进 | 完成章 | 备注 |",
             "| --- | --- | --- | --- | --- | --- |"]
    for pid, v in sorted(state.get("promises", {}).items()):
        lines.append("| %s | %s | %s | %s | %s | %s |" % (
            pid, v.get("status", "open"), _num(v.get("open_ch")), _num(v.get("adv_ch")),
            _num(v.get("done_ch")), str(v.get("note", "")).replace("|", "\\|")))
    lines += ["", "## 信息差",
              "| ID | 状态 | 埋设章 | 最近推进 | 完成章 | 备注 |",
              "| --- | --- | --- | --- | --- | --- |"]
    for gid, v in sorted(state.get("info_gaps", {}).items()):
        status = "已曝光" if v.get("revealed") else "未曝光"
        lines.append("| %s | %s | %s | %s | %s | %s |" % (
            gid, status, _num(v.get("plant_ch")), "",
            _num(v.get("reveal_ch")), str(v.get("note", "")).replace("|", "\\|")))
    return "\n".join(lines)


# ── 追踪/作者真相.md(作者才看的真相) ──
def _author_truth(state):
    lines = ["# 作者真相(仅作者可见)", "", "## 时间线(全量)"]
    tl = state.get("timeline", [])
    if tl:
        for ev in tl:
            lines.append("- %s. %s" % (ev.get("ch", "?"), ev.get("event", "")))
    else:
        lines.append("（空）")
    lines += ["", "## 未曝光信息差(作者才知,读者未见)"]
    gaps = st.unrevealed_gaps(state)
    if gaps:
        for gid, v in gaps:
            note = str(v.get("note", "")).strip()
            lines.append("- %s: %s" % (gid, note) if note else "- %s" % gid)
    else:
        lines.append("（无）")
    return "\n".join(lines)


# ── 追踪/读者已知.md(读者视角) ──
def _reader_known(state):
    lines = ["# 读者已知(读者视角)", "", "## 时间线(读者已见)"]
    tl = [ev for ev in state.get("timeline", [])
          if ev.get("kind", "fact") in ("fact", "reveal")]
    if tl:
        for ev in tl:
            lines.append("- %s. %s" % (ev.get("ch", "?"), ev.get("event", "")))
    else:
        lines.append("（空）")
    lines += ["", "## 已曝光信息差"]
    revealed = [(gid, v) for gid, v in state.get("info_gaps", {}).items()
                if v.get("revealed")]
    if revealed:
        for gid, v in revealed:
            note = str(v.get("note", "")).strip()
            lines.append("- %s: %s" % (gid, note) if note else "- %s" % gid)
    else:
        lines.append("（无）")
    return "\n".join(lines)


# ── 追踪/时间线.md(append-only 观感) ──
def _timeline_table(state):
    lines = ["# 时间线(append-only,只增不改)", "",
             "| 章 | 类型 | 事件 |", "| --- | --- | --- |"]
    tl = state.get("timeline", [])
    if not tl:
        lines.append("|  |  | （空） |")
    for ev in tl:
        lines.append("| %s | %s | %s |" % (
            ev.get("ch", ""), ev.get("kind", "fact"),
            str(ev.get("event", "")).replace("|", "\\|")))
    return "\n".join(lines)


# ── 追踪/角色状态/{名}.md ──
def _write_entity_files(root, tk, state):
    # L1:先清理陈旧文件(实体被移除时不留残卡),再写当前
    edir = os.path.join(tk, "角色状态")
    if os.path.isdir(edir):
        for f in os.listdir(edir):
            if f.endswith(".md"):
                os.remove(os.path.join(edir, f))
    for name, v in state.get("entity_states", {}).items():
        if not str(name).strip():
            continue
        safe = str(name).replace("/", "_").replace("\\", "_").replace(":", "_").replace("*", "_").replace("?", "_").replace('"', "_").replace("<", "_").replace(">", "_").replace("|", "_")
        first = v.get("first_ch")
        lines = ["# 角色状态:%s" % name, "",
                 "- 首现章: %s" % (first if first is not None else ""),
                 "- 位置: %s" % str(v.get("where", "")).strip(),
                 "- 状态: %s" % str(v.get("state", "")).strip()]
        _write(root, os.path.join(tk, "角色状态"), "%s.md" % safe, "\n".join(lines))


# ── 追踪/逐章记录/ch{NNN}.md ──
def _write_chapter_logs(root, tk, state):
    # L1:先清理陈旧日志,再写当前
    ldir = os.path.join(tk, "逐章记录")
    if os.path.isdir(ldir):
        for f in os.listdir(ldir):
            if f.endswith(".md"):
                os.remove(os.path.join(ldir, f))
    for k in sorted(int(x) for x in state.get("chapters", {}) if str(x).isdigit()):
        content = _chapter_log(root, state, k)
        _write(root, os.path.join(tk, "逐章记录"), "ch%03d.md" % k,
               _cut(content, CHAPTER_LOG_MAX))


def _chapter_constraints(root, ch):
    for f in st.chapter_files(root):
        if st.chapter_num(f) == ch:
            fm = st.frontmatter(os.path.join(root, "定稿", "正文", f))
            parts = []
            must = st.fm_list(fm, "must_cover")
            forb = st.fm_list(fm, "forbidden")
            if must:
                parts.append("必覆盖:" + ",".join(must))
            if forb:
                parts.append("禁区:" + ",".join(forb))
            return "; ".join(parts) if parts else "无"
    return "无"


def _chapter_log(root, state, ch):
    """一章的六类字段记录,从 state 推导(约束回读 front matter)。"""
    rec = state.get("chapters", {}).get(str(ch), {})
    title = str(rec.get("title", "")).strip()
    status = str(rec.get("status", "")).strip()
    words = str(rec.get("words", "")).strip()
    # 结果
    events = [str(ev.get("event", "")) for ev in state.get("timeline", [])
              if ev.get("ch") == ch]
    result = "; ".join(events) if events else "(无摘要)"
    meta = []
    if status:
        meta.append("状态:" + status)
    if words:
        meta.append("字数:" + words)
    if meta:
        result += "（" + ", ".join(meta) + "）"
    # 角色变化(本章首现的实体,附当前位置/状态)
    ent = []
    for name, v in state.get("entity_states", {}).items():
        if v.get("first_ch") == ch:
            base = "首现:%s" % name
            extra = []
            w = str(v.get("where", "")).strip()
            stt = str(v.get("state", "")).strip()
            if w:
                extra.append("位置:" + w)
            if stt:
                extra.append("状态:" + stt)
            if extra:
                base += "(" + ",".join(extra) + ")"
            ent.append(base)
    # 伏笔变化
    promises = state.get("promises", {})
    gaps = state.get("info_gaps", {})
    p_new = sorted(pid for pid, v in promises.items() if v.get("open_ch") == ch)
    p_adv = sorted(pid for pid, v in promises.items() if v.get("adv_ch") == ch)
    p_done = sorted(pid for pid, v in promises.items() if v.get("done_ch") == ch)
    g_new = sorted(gid for gid, v in gaps.items() if v.get("plant_ch") == ch)
    g_done = sorted(gid for gid, v in gaps.items() if v.get("reveal_ch") == ch)
    pv = []
    if p_new:
        pv.append("新埋:" + ",".join(p_new))
    if p_adv:
        pv.append("推进:" + ",".join(p_adv))
    if p_done:
        pv.append("回收:" + ",".join(p_done))
    if g_new:
        pv.append("埋设:" + ",".join(g_new))
    if g_done:
        pv.append("揭示:" + ",".join(g_done))
    # 时间与揭示
    ts = []
    if g_done:
        ts.append("揭示信息差:" + ",".join(g_done))
    for ev in state.get("timeline", []):
        if ev.get("ch") == ch and ev.get("kind") in ("reveal", "private"):
            ts.append("事件:" + str(ev.get("event", "")))
    # 下一章承诺(本章新埋/推进/埋设的伏笔与信息差,下一章须承接)
    nxt = sorted(set(p_new) | set(p_adv) | set(g_new))

    head = "# 逐章记录:第%d章" % ch
    if title:
        head += "《%s》" % title
    return "\n".join([
        head, "",
        "- 结果: %s" % result,
        "- 角色变化: %s" % ("; ".join(ent) if ent else "无"),
        "- 伏笔变化: %s" % ("; ".join(pv) if pv else "无"),
        "- 时间与揭示: %s" % ("; ".join(ts) if ts else "无"),
        "- 约束: %s" % _chapter_constraints(root, ch),
        "- 下一章承诺: %s" % (", ".join(nxt) if nxt else "无"),
    ])
