# -*- coding: utf-8 -*-
"""断点续跑:诊断单章进度,给出恢复契约建议(只建议,不覆盖)。
机制来源:webnovel-writer 恢复契约(每章查断点/失败只补跑失败步骤)。"""
import os
from storyrepo import state as st
from storyrepo import review as rv


def _chapter_path(root: str, ch: int):
    for f in st.chapter_files(root):
        if st.chapter_num(f) == ch:
            return os.path.join(root, "定稿", "正文", f)
    return None


def diagnose(root: str, ch=None) -> dict:
    """依据 正文/评审 json/追踪 chapters/状态卡新鲜 判定进度,输出恢复建议。
    返回 {"status": "not_started|draft|reviewed|committed|unknown",
          "next_step": str, "files": {str: bool}}。"""
    latest = st.latest_chapter(root)
    target = ch if ch is not None else (latest + 1 if latest else 1)
    body_ok = _chapter_path(root, target) is not None
    review_p = rv.review_path(root, target)
    review_ok = os.path.exists(review_p)
    try:
        s = st.load_state(root)
    except FileNotFoundError:
        s = None
    chapters = (s or {}).get("chapters", {})
    tracked_ok = str(target) in chapters or target in chapters
    card_ok = True
    files = st.chapter_files(root)
    if files:
        card_p = os.path.join(st.tracking_path(root), "上下文.md")
        newest = max(os.path.getmtime(os.path.join(root, "定稿", "正文", f)) for f in files)
        card_ok = os.path.exists(card_p) and os.path.getmtime(card_p) >= newest
    fm = {"正文": body_ok, "评审报告": review_ok, "追踪已合并": tracked_ok, "状态卡新鲜": card_ok}

    if not body_ok:
        if review_ok:
            status = "unknown"
            step = "异常:第%d章有评审报告但无正文,请人工核查,勿直接续写覆盖" % target
        else:
            status = "not_started"
            step = "第%d章尚未动笔:先跑机检 prewrite,再按 合同→任务书→起草 推进" % target
    else:
        corrupt = blocking = False
        if review_ok:
            try:
                issues, errors = rv.load_review(review_p)
                corrupt = bool(errors)
                blocking = rv.has_blocking(issues) or corrupt
            except Exception:
                corrupt = blocking = True
        if not review_ok:
            status = "draft"
            step = "正文已写未评审:跑机检 precommit,再评审(Step 5)"
        elif corrupt:
            status = "draft"
            step = "评审报告损坏:重跑评审(Step 5)或用户裁决"
        elif blocking:
            status = "draft"
            step = "评审有 blocking:定点修复后直接进润色,不重跑评审"
        elif tracked_ok:
            status = "committed"
            step = "第%d章已结算:续写第%d章或结转" % (target, target + 1)
            if not card_ok:
                step += ";状态卡过期,先重建视图再续写"
        else:
            status = "reviewed"
            step = "评审通过未结算:跑追踪合并 + 重建派生视图(Step 7)"
    if s is None and body_ok:
        step += "(缺追踪状态:先 init_state)"
    return {"status": status, "next_step": step, "files": fm}
