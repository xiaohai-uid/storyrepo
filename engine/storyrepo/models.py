# -*- coding: utf-8 -*-
"""领域模型(dataclass + JSON 往返)。机制来源:webnovel-writer review-schema / oh-story tracking。"""
from dataclasses import dataclass, field, asdict
from typing import List, Optional

SEVERITIES = ("critical", "high", "medium", "low")
CATEGORIES = ("continuity", "setting", "character", "timeline", "ai_flavor", "logic", "pacing", "other")

@dataclass
class ReviewIssue:
    severity: str
    category: str
    location: str
    description: str
    evidence: str = ""
    fix_hint: str = ""
    blocking: bool = False

    def __post_init__(self):
        if self.severity not in SEVERITIES:
            raise ValueError("severity 非法: %s" % self.severity)
        if self.category not in CATEGORIES:
            raise ValueError("category 非法: %s" % self.category)
        if self.severity == "critical":
            self.blocking = True

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(severity=d["severity"], category=d["category"], location=d["location"],
                   description=d["description"], evidence=d.get("evidence", ""),
                   fix_hint=d.get("fix_hint", ""),
                   blocking=bool(d.get("blocking", d.get("severity") == "critical")))


@dataclass
class Promise:
    status: str = "open"              # open | adv | done
    open_ch: Optional[int] = None
    adv_ch: Optional[int] = None
    done_ch: Optional[int] = None
    note: str = ""

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(status=d.get("status", "open"), open_ch=d.get("open_ch"), adv_ch=d.get("adv_ch"),
                   done_ch=d.get("done_ch"), note=d.get("note", ""))


@dataclass
class InfoGap:
    revealed: bool = False
    plant_ch: Optional[int] = None
    reveal_ch: Optional[int] = None
    note: str = ""

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(revealed=bool(d.get("revealed", False)), plant_ch=d.get("plant_ch"),
                   reveal_ch=d.get("reveal_ch"), note=d.get("note", ""))


@dataclass
class EntityState:
    first_ch: Optional[int] = None
    where: str = ""
    state: str = ""

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(first_ch=d.get("first_ch"), where=d.get("where", ""), state=d.get("state", ""))


@dataclass
class ChapterRecord:
    status: str = "committed"         # committed | rejected
    title: str = ""
    words: str = ""

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(status=d.get("status", "committed"), title=d.get("title", ""), words=d.get("words", ""))


@dataclass
class TimelineEvent:
    ch: int
    event: str
    kind: str = "fact"                # fact(客观) | reveal(读者已见) | private(作者独知)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(ch=d.get("ch", 0), event=d.get("event", ""), kind=d.get("kind", "fact"))
