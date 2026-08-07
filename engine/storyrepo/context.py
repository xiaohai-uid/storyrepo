# -*- coding: utf-8 -*-
"""模块 3:写作上下文装配(context.py)。
assemble_context 汇总四路上下文(recent_endings / summary_chain / entity_cards /
next_chapter_injection)+ budget_kb;budget_check 判四路合计 ≤ 8KB。
机制来源:context-agent / AI_NovelGenerator(context 注入)。
规则:纯标准库、UTF-8、只读不写;缺文件容错(跳过/占位)。
预算口径:按 len(s.encode("utf-8")) 估算字节(中文 1 字 ≈ 3 字节),
四路合计 > 8KB 视为超预算(各路上限 800/1000/400/150 字是软上限,预算为最终硬闸)。"""
import os
import re
from typing import Dict, List

from storyrepo import state as st
from storyrepo.contract import load_outline, split_list

BANNER_RE = re.compile(r"^[—–-]{2,}")
BUDGET_BYTES = 8 * 1024

ENDINGS_COUNT = 3       # 最近 3 章
END_LIMIT = 800         # 末段 ≤800 字
SUMMARY_COUNT = 5       # 最近 5 篇章摘要
SUMMARY_LIMIT = 1000    # 拼接 ≤1000 字
CARD_COUNT = 3          # 实体卡 ≤3 张
CARD_LIMIT = 400        # 每张前 400 字
INJECT_LIMIT = 150      # 下章注入 ≤150 字

CARD_DIR = os.path.join("定稿", "设定", "角色")
SUMMARY_DIR = os.path.join("定稿", "记忆", "章摘要")
BODY_DIR = os.path.join("定稿", "正文")


def _paragraphs(text: str) -> List[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _last_ending(text: str, limit: int = END_LIMIT) -> str:
    """正文末段(去"——"横幅),≤limit 字。"""
    paras = _paragraphs(text)
    while paras and BANNER_RE.match(paras[-1]):
        paras.pop()
    if not paras:
        return ""
    last = paras[-1].strip("—–- \t")
    return last[:limit]


def _chapter_body(root: str, n: int) -> str:
    for f in st.chapter_files(root):
        if st.chapter_num(f) == n:
            return st.body(os.path.join(root, BODY_DIR, f))
    return ""


def _recent_endings(root: str, ch: int) -> List[str]:
    out = []
    for n in range(max(1, ch - ENDINGS_COUNT), ch):
        e = _last_ending(_chapter_body(root, n))
        if e:
            out.append(e)
    return out


def _summary_chain(root: str, ch: int) -> str:
    parts = []
    for n in range(max(1, ch - SUMMARY_COUNT), ch):
        p = os.path.join(root, SUMMARY_DIR, "%03d.md" % n)
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as f:
            t = f.read()
        body = "\n".join(l for l in t.splitlines() if not l.strip().startswith("#"))
        if body.strip():
            parts.append(body.strip())
    return "\n".join(parts)[:SUMMARY_LIMIT]


def _entity_cards(root: str, state: Dict, ch: int) -> List[str]:
    """细纲行"角色"列(若有)或 state.entity_states 前 3,读角色卡前 400 字。"""
    names: List[str] = []
    row = next((r for r in load_outline(root) if r["ch"] == ch), None)
    if row and row.get("roles"):
        names = split_list(row["roles"])[:CARD_COUNT]
    if not names:
        names = list(state.get("entity_states", {}).keys())[:CARD_COUNT]
    cards = []
    for name in names:
        p = os.path.join(root, CARD_DIR, "%s.md" % name)
        if not os.path.exists(p):
            cards.append("【%s】(角色卡缺失:%s)" % (name, p))
            continue
        with open(p, encoding="utf-8") as f:
            t = f.read()
        cards.append("【%s】%s" % (name, t[:CARD_LIMIT]))
    return cards


def _next_injection(root: str, ch: int) -> str:
    """细纲 ch+1 行的 goal+suspense/foreshadow/twist,截 150 字。"""
    row = next((r for r in load_outline(root) if r["ch"] == ch + 1), None)
    if not row:
        return ""
    parts = [str(row.get(k) or "").strip() for k in ("goal", "suspense", "foreshadow", "twist")]
    return "；".join(x for x in parts if x)[:INJECT_LIMIT]


def _total_bytes(ctx: Dict) -> int:
    total = 0
    for s in ctx.get("recent_endings", []) or []:
        total += len(str(s).encode("utf-8"))
    total += len(str(ctx.get("summary_chain", "")).encode("utf-8"))
    for s in ctx.get("entity_cards", []) or []:
        total += len(str(s).encode("utf-8"))
    total += len(str(ctx.get("next_chapter_injection", "")).encode("utf-8"))
    return total


def assemble_context(root: str, state: Dict, ch: int) -> Dict:
    """装配第 ch 章四路上下文。
    {"recent_endings": [str], "summary_chain": str, "entity_cards": [str],
     "next_chapter_injection": str, "budget_kb": float}"""
    endings = _recent_endings(root, ch)
    chain = _summary_chain(root, ch)
    cards = _entity_cards(root, state, ch)
    inject = _next_injection(root, ch)
    ctx = {
        "recent_endings": endings,
        "summary_chain": chain,
        "entity_cards": cards,
        "next_chapter_injection": inject,
        "budget_kb": 0.0,
    }
    ctx["budget_kb"] = round(_total_bytes(ctx) / 1024.0, 2)
    return ctx


def budget_check(ctx: Dict) -> bool:
    """四路合计 ≤ 8KB(UTF-8 字节估算)。"""
    return float(ctx.get("budget_kb", 0)) <= BUDGET_BYTES / 1024.0
