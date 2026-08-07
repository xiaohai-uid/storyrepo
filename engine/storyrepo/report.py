# -*- coding: utf-8 -*-
"""作者报告:三段式(状态/做了什么/下一步),纯文本面向作者,无 JSON/无路径。
机制来源:webnovel-writer 恢复契约(只建议不覆盖)+ oh-story check(续写前全绿)。"""
import os
from storyrepo import config, state as st
from storyrepo import review as rv

GATE_STAGES = ("prewrite", "precommit", "postcommit")


def author_report(root: str, stage: str, ch=None) -> str:
    """三段式:状态(最新章/字数/活跃承诺/未曝光信息差)→ 做了什么(gate/审查/结算)→ 下一步建议。"""
    try:
        s = st.load_state(root)
    except FileNotFoundError:
        s = None
    files = st.chapter_files(root)
    latest = max((st.chapter_num(f) for f in files), default=0)
    total_words = sum(st.hanzi(st.body(os.path.join(root, "定稿", "正文", f))) for f in files)
    active = len(st.active_promises(s)) if s else 0
    gaps = len(st.unrevealed_gaps(s)) if s else 0
    try:
        plan = config.load_config(root).get("total_chapters", 0)
    except FileNotFoundError:
        plan = 0
    target = ch or latest or 1

    lines = ["# 作者报告(%s)" % stage, "",
             "## 一、状态",
             "- 最新章: %d / 计划 %d 章" % (latest, plan),
             "- 正文总字数: %d 字" % total_words,
             "- 活跃承诺: %d  未曝光信息差: %d" % (active, gaps),
             "",
             "## 二、本次做了什么(%s)" % stage]
    gate_ok = None
    if stage in GATE_STAGES:
        try:
            from storyrepo import gates
            g = gates.gate(root, stage=stage, chapter=ch)
            gate_ok = bool(g.get("passed"))
            lines.append("- 机检(%s): 通过 %d 项,问题 %d 项 → %s"
                         % (stage, len(g.get("oks", [])), len(g.get("fails", [])),
                            "放行" if gate_ok else "未放行"))
        except ImportError:
            lines.append("- 机检: gates 模块未就绪(待模块 1 落地)")
    else:
        lines.append("- 机检: 本阶段不涉及")
    blocking = False
    rp = rv.review_path(root, target)
    if os.path.exists(rp):
        try:
            issues, errors = rv.load_review(rp)
        except Exception:
            issues, errors = [], ["评审报告无法解析"]
        if errors:
            lines.append("- 审查: 第%d章评审报告损坏(%s)" % (target, "、".join(errors)))
            blocking = True
        else:
            blocking = rv.has_blocking(issues)
            lines.append("- 审查: 第%d章 问题 %d 条,blocking %d 条"
                         % (target, len(issues), sum(1 for i in issues if i.blocking)))
    else:
        lines.append("- 审查: 第%d章尚无评审报告" % target)
    committed = sorted(int(k) for k in (s or {}).get("chapters", {})) if s else []
    lines.append("- 已结算章: %d 章(最新 %s)" % (len(committed),
                 "第%d章" % committed[-1] if committed else "无"))
    lines += ["", "## 三、下一步建议"]
    nexts = []
    if s is None:
        nexts.append("缺追踪状态:先跑 init_state")
    if gate_ok is False:
        nexts.append("机检未放行:定点修复后重跑 gate(失败只补跑失败步骤)")
    if blocking:
        nexts.append("第%d章存在 blocking:定点修复后进润色,勿重跑评审" % target)
    if stage == "postcommit" and not nexts:
        nexts.append("本批次可结转:git add -A && git commit(或先重建派生视图)")
    if not nexts:
        nexts.append("续写第%d章:合同→任务书→起草→机检→评审→结算" % (target + 1))
    lines += ["- " + n for n in nexts]
    return "\n".join(lines) + "\n"
