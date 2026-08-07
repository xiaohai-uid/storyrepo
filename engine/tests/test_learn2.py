# -*- coding: utf-8 -*-
"""tests/test_learn2.py:learn 学习回路(垂直切片 05)。
覆盖:absorb_review 吸收 AI 味反例 → 机检红线动态生效(doctor fail);反例库超 200 条裁最旧;trend 输出结构。
只测外部行为:模块公开函数(absorb_review / trend / checks.redlines)+ doctor(gates.gate)。"""
import os
import re

import pytest

from conftest import add_chapter, write_file
from storyrepo import checks, learn, models
from storyrepo.gates import gate
from storyrepo.review import save_review

PHRASE = "他忽然觉得胸口一暖"


def _lib_entries(book):
    lib = os.path.join(book, "文风", "审查反例库.md")
    with open(lib, encoding="utf-8") as fh:
        return [ln.strip() for ln in fh.read().splitlines()
                if ln.strip() and not ln.strip().startswith("#")]


def _redline_check(root, ch):
    return [c for c in checks.collect_checks(root, "precommit", ch) if c["name"] == "AI红线"][0]


class TestAbsorb:
    def test_absorb_writes_library(self, book):
        save_review(book, 1, [
            models.ReviewIssue(severity="high", category="ai_flavor", location="L12",
                               description="AI 味", evidence=PHRASE),
        ])
        assert learn.absorb_review(book, 1) == 1
        lib = os.path.join(book, "文风", "审查反例库.md")
        assert os.path.exists(lib)
        assert PHRASE in open(lib, encoding="utf-8").read()
        assert _lib_entries(book) == [PHRASE]

    def test_absorb_then_doctor_fails(self, book):
        """吸收后:含该反例短语的新正文在 doctor(precommit)红线 fail。"""
        save_review(book, 1, [
            models.ReviewIssue(severity="high", category="ai_flavor", location="L12",
                               description="AI 味", evidence=PHRASE),
        ])
        learn.absorb_review(book, 1)
        # 反例库短语被转义为正则并入红线表;无 root 时仍是纯内置表
        assert any(re.search(p, PHRASE) for p, _ in checks.redlines(book))
        assert not any(re.search(p, PHRASE) for p, _ in checks.redlines())
        add_chapter(book, 2, prose="他推门进来,%s。风从走廊尽头吹来。" % PHRASE, summary="二")
        item = _redline_check(book, 2)
        assert item["ok"] is False and "反例库" in item["detail"], item
        r = gate(book, "precommit", 2)
        assert r["passed"] is False
        assert any("反例库" in f for f in r["fails"]), r["fails"]

    def test_not_absorbed_redline_passes(self, book):
        """未吸收前:同句正文不触发红线(对照,避免自证式断言)。"""
        add_chapter(book, 1, prose="他推门进来,%s。风从走廊尽头吹来。" % PHRASE, summary="一")
        item = _redline_check(book, 1)
        assert item["ok"] is True, item

    def test_filter_severity_and_category(self, book):
        """severity<high 或 category≠ai_flavor 的 evidence 不吸收。"""
        save_review(book, 1, [
            models.ReviewIssue(severity="low", category="ai_flavor", location="L1",
                               description="低危", evidence=PHRASE),
            models.ReviewIssue(severity="high", category="continuity", location="L2",
                               description="设定冲突", evidence=PHRASE),
            models.ReviewIssue(severity="high", category="ai_flavor", location="L3",
                               description="AI 味", evidence="她忍不住轻轻一叹"),
        ])
        assert learn.absorb_review(book, 1) == 1
        lib = open(os.path.join(book, "文风", "审查反例库.md"), encoding="utf-8").read()
        assert "她忍不住轻轻一叹" in lib
        assert PHRASE not in lib

    def test_evidence_over_20_chars_skipped(self, book):
        long_ev = "他忽然觉得胸口一暖仿佛整个世界都安静了下来"  # 21 字,超限
        save_review(book, 1, [
            models.ReviewIssue(severity="high", category="ai_flavor", location="L1",
                               description="AI 味", evidence=long_ev),
        ])
        assert learn.absorb_review(book, 1) == 0
        assert not os.path.exists(os.path.join(book, "文风", "审查反例库.md"))

    def test_dedupe_reabsorb(self, book):
        save_review(book, 1, [
            models.ReviewIssue(severity="high", category="ai_flavor", location="L12",
                               description="AI 味", evidence=PHRASE),
        ])
        assert learn.absorb_review(book, 1) == 1
        assert learn.absorb_review(book, 1) == 0      # 去重:重复吸收不新增
        assert _lib_entries(book) == [PHRASE]

    def test_missing_review_raises(self, book):
        with pytest.raises(FileNotFoundError):
            learn.absorb_review(book, 3)

    def test_cap_200_trims_oldest(self, book):
        """预置 199 条旧反例 → 吸收第 200 条;再吸收 → 201 条超限,裁最旧保留最新。"""
        write_file(book, "文风/审查反例库.md",
                   "# 审查反例库(AI 味反例,机检动态合并)\n\n"
                   + "\n".join("旧反例%03d" % i for i in range(199)) + "\n")
        save_review(book, 1, [
            models.ReviewIssue(severity="high", category="ai_flavor", location="L1",
                               description="AI 味", evidence="新反例一条"),
        ])
        assert learn.absorb_review(book, 1) == 1
        entries = _lib_entries(book)
        assert len(entries) == 200
        assert entries[0] == "旧反例000" and entries[-1] == "新反例一条"
        save_review(book, 2, [
            models.ReviewIssue(severity="high", category="ai_flavor", location="L2",
                               description="AI 味", evidence="又一条新反例"),
        ])
        assert learn.absorb_review(book, 2) == 1
        entries = _lib_entries(book)
        assert len(entries) == 200                          # 超限裁最旧,不炸
        assert entries[0] == "旧反例001"                     # 最旧被裁
        assert "旧反例000" not in entries
        assert entries[-1] == "又一条新反例"                  # 最新保留
        # 被裁的旧反例不再进入红线表
        assert not any(re.search(p, "旧反例000") for p, _ in checks.redlines(book))
        assert any(re.search(p, "又一条新反例") for p, _ in checks.redlines(book))


class TestTrend:
    def test_structure_and_known_literals(self, book):
        add_chapter(book, 1, prose="你好。\n\n她说:「早安。」\n\n他又说了一句。\n\n", summary="一")
        add_chapter(book, 2, prose="他摇了摇头。\n\n", summary="二")
        add_chapter(book, 3, prose=("这一章讲述了主角的抉择。\n\n下一章,风雨将至。\n\n"
                                    "仿佛一幅画卷。\n\n或许这就是命运。\n\n"), summary="三")
        t = learn.trend(book, n=10)
        assert [d["chapter"] for d in t] == [1, 2, 3]       # 近 n 章、按章号升序
        for d in t:
            assert set(d) == {"chapter", "dialogue_ratio", "redline_hits", "avg_sentence_len", "words"}
            assert isinstance(d["dialogue_ratio"], float) and 0.0 <= d["dialogue_ratio"] <= 1.0
            assert isinstance(d["redline_hits"], int) and d["redline_hits"] >= 0
            assert d["avg_sentence_len"] > 0
        # 已知字面量:第 1 章 12 汉字 / 3 句(。！？切分)→ 平均句长 4.0;字数 = 汉字数
        assert t[0]["words"] == 12
        assert t[0]["avg_sentence_len"] == 4.0
        assert t[0]["dialogue_ratio"] == pytest.approx(1.0 / 3)
        # 第 3 章命中四条内置红线(章末总结体/预告体/万能比喻/抽象升华)
        assert t[2]["redline_hits"] == 4

    def test_n_limits_to_recent(self, book):
        for i in (1, 2, 3):
            add_chapter(book, i, prose="第%d句。\n\n" % i, summary=str(i))
        t = learn.trend(book, n=2)
        assert [d["chapter"] for d in t] == [2, 3]

    def test_trend_includes_absorbed_counterexample(self, book):
        """吸收反例后,trend 的红线命中计入本书反例库(近 n 章漂移可见)。"""
        add_chapter(book, 1, prose="他推门进来,%s。风从走廊尽头吹来。" % PHRASE, summary="一")
        assert learn.trend(book)[0]["redline_hits"] == 0
        save_review(book, 2, [
            models.ReviewIssue(severity="high", category="ai_flavor", location="L1",
                               description="AI 味", evidence=PHRASE),
        ])
        learn.absorb_review(book, 2)
        assert learn.trend(book)[0]["redline_hits"] == 1

    def test_empty_book(self, book):
        assert learn.trend(book) == []
