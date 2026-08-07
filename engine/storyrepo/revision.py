# -*- coding: utf-8 -*-
"""回炉级联:重放式重算 + expected_revision 并发控制 + 后续影响扫描。
机制来源:oh-story workflow-revision(大修级联:重算增量/伏笔当前值/三轨合并/角色快照/并发控制/影响清单)。
规则:状态写入只经 state.py;派生视图只经 views.write_views。"""
import os
from typing import Dict, List
from storyrepo import state as st


def _replay(root: str, old: Dict) -> Dict:
    """从头(1..latest)重放全部章节 front matter 与摘要,天然幂等正确。"""
    fresh = st.new_state(root)
    # 保留旧状态中 new_state 未定义的键(避免数据丢失)
    for k, v in old.items():
        if k not in fresh:
            fresh[k] = v
    for f in st.chapter_files(root):
        n = st.chapter_num(f)
        if n < 1:
            continue
        fm = st.frontmatter(os.path.join(root, "定稿", "正文", f))
        st.merge_chapter_facts(fresh, n, fm, summary=fm.get("summary", ""))
    # 三轨保留:merge 只产生 fact 事件,reveal/private 事件按 (ch, 原序) 插回,保持时间线交错顺序
    non_fact = [(i, dict(ev)) for i, ev in enumerate(old.get("timeline", []))
                if isinstance(ev, dict) and ev.get("kind") not in ("fact", None)]
    # 把非 fact 事件按其 ch 与旧序插入 fact 序列(同 ch 时按旧顺序)
    for old_i, ev in sorted(non_fact, key=lambda t: (t[1].get("ch", 0), t[0])):
        ch = ev.get("ch", 0)
        # 找到最后一个 ch 不大于本事件的 fact 位置后插入
        pos = 0
        for j, e in enumerate(fresh["timeline"]):
            if e.get("ch", 0) <= ch:
                pos = j + 1
        fresh["timeline"].insert(pos, ev)
    return fresh


def _changed_ids(old: Dict, fresh: Dict) -> set:
    """重放前后相比,状态发生变化的 P/S/实体 id 集合。"""
    changed = set()
    for key in ("promises", "info_gaps", "entity_states"):
        a, b = old.get(key, {}), fresh.get(key, {})
        for k in set(a) | set(b):
            if a.get(k) != b.get(k):
                changed.add(k)
    return changed


def _scan_impact(root: str, ch: int, changed: set) -> List[str]:
    """扫描全部其他章节 front matter 的 promises/entities 字段,引用已变 P/S/实体 → impact 提示。
    不再假设只有 ch 之后的章会受影响(用户传错章号时也不会漏报)。"""
    impact = []
    for f in st.chapter_files(root):
        n = st.chapter_num(f)
        if n == ch or n < 1:
            continue
        fm = st.frontmatter(os.path.join(root, "定稿", "正文", f))
        refs = []
        for key in ("promises_new", "promises_advanced", "promises_done",
                    "info_gaps_new", "info_gaps_revealed", "entities_new"):
            refs += st.fm_list(fm, key)
        hit = sorted(set(refs) & changed)
        if hit:
            impact.append("第%d章 引用 %s(状态已变),需同步检查" % (n, "、".join(hit)))
    return impact


def cascade_revision(root: str, state: Dict, ch: int, expected_revision: int) -> Dict:
    """回炉级联:重放 1..latest → 冲突检测 → 影响扫描 → bump+save → 重建视图。
    返回 {"ok": bool, "conflict": bool, "impact": [str], "notes": [str]}。"""
    if int(expected_revision) != st.revision(state):
        return {"ok": False, "conflict": True, "impact": [],
                "notes": ["期望修订号 %s 与当前 %d 不符,拒绝级联(请重读最新状态)" % (expected_revision, st.revision(state))]}
    latest = st.latest_chapter(root)
    fresh = _replay(root, state)
    fresh["state_revision"] = st.revision(state)   # 保留并发号,随后 bump
    changed = _changed_ids(state, fresh)
    impact = _scan_impact(root, ch, changed)
    st.bump_revision(fresh)
    st.save_state(root, fresh)
    state.clear()
    state.update(fresh)                            # 调用方持有的引用同步为新状态
    notes = ["重放范围 1..%d 章,状态由章节文件重算(幂等)" % latest]
    preserved = sum(1 for ev in fresh["timeline"] if ev.get("kind") not in ("fact", None))
    if preserved:
        notes.append("timeline 保留非 fact 事件 %d 条" % preserved)
    if not changed:
        notes.append("重放结果与旧状态一致(无事实变更)")
    else:
        notes.append("受影响的 P/S/实体 %d 项: %s" % (len(changed), "、".join(sorted(changed))))
    try:
        from storyrepo import views
        views.write_views(root, fresh)
        notes.append("派生视图已重建")
    except ImportError:
        notes.append("views 模块未就绪,派生视图待重建")
    except Exception as e:
        notes.append("派生视图重建失败: %s" % e)
    notes.append("级联完成;续写前请再跑 checks.gate(postcommit) 确认全绿")
    return {"ok": True, "conflict": False, "impact": impact, "notes": notes}
