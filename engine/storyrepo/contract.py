# -*- coding: utf-8 -*-
"""模块 3:章合同构建(contract.py)。
从 大纲/细纲蓝图.md 提取第 ch 章的写作合同:
{"goal", "hard_constraints", "forbidden", "foreshadow_todo", "ending_requirement", "sources"}。
机制来源:webnovel-writer chapter-plan / oh-story(细纲驱动写作)。
规则:纯标准库、UTF-8、只读不写;无细纲文件不抛错(goal 降级占位)。

细纲蓝图.md 行格式(两种,均以 | 分隔,第 1 列 == ch):
1) Markdown 表格:首行表头须含 "要发生什么"(或首列为 ch/章/章号);
   表头列名按子串识别:ch / 标题 / 要发生什么 / 硬约束 / 禁区 / 角色 /
   suspense(悬念) / foreshadow(伏笔) / twist(反转)。
2) 无表头管道行(简易,列序同表头): ch|标题|要发生什么|硬约束|禁区|角色|suspense|foreshadow|twist
"""
import os
import re
from typing import Dict, List, Optional

from storyrepo import state as st

OUTLINE_REL = os.path.join("大纲", "细纲蓝图.md")
SUMMARY_REL = os.path.join("大纲", "总纲.md")

# 简易行(无表头)的列序(同表头列序,从索引 1 起)
_POSITIONAL = ("title", "goal", "hard", "forbidden", "roles", "suspense", "foreshadow", "twist")
_HEADER_HINTS = ("要发生什么", "ch", "章", "章号", "章节")


def _to_int(s) -> Optional[int]:
    m = re.search(r"\d+", str(s))
    return int(m.group()) if m else None


def split_list(s) -> List[str]:
    """逗号/顿号/分号分隔的列表。"""
    return [x.strip() for x in re.split(r"[,，、;；]", str(s)) if x.strip()]


def _norm_key(header: str) -> Optional[str]:
    """表头列名 → 规范键。"""
    h = header.strip().lower()
    if h in ("ch", "章", "章号", "章节", "章序"):
        return "ch"
    if "标题" in h or "章名" in h or "title" in h:
        return "title"
    if "要发生什么" in h or "goal" in h or h == "发生":
        return "goal"
    if "硬约束" in h or "约束" in h or "hard" in h:
        return "hard"
    if "禁区" in h or "forbidden" in h:
        return "forbidden"
    if "角色" in h or "人物" in h or "roles" in h or "chars" in h:
        return "roles"
    if "suspense" in h or "悬念" in h:
        return "suspense"
    if "foreshadow" in h or "伏笔" in h:
        return "foreshadow"
    if "twist" in h or "反转" in h:
        return "twist"
    return None


def _looks_like_header(cells: List[str]) -> bool:
    return any(("要发生什么" in c) or (c.strip().lower() in _HEADER_HINTS) for c in cells)


def _is_separator(cells: List[str]) -> bool:
    joined = "".join(cells)
    return (not any(cells)) or set(joined) <= set("-: ")


def _positional_row(cells: List[str]) -> Dict:
    row: Dict = {"ch": _to_int(cells[0])}
    for i, key in enumerate(_POSITIONAL, start=1):
        row[key] = cells[i] if i < len(cells) else ""
    return row


def load_outline(root: str) -> List[Dict]:
    """读 大纲/细纲蓝图.md,返回规范行列表(按 ch 升序);无文件返回 []。
    每行: {"ch", "title", "goal", "hard", "forbidden", "roles",
            "suspense", "foreshadow", "twist"}。"""
    p = os.path.join(root, OUTLINE_REL)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        text = f.read()
    rows: List[Dict] = []
    headers = None
    for raw in text.splitlines():
        line = raw.strip()
        if "|" not in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if headers is None:
            if _looks_like_header(cells):
                headers = cells
                continue
            if _is_separator(cells):
                continue
            if _to_int(cells[0]) is None:
                continue
            rows.append(_positional_row(cells))
            continue
        if _is_separator(cells):
            continue
        ch_idx = 0
        for i, h in enumerate(headers):
            if _norm_key(h) == "ch":
                ch_idx = i
                break
        if ch_idx >= len(cells):
            continue
        chnum = _to_int(cells[ch_idx])
        if chnum is None:
            continue
        row: Dict = {"ch": chnum, "title": ""}
        for i, h in enumerate(headers):
            k = _norm_key(h)
            if k and k != "ch":
                row[k] = cells[i] if i < len(cells) else ""
        rows.append(row)
    rows.sort(key=lambda r: r["ch"])
    return rows


def _merge_cells(row: Dict) -> str:
    """suspense/foreshadow/twist 非空合并。"""
    parts = [str(row.get(k) or "").strip() for k in ("suspense", "foreshadow", "twist")]
    return "；".join(x for x in parts if x)


def _foreshadow_todo(state: Dict, ch: int, limit: int = 5) -> List[str]:
    """活跃伏笔中 note 非空或 adv_ch 距当前 ≥3 的 id(≤5 条,note 优先、按埋设章序)。"""
    cands = []
    for pid, v in st.active_promises(state):
        adv = int(v.get("adv_ch") or 0)
        note = (v.get("note") or "").strip()
        if note or (adv and ch - adv >= 3):
            cands.append((pid, 0 if note else 1, adv))
    cands.sort(key=lambda t: (t[1], t[2]))
    return [t[0] for t in cands[:limit]]


def build_contract(root: str, state: Dict, ch: int) -> Dict:
    """构建第 ch 章写作合同。
    - goal/hard/ending: 细纲蓝图第 ch 行;ending_requirement 取 ch+1 行
      suspense/foreshadow/twist 合并(本章结尾须为其埋伏笔)。
    - forbidden: 未曝光信息差 id + 细纲行"禁区"列。
    - 无细纲文件 → goal="(无细纲,依 大纲/总纲.md 一句话)",不抛错。"""
    outline = load_outline(root)
    has_outline = bool(outline)
    row = next((r for r in outline if r["ch"] == ch), None)
    next_row = next((r for r in outline if r["ch"] == ch + 1), None)
    gaps = [g for g, _ in st.unrevealed_gaps(state)]

    sources: Dict[str, Optional[str]] = {"追踪状态": st.state_path(root)}
    if has_outline:
        sources["细纲蓝图"] = os.path.join(root, OUTLINE_REL)

    if not has_outline:
        goal = "(无细纲,依 大纲/总纲.md 一句话)"
        hard: List[str] = []
        forbidden: List[str] = list(gaps)
        ending = ""
        sources["总纲"] = os.path.join(root, SUMMARY_REL)
    elif row is None:
        goal = "(细纲蓝图无第%d章行)" % ch
        hard = []
        forbidden = list(gaps)
        ending = ""
    else:
        goal = row.get("goal") or ""
        hard = split_list(row.get("hard"))
        forbidden = list(gaps) + split_list(row.get("forbidden"))
        ending = _merge_cells(next_row) if next_row else ""

    return {
        "goal": goal,
        "hard_constraints": hard,
        "forbidden": forbidden,
        "foreshadow_todo": _foreshadow_todo(state, ch),
        "ending_requirement": ending,
        "sources": sources,
    }
