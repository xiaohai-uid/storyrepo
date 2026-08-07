# -*- coding: utf-8 -*-
"""追踪状态(单一权威):_tracking-state.json 的加载/保存/合并。
机制来源:oh-story tracking_commit(单一权威/事务/并发控制),自研轻量实现。
状态写入只允许经过本模块 + views.write_views 重建派生视图。"""
import os, re, json
from typing import Dict, List, Optional, Tuple

TRACKING_DIR = "追踪"
STATE_FILE = "_tracking-state.json"
MAX_CARD_BYTES = 12288

def tracking_path(root: str) -> str:
    return os.path.join(root, TRACKING_DIR)

def state_path(root: str) -> str:
    return os.path.join(tracking_path(root), STATE_FILE)

def new_state(root: str) -> Dict:
    return {
        "spec": 1,
        "book": os.path.basename(root) or "未命名",
        "imported_through_chapter": 0,
        "state_revision": 1,
        "chapters": {},
        "promises": {},
        "info_gaps": {},
        "timeline": [],
        "entity_states": {},
        "reader_knowledge": {"reveals": []},
    }

def load_state(root: str) -> Dict:
    p = state_path(root)
    if not os.path.exists(p):
        raise FileNotFoundError("缺追踪状态(先跑 storyrepo init): %s" % p)
    try:
        with open(p, encoding="utf-8") as f:
            s = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError("追踪状态损坏(%s): %s。救援:删除该文件后重跑 storyrepo init,或用 storyrepo revision 重放重建。" % (p, e))
    # 最小 schema 补全(容错空/残缺状态)
    base = new_state(root)
    for k, v in base.items():
        if k not in s:
            s[k] = v
    for k in ("promises", "info_gaps", "entity_states", "chapters"):
        if not isinstance(s.get(k), dict):
            s[k] = {}
    if not isinstance(s.get("timeline"), list):
        s["timeline"] = []
    if not isinstance(s.get("state_revision"), int):
        s["state_revision"] = 1
    return s

def save_state(root: str, s: Dict) -> None:
    os.makedirs(tracking_path(root), exist_ok=True)
    p = state_path(root)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)   # 原子写:中途崩溃不损坏原文件

def init_state(root: str) -> bool:
    """幂等初始化;返回 True 表示本次新建。"""
    if os.path.exists(state_path(root)):
        return False
    s = new_state(root)
    save_state(root, s)
    for d in ("角色状态", "逐章记录"):
        os.makedirs(os.path.join(tracking_path(root), d), exist_ok=True)
    ctx = os.path.join(tracking_path(root), "上下文.md")
    if not os.path.exists(ctx):
        with open(ctx, "w", encoding="utf-8") as f:
            f.write("# 续写状态卡(7 栏,待首章后由 views 重建)\n")
    return True

# ── 修订号(并发控制,参考 oh-story expected_state_revision) ──
def revision(s: Dict) -> int:
    return int(s.get("state_revision", 1))

def bump_revision(s: Dict) -> int:
    s["state_revision"] = revision(s) + 1
    return s["state_revision"]

# ── 章节文件 ──
def chapter_files(root: str) -> List[str]:
    d = os.path.join(root, "定稿", "正文")
    if not os.path.isdir(d):
        return []
    return sorted(f for f in os.listdir(d) if re.match(r"\d{3,4}-", f) and f.endswith(".md"))

def chapter_num(fname: str) -> int:
    m = re.match(r"(\d{3,4})-", fname)
    return int(m.group(1)) if m else -1

def latest_chapter(root: str) -> int:
    fs = chapter_files(root)
    return max((chapter_num(f) for f in fs), default=0)

def frontmatter(path: str) -> Dict:
    """解析章节 front matter(平铺 KV),返回 dict;缺则空 dict。
    防护:第二段必须含 ':' 才视为 front matter,否则整文当正文。"""
    with open(path, encoding="utf-8") as f:
        t = f.read()
    if not t.startswith("---"):
        return {}
    seg = t.split("---", 2)[1]
    if ":" not in seg:
        return {}
    d = {}
    for line in seg.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            d[k.strip()] = v.strip()
    return d

def body(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        t = f.read()
    if t.startswith("---"):
        t = re.sub(r"^---.*?---\n", "", t, flags=re.S)
    return t

def fm_list(fm: Dict, key: str) -> List[str]:
    return [e.strip() for e in str(fm.get(key, "")).split(",") if e.strip() and e.strip() not in ('""', "''")]

def hanzi(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))

# ── 事实合并(章事务 Step 7 的核心) ──
def merge_chapter_facts(s: Dict, ch: int, fm: Dict, summary: str = "") -> List[str]:
    """合并一章事实;返回警告列表(未知 P/S id 被忽略等)。"""
    warn = []
    for p in fm_list(fm, "promises_new"):
        s["promises"].setdefault(p, {"status": "open", "open_ch": ch, "adv_ch": ch, "done_ch": None, "note": ""})
    for p in fm_list(fm, "promises_advanced"):
        if p in s["promises"]:
            s["promises"][p]["adv_ch"] = ch
            s["promises"][p]["status"] = "adv"
        else:
            warn.append("未知承诺 id 被忽略: %s(请检查拼写或先在 promises_new 登记)" % p)
    for p in fm_list(fm, "promises_done"):
        if p in s["promises"]:
            s["promises"][p]["status"] = "done"
            s["promises"][p]["done_ch"] = ch
        else:
            warn.append("未知承诺 id 被忽略: %s(请检查拼写或先在 promises_new 登记)" % p)
    for g in fm_list(fm, "info_gaps_new"):
        s["info_gaps"].setdefault(g, {"revealed": False, "plant_ch": ch, "reveal_ch": None, "note": ""})
    for g in fm_list(fm, "info_gaps_revealed"):
        if g in s["info_gaps"]:
            s["info_gaps"][g]["revealed"] = True
            s["info_gaps"][g]["reveal_ch"] = ch
        else:
            warn.append("未知信息差 id 被忽略: %s(请检查拼写或在 info_gaps_new 登记)" % g)
    for e in fm_list(fm, "entities_new"):
        s["entity_states"].setdefault(e, {"first_ch": ch, "where": "", "state": ""})
    if summary:
        s["timeline"].append({"ch": ch, "event": summary[:80], "kind": "fact"})
    s["chapters"][str(ch)] = {"status": "committed", "title": fm.get("title", ""), "words": fm.get("words", "")}
    s["imported_through_chapter"] = max([int(k) for k in s["chapters"]]) if s["chapters"] else 0
    return warn

# ── 查询 ──
def active_promises(s: Dict) -> List[Tuple[str, Dict]]:
    return [(k, v) for k, v in s.get("promises", {}).items() if v.get("status") != "done"]

def unrevealed_gaps(s: Dict) -> List[Tuple[str, Dict]]:
    return [(k, v) for k, v in s.get("info_gaps", {}).items() if not v.get("revealed")]
