# -*- coding: utf-8 -*-
"""门禁:按 stage 过滤 collect_checks 结果,输出通过/失败清单。
机制来源:oh-story 机检门禁(stage 分段放行),自研轻量实现。
- prewrite:只跑 1(编号)/2(字数,允许弱提示)/3(占位符)/11(摘要);其余一律 ok 记"跳过"。
- precommit:全量,passed = 无 fail。
- postcommit:全量且第 10 项(追踪新鲜)必查(不得跳过,计入 fail)。"""
from typing import Dict, Optional

from storyrepo.checks import collect_checks


def gate(root: str, stage: str = "precommit", chapter=None) -> Dict:
    """{"passed": bool, "fails": [str], "oks": [str]}。"""
    checks = collect_checks(root, stage, chapter)
    if stage == "prewrite":
        active = {1, 2, 3, 11}
    else:
        active = set(range(1, len(checks) + 1))
    fails, oks = [], []
    for i, c in enumerate(checks, start=1):
        if i not in active:
            oks.append("%s(跳过)" % c["name"])
            continue
        if i == 2 and stage == "prewrite" and not c["ok"]:
            # 第 2 项在 prewrite 仅弱提示,不计 fail
            oks.append("%s(弱提示: %s)" % (c["name"], c["detail"]))
            continue
        if c["ok"]:
            oks.append(c["name"])
        else:
            fails.append("%s: %s" % (c["name"], c["detail"]))
    return {"passed": not fails, "fails": fails, "oks": oks}
