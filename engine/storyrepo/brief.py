# -*- coding: utf-8 -*-
"""模块 3:五段式章节写作任务书(brief.py)。
来源:context-agent 输出格式。build_brief 组装五段任务书:
①开篇委托 ②这章的故事 ③这章的人物 ④怎么写更顺 ⑤收在哪里。
无 contract/context 时内部调用 build_contract + assemble_context。
规则:纯标准库、UTF-8、输出中文、只读不写;缺文件容错。"""
import os
import re
from typing import Dict, List, Optional, Tuple

from storyrepo import config
from storyrepo import state as st
from storyrepo.contract import build_contract, load_outline
from storyrepo.context import assemble_context

STYLE_REL = os.path.join("文风", "风格宪法.md")
STYLE_LIMIT = 200
PREV_ENDING_LIMIT = 200
DISTILL_KEYS = ("状态", "驱动", "作用", "说话")


def _chapter_title(root: str, state: Dict, ch: int) -> str:
    row = next((r for r in load_outline(root) if r["ch"] == ch), None)
    if row and row.get("title"):
        return row["title"]
    rec = state.get("chapters", {}).get(str(ch), {}) or {}
    if rec.get("title"):
        return rec["title"]
    return "第%d章" % ch


def _style_head(root: str) -> str:
    p = os.path.join(root, STYLE_REL)
    if not os.path.exists(p):
        return "无风格宪法文件"
    with open(p, encoding="utf-8") as f:
        t = f.read()
    return t[:STYLE_LIMIT]


def _split_entry(entry: str) -> Tuple[str, str]:
    """解析 "【名】内容" 实体卡条目。"""
    m = re.match(r"^【(.+?)】", entry)
    if m:
        return m.group(1), entry[m.end():]
    return entry, ""


def _distill(name: str, excerpt: str) -> str:
    """从角色卡首 400 字提炼状态/驱动/作用/说话倾向;无关键词行则给原文。"""
    lines = [l.strip() for l in excerpt.splitlines() if any(k in l for k in DISTILL_KEYS)]
    if lines:
        return "%s: %s" % (name, "；".join(lines[:6]))
    return "%s: %s" % (name, excerpt[:400])


def _section(lines: List[str], title: str, items: List[str]) -> None:
    lines.append("## %s" % title)
    for it in items:
        lines.append(it)
    lines.append("")


def build_brief(root: str, state: Dict, ch: int,
                contract: Optional[Dict] = None, context: Optional[Dict] = None) -> str:
    """五段任务书。contract/context 可显式传入(便于流水线复用),缺省内部装配。"""
    c = contract if contract is not None else build_contract(root, state, ch)
    ctx = context if context is not None else assemble_context(root, state, ch)

    cfg = config.load_config(root)
    book = cfg.get("name", "未命名")
    goal = c.get("goal") or "(无明确目标)"
    title = _chapter_title(root, state, ch)
    hard: List[str] = c.get("hard_constraints") or []
    forbidden: List[str] = c.get("forbidden") or []
    ending = c.get("ending_requirement") or ""
    chain = ctx.get("summary_chain") or ""
    cards: List[str] = ctx.get("entity_cards") or []
    endings: List[str] = ctx.get("recent_endings") or []
    prev_ending = endings[-1] if endings else ""

    lines: List[str] = []
    lines.append("# 第%d章 写作任务书(%s)" % (ch, book))
    lines.append("")

    _section(lines, "一、开篇委托", [
        "- 书名:%s" % book,
        "- 章号:%d" % ch,
        "- 标题:%s" % title,
        "- 一句话目标:%s" % goal,
    ])

    items2 = [
        "- 前文摘要:%s" % (chain or "暂无前文摘要"),
        "- 目标:%s" % goal,
        "- 节点(细纲·要发生什么):%s" % goal,
        "- 必覆盖:%s" % ("、".join(hard) if hard else "无"),
        "- 禁区:%s" % ("、".join(forbidden) if forbidden else "无"),
    ]
    if cards:
        items2.append("- 检索线索(实体卡):")
        items2 += ["  - %s" % card for card in cards]
    _section(lines, "二、这章的故事", items2)

    if cards:
        items3 = ["- %s" % _distill(*_split_entry(card)) for card in cards]
    else:
        items3 = ["- 无(未登记角色)"]
    _section(lines, "三、这章的人物", items3)

    _section(lines, "四、怎么写更顺", [
        "- 风格宪法(前 %d 字):%s" % (STYLE_LIMIT, _style_head(root)),
        "- 结尾埋伏笔要求:%s" % (ending or "无明确要求"),
    ])

    items5 = ["- 结尾要求:%s" % (ending or "无明确要求")]
    if prev_ending:
        items5.append("- 上章结尾复述(供衔接):%s" % prev_ending[:PREV_ENDING_LIMIT])
    else:
        items5.append("- 上章结尾复述:尚无上章(本书开篇)")
    _section(lines, "五、收在哪里", items5)

    return "\n".join(lines)
