# -*- coding: utf-8 -*-
"""评审落库:JSON 读写 / blocking 门禁 / 人类可读报告。
机制来源:webnovel-writer review-schema(子代理 JSON 协议 + 门禁;blocking 定点修复,不重跑评审)。"""
import os, json
from typing import List, Tuple
from storyrepo import models

REVIEW_DIR = os.path.join("工作区", "评审报告")


def review_path(root: str, ch: int) -> str:
    return os.path.join(root, REVIEW_DIR, "第%03d章.json" % ch)


def report_path(root: str, ch: int) -> str:
    return os.path.join(root, REVIEW_DIR, "第%03d章.md" % ch)


def _parse_issues(raw):
    issues, errors = [], []
    if raw is None:
        return issues, ["缺 issues 字段"]
    if not isinstance(raw, list):
        return issues, ["issues 字段不是数组"]
    for i, d in enumerate(raw, 1):
        if not isinstance(d, dict):
            errors.append("第 %d 条 issue 不是对象" % i)
            continue
        try:
            issues.append(models.ReviewIssue.from_dict(d))
        except KeyError as e:
            errors.append("第 %d 条 issue 缺字段 %s" % (i, e))
        except ValueError as e:
            errors.append("第 %d 条 issue %s" % (i, e))
    return issues, errors


def load_review(path: str) -> Tuple[List[models.ReviewIssue], List[str]]:
    """读评审 JSON;evidence/fix_hint 可缺,severity/category 非法进 errors;文件缺失抛 FileNotFoundError。"""
    if not os.path.exists(path):
        raise FileNotFoundError("缺评审报告: %s" % path)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (ValueError, UnicodeDecodeError) as e:
        return [], ["评审 JSON 非法: %s" % e]
    if not isinstance(data, dict):
        return [], ["评审 JSON 顶层不是对象"]
    return _parse_issues(data.get("issues"))


def has_blocking(issues: List[models.ReviewIssue]) -> bool:
    return any(getattr(i, "blocking", False) for i in issues)


def save_review(root: str, ch: int, issues: List[models.ReviewIssue]) -> str:
    """写 工作区/评审报告/第NNN章.json,返回路径。"""
    p = review_path(root, ch)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    blocking_count = sum(1 for i in issues if i.blocking)
    payload = {
        "chapter": ch,
        "issues": [i.to_dict() for i in issues],
        "issues_count": len(issues),
        "blocking_count": blocking_count,
        "has_blocking": blocking_count > 0,
    }
    with open(p, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    return p


def write_report(root: str, ch: int, issues: List[models.ReviewIssue]) -> str:
    """人类可读审查报告 md:问题清单/位置/建议 + blocking 标记,返回路径。"""
    p = report_path(root, ch)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    blocking_count = sum(1 for i in issues if i.blocking)
    L = ["# 第%d章 审查报告" % ch, "",
         "- 问题数: %d,其中 blocking: %d" % (len(issues), blocking_count),
         "- 结论: %s" % ("有 blocking,未放行,先定点修复" if blocking_count else "无 blocking,可进入润色/结算"),
         ""]
    if not issues:
        L.append("未发现问题。")
    for idx, i in enumerate(issues, 1):
        tag = "⛔ blocking" if i.blocking else "非 blocking"
        L.append("### %d. [%s/%s] %s(%s)" % (idx, i.severity, i.category, tag, i.location))
        L.append("- 问题: %s" % i.description)
        if i.evidence:
            L.append("- 证据: %s" % i.evidence)
        if i.fix_hint:
            L.append("- 建议: %s" % i.fix_hint)
        L.append("")
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(L).rstrip() + "\n")
    return p


def apply_blocking(root: str, ch: int) -> bool:
    """读取既有评审 json:有 blocking → False(未放行);报告缺失/损坏抛错。"""
    p = review_path(root, ch)
    if not os.path.exists(p):
        raise FileNotFoundError("缺评审报告,无法放行: %s" % p)
    issues, errors = load_review(p)
    if errors:
        raise ValueError("评审报告损坏,无法放行: %s" % "; ".join(errors))
    return not has_blocking(issues)
