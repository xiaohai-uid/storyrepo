# -*- coding: utf-8 -*-
"""批次模式(batch.py):subagent-parallel 的批次计划与顺序合并。
机制来源:规格 Implementation Decisions「批次模式」;合并路径与串行 commit(cmd_commit)等价。
引擎只负责计划 JSON 结构与顺序合并;子代理编排(并行起草)发生在技能层,不进引擎。

- create_batch_plan(root, chapters):生成批次计划 dict(每章:章号/合同/正文输出路径/状态)。
- merge_batch(root, plan, chapters_done):按章序逐章走既有 commit 路径
  (读 front matter → merge_chapter_facts → bump_revision → save_state → write_views);
  单章机检失败标记 rejected 不阻塞同批;已提交章由幂等守卫整批拒绝(报错,零写入)。"""
import glob
import os
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from storyrepo import contract as ct
from storyrepo import gates, state as st, views

MODE = "subagent-parallel"


def _body_glob(root: str, ch: int) -> str:
    """第 ch 章正文输出路径(glob 模板):标题由 worker 在 front matter 自定,故以 * 匹配。"""
    return os.path.join(root, "定稿", "正文", "%03d-*.md" % ch)


def create_batch_plan(root: str, chapters: Iterable) -> Dict:
    """生成批次计划(计划 JSON 主体,由 cli 落盘 工作区/批次-<时间戳>.json)。

    chapters: 章号可迭代(数字或数字字符串),自动升序去重。
    返回 {"book", "mode", "created", "chapters": [
        {"chapter": int, "contract": dict(contract.build_contract),
         "output_path": str(正文输出 glob), "status": "pending"}]}。"""
    s = st.load_state(root)
    items = []
    for ch in sorted({int(c) for c in chapters}):
        items.append({
            "chapter": ch,
            "contract": ct.build_contract(root, s, ch),
            "output_path": _body_glob(root, ch),
            "status": "pending",
        })
    return {
        "book": s.get("book", ""),
        "mode": MODE,
        "created": datetime.now().isoformat(timespec="seconds"),
        "expected_revision": st.revision(s),
        "chapters": items,
    }


def merge_batch(root: str, plan: Dict, chapters_done: Optional[Dict] = None) -> Dict:
    """按章序合并批次计划,逐章走既有 commit 路径(修订号/时间线与串行等价)。

    chapters_done: {章号: 真值} 表示该章 worker 已返回;缺省 None = 全部视为已返回。
    逐章(升序)处理:
      - 幂等守卫:计划中任何章已提交 → 整批拒绝(raise ValueError),零写入,不污染时间线。
      - worker 未返回 → 记 skipped,不合并。
      - 正文文件缺失/不唯一 → 记 rejected。
      - doctor precommit 机检失败 → 记 rejected,不阻塞同批其他章。
      - 通过 → 读 front matter → merge_chapter_facts → bump_revision → save_state → write_views。
    合并前先做一次无 bump 的保存+视图重建:批次正文全部由 worker 预写,
    该刷新既满足机检「追踪新鲜」检查,也修复中断遗留的「状态新、卡旧」中间态。

    返回 {"merged": [..], "rejected": [{chapter, fails|reason}], "skipped": [..],
          "warns": {章: [警告]}, "revision": int, "ok": bool(全部计划章入账)}。"""
    if not isinstance(plan, dict) or not isinstance(plan.get("chapters"), list):
        raise ValueError("批次计划非法:缺 chapters 数组")
    items = []
    for it in plan["chapters"]:
        if not isinstance(it, dict) or "chapter" not in it:
            raise ValueError("批次计划非法:chapters 每项须含 chapter")
        try:
            ch = int(it["chapter"])
        except (TypeError, ValueError):
            raise ValueError("批次计划非法:chapter 须为章号数字,收到 %r" % (it["chapter"],))
        if ch < 1:
            raise ValueError("批次计划非法:章号须 ≥1,收到 %d" % ch)
        items.append((ch, it))
    items.sort(key=lambda t: t[0])

    s = st.load_state(root)
    # 并发守卫:计划固化的修订号与当前不符 → 拒绝(防止两个并发 merge 交错污染)
    exp = plan.get("expected_revision")
    if exp is not None and int(exp) != st.revision(s):
        raise ValueError("批次计划期望 rev %s,当前 %d——状态已变化,请重建计划" % (exp, st.revision(s)))
    # M1 幂等守卫:计划中任何章已提交 → 整批拒绝(重复 merge 同一计划在此被拦下)
    committed = {int(k) for k in s.get("chapters", {})}
    dup = [ch for ch, _ in items if ch in committed]
    if dup:
        raise ValueError("批次含已提交章 %s(rev %d)。重写走 storyrepo revision --chapter N(重放式级联);或为剩余章另建计划。"
                         % ("、".join(str(c) for c in dup), st.revision(s)))
    # 预刷新(无 bump 保存 + 派生视图重建)
    st.save_state(root, s)
    views.write_views(root, s)

    returned = {int(k): v for k, v in (chapters_done or {}).items()}
    if chapters_done is None:
        returned = {ch: True for ch, _ in items}
    merged: List[int] = []
    rejected: List[Dict] = []
    skipped: List[int] = []
    warns: Dict[int, List[str]] = {}
    for ch, it in items:
        if ch not in returned:
            skipped.append(ch)
            continue
        pattern = str(it.get("output_path") or "")
        if pattern and not os.path.isabs(pattern):
            pattern = os.path.join(root, pattern)
        files = sorted(glob.glob(pattern)) if pattern else []
        if not files:
            rejected.append({"chapter": ch, "reason": "缺正文(worker 未产出文件): %s" % pattern})
            continue
        if len(files) > 1:
            rejected.append({"chapter": ch, "reason": "正文文件不唯一: %s" % "、".join(files)})
            continue
        g = gates.gate(root, "precommit", ch)
        if not g["passed"]:
            rejected.append({"chapter": ch, "fails": g["fails"]})
            continue
        fm = st.frontmatter(files[0])
        warns[ch] = st.merge_chapter_facts(s, ch, fm, fm.get("summary", ""))
        st.bump_revision(s)
        st.save_state(root, s)
        views.write_views(root, s)
        merged.append(ch)
    return {
        "merged": merged,
        "rejected": rejected,
        "skipped": skipped,
        "warns": warns,
        "revision": st.revision(s),
        "ok": bool(merged) and not rejected and not skipped,
    }
