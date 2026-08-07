# -*- coding: utf-8 -*-
"""学习与统计:金句收割 + AI 味反例吸收 + 每章文风统计/趋势。
机制来源:webnovel-writer Step 7.3 金句收割(可选);反例吸收自评审报告(review.load_review);
红线清单复用 checks.redlines(内置表 + 本书 文风/审查反例库.md 动态合并)。"""
import os, re
from typing import Dict, List
from storyrepo import checks, state as st
from storyrepo import review as rv

QUOTE_DIR = os.path.join("文风", "金句库")
MAX_QUOTE_LEN = 25
MAX_PER_CHAPTER = 5
QUOTE_ENDS = ("。", "！", "？")
_SKIP_STARTS = ("#", "*", "-", ">")

COUNTEREXAMPLES_FILE = os.path.join("文风", "审查反例库.md")
MAX_COUNTEREXAMPLES = 200
MAX_EVIDENCE_LEN = 20
_ABSORB_SEVERITIES = ("critical", "high")
_SENT_END = re.compile(r"[。！？!?]")


def _chapter_path(root: str, ch: int):
    """返回第 ch 章正文路径;缺章返回 None。"""
    for f in st.chapter_files(root):
        if st.chapter_num(f) == ch:
            return os.path.join(root, "定稿", "正文", f)
    return None


def _counterexample_lines(root: str) -> List[str]:
    """读 文风/审查反例库.md:非空且不以 # 开头的行即一条反例(最旧在前,最新在后)。"""
    p = os.path.join(root, COUNTEREXAMPLES_FILE)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as fh:
        return [ln.strip() for ln in fh.read().splitlines() if ln.strip() and not ln.strip().startswith("#")]


def _paragraphs(text: str) -> List[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _quote_candidates(text: str) -> List[str]:
    out = []
    for p in _paragraphs(text):
        if len(p) > MAX_QUOTE_LEN or p.startswith(_SKIP_STARTS):
            continue
        if not p.endswith(QUOTE_ENDS) or "他说" in p or "她道" in p:
            continue
        out.append(p)
    return out


def absorb_review(root: str, ch: int) -> int:
    """吸收第 ch 章评审反例:severity∈{critical,high} 且 category=ai_flavor 的 evidence 短句(≤20 字),
    与既有反例去重后追加 文风/审查反例库.md(上限 200 条,超限裁最旧)。返回新增条数。"""
    issues, errors = rv.load_review(rv.review_path(root, ch))
    if errors:
        raise ValueError("评审报告损坏,无法吸收: %s" % "; ".join(errors))
    existing = _counterexample_lines(root)
    seen = set(existing)
    new = []
    for i in issues:
        if i.severity not in _ABSORB_SEVERITIES or i.category != "ai_flavor":
            continue
        ev = (i.evidence or "").strip()
        if ev and "\n" not in ev and len(ev) <= MAX_EVIDENCE_LEN and ev not in seen:
            seen.add(ev)
            new.append(ev)
    if not new:
        return 0
    p = os.path.join(root, COUNTEREXAMPLES_FILE)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    headers = []
    if os.path.exists(p):
        with open(p, encoding="utf-8") as fh:
            headers = [ln for ln in fh.read().splitlines() if ln.strip().startswith("#")]
    entries = existing + new
    if len(entries) > MAX_COUNTEREXAMPLES:
        entries = entries[-MAX_COUNTEREXAMPLES:]
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("\n".join(headers or ["# 审查反例库(AI 味反例,机检动态合并)"]) + "\n\n")
        fh.write("\n".join(entries) + "\n")
    return len(new)


def harvest_quotes(root: str, ch: int) -> int:
    """收割金句到 文风/金句库/{ch}.md:独立成段短句(≤25 字、句末标点、无 他说/她道),
    每章 ≤5 条,与既有文件去重;返回新增条数。"""
    p = None
    for f in st.chapter_files(root):
        if st.chapter_num(f) == ch:
            p = os.path.join(root, "定稿", "正文", f)
            break
    if p is None:
        raise FileNotFoundError("缺第%d章正文: %s" % (ch, os.path.join(root, "定稿", "正文")))
    cands = _quote_candidates(st.body(p))[:MAX_PER_CHAPTER]
    d = os.path.join(root, QUOTE_DIR)
    os.makedirs(d, exist_ok=True)
    target = os.path.join(d, "%03d.md" % ch)
    existing = set()
    for f in os.listdir(d):
        if not f.endswith(".md"):
            continue
        with open(os.path.join(d, f), encoding="utf-8") as fh:
            for line in fh.read().splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    existing.add(line)
    new = [q for q in cands if q not in existing]
    if new:
        content = ""
        if os.path.exists(target):
            with open(target, encoding="utf-8") as fh:
                content = fh.read().rstrip()
        with open(target, "w", encoding="utf-8") as fh:
            if content:
                fh.write(content + "\n")
            else:
                fh.write("# 第%d章 金句\n\n" % ch)
            fh.write("\n".join(new) + "\n")
    return len(new)


def style_stats(root: str) -> dict:
    """每章统计 {章号: {"hanzi", "paragraphs", "dialogue_ratio", "redline_hits"}}。
    对话占比 = 含 “” 或 「」 的段落数 / 总段数(0-1);红线命中按 checks.redlines(root)(内置表 + 本书反例库)。"""
    out = {}
    for f in st.chapter_files(root):
        n = st.chapter_num(f)
        text = st.body(os.path.join(root, "定稿", "正文", f))
        paras = _paragraphs(text)
        total = len(paras)
        dial = sum(1 for p in paras if any(c in p for c in "“”「」"))
        hits = sum(len(re.findall(pat, text)) for pat, _ in checks.redlines(root))
        out[n] = {
            "hanzi": st.hanzi(text),
            "paragraphs": total,
            "dialogue_ratio": (dial / total) if total else 0.0,
            "redline_hits": hits,
        }
    return out


def _avg_sentence_len(text: str) -> float:
    """平均句长 = 汉字数 / 句数(。！？!? 切分);无句返回 0。"""
    sents = [s for s in _SENT_END.split(text) if s.strip()]
    if not sents:
        return 0.0
    return round(st.hanzi(text) / len(sents), 1)


def trend(root: str, n: int = 10) -> List[Dict]:
    """近 n 章文风趋势(按章号升序):每章 {chapter, dialogue_ratio, redline_hits, avg_sentence_len, words}。
    对话占比/红线命中/字数(汉字数)复用 style_stats;平均句长 = 汉字数/句数。"""
    stats = style_stats(root)
    out = []
    for ch in sorted(stats)[-n:]:
        p = _chapter_path(root, ch)
        s = stats[ch]
        out.append({
            "chapter": ch,
            "dialogue_ratio": s["dialogue_ratio"],
            "redline_hits": s["redline_hits"],
            "avg_sentence_len": _avg_sentence_len(st.body(p)) if p else 0.0,
            "words": s["hanzi"],
        })
    return out
