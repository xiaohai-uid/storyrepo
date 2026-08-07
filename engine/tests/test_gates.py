# -*- coding: utf-8 -*-
"""tests/test_gates.py:gate 三 stage 过滤(1/2弱提示/3/11 vs 全量)。
覆盖:正常路径 + 失败路径 + 边界(空书、缺状态、非法参数、chapter 定向)。"""
import os

import pytest

from storyrepo import state as st
from storyrepo.gates import gate
from conftest import add_chapter


def refresh(root):
    """重放全部章节事实并入档(让 state mtime 新于正文)。"""
    s = st.load_state(root)
    for f in st.chapter_files(root):
        p = os.path.join(root, "定稿", "正文", f)
        st.merge_chapter_facts(s, st.chapter_num(f), st.frontmatter(p))
    st.save_state(root, s)
    from storyrepo import views
    views.write_views(root, s)


def backdate_state(root):
    """把追踪状态 mtime 拨回 100 秒,模拟「状态早于最新正文」。"""
    p = st.state_path(root)
    t = os.path.getmtime(p)
    os.utime(p, (t - 100, t - 100))


def clean_prose(n=3000):
    """恰好 n 个汉字、无重复 4-gram、避开占位符/红线词的单段正文。"""
    pool = "".join(chr(0x4E00 + i) for i in range(2000))
    return (pool * (n // 2000 + 1))[:n]


def clean_book(book, n=2):
    for i in range(1, n + 1):
        add_chapter(book, i, prose=clean_prose())
    refresh(book)
    return book


class TestShape:
    def test_keys(self, book):
        r = gate(book)
        assert set(r) == {"passed", "fails", "oks"}
        assert isinstance(r["passed"], bool)
        assert isinstance(r["fails"], list) and isinstance(r["oks"], list)
        assert all(isinstance(x, str) for x in r["fails"] + r["oks"])


class TestPrewrite:
    def test_pass_clean(self, book):
        clean_book(book)
        r = gate(book, "prewrite")
        assert r["passed"] is True and r["fails"] == []

    def test_placeholder_fails(self, book):
        add_chapter(book, 1, prose="这章 TODO 未写完。")
        r = gate(book, "prewrite")
        assert r["passed"] is False
        assert any("占位符" in f for f in r["fails"])

    def test_leak_skipped(self, book):
        add_chapter(book, 1, prose="第一章。", gaps_new="S-001")
        refresh(book)
        add_chapter(book, 2, prose="秘密 S-001 泄露了。")
        r = gate(book, "prewrite")
        assert r["passed"] is True                 # 泄密扫描被跳过,不拦 prewrite
        assert any("泄密扫描(跳过)" in o for o in r["oks"])

    def test_words_weak_hint(self, book):
        add_chapter(book, 1, prose=clean_prose(100))
        r = gate(book, "prewrite")
        assert r["passed"] is True                 # 字数不足只弱提示
        assert any("字数窗口(弱提示" in o for o in r["oks"])

    def test_summary_fails(self, book):
        add_chapter(book, 1, prose="正文。", fm_extra={"summary": " "})
        r = gate(book, "prewrite")
        assert r["passed"] is False
        assert any("摘要非空" in f for f in r["fails"])

    def test_numbering_fails(self, book):
        add_chapter(book, 1, prose="a")
        add_chapter(book, 3, prose="c")
        r = gate(book, "prewrite")
        assert r["passed"] is False
        assert any("编号连续" in f for f in r["fails"])

    def test_others_marked_skipped(self, book):
        clean_book(book)
        r = gate(book, "prewrite")
        skipped = [o for o in r["oks"] if "(跳过)" in o]
        assert len(skipped) == 7                    # 4,5,6,7,8,9,10 跳过
        assert any("追踪新鲜(跳过)" in o for o in skipped)


class TestPrecommit:
    def test_pass_clean(self, book):
        clean_book(book)
        r = gate(book, "precommit")
        assert r["passed"] is True and r["fails"] == []
        assert len(r["oks"]) == 11

    def test_fail_on_leak(self, book):
        add_chapter(book, 1, prose="第一章。", gaps_new="S-001")
        refresh(book)
        add_chapter(book, 2, prose="秘密 S-001 泄露了。")
        r = gate(book, "precommit")
        assert r["passed"] is False
        assert any("泄密扫描" in f for f in r["fails"])

    def test_fail_on_words(self, book):
        add_chapter(book, 1, prose=clean_prose(100))
        r = gate(book, "precommit")
        assert r["passed"] is False
        assert any("字数窗口" in f for f in r["fails"])

    def test_fail_on_stale_state(self, book):
        add_chapter(book, 1, prose=clean_prose())
        refresh(book)
        add_chapter(book, 2, prose=clean_prose())
        backdate_state(book)
        r = gate(book, "precommit")
        assert r["passed"] is False
        assert any("追踪新鲜" in f for f in r["fails"])

    def test_chapter_param(self, book):
        add_chapter(book, 1, prose=clean_prose())
        add_chapter(book, 2, prose="这章 TODO。")
        refresh(book)
        assert gate(book, "precommit")["passed"] is False      # 第2章占位符
        assert gate(book, "precommit", chapter=1)["passed"] is True
        assert gate(book, "precommit", chapter=2)["passed"] is False


class TestPostcommit:
    def test_pass_clean(self, book):
        clean_book(book)
        r = gate(book, "postcommit")
        assert r["passed"] is True and r["fails"] == []

    def test_fail_stale(self, book):
        add_chapter(book, 1, prose=clean_prose())
        refresh(book)
        add_chapter(book, 2, prose=clean_prose())
        backdate_state(book)
        r = gate(book, "postcommit")
        assert r["passed"] is False
        assert any("追踪新鲜" in f for f in r["fails"])


class TestEmpty:
    def test_all_stages_pass(self, book):
        for stage in ("prewrite", "precommit", "postcommit"):
            r = gate(book, stage)
            assert r["passed"] is True, stage


class TestErrors:
    def test_invalid_stage(self, book):
        with pytest.raises(ValueError):
            gate(book, "release")

    def test_missing_book(self, tmp_path):
        root = str(tmp_path / "无")
        os.makedirs(root)
        with pytest.raises(FileNotFoundError):
            gate(root)

    def test_no_state_prewrite_passes_precommit_fails(self, book):
        add_chapter(book, 1, prose=clean_prose())
        os.remove(st.state_path(book))
        assert gate(book, "prewrite")["passed"] is True       # 不依赖状态
        r = gate(book, "precommit")
        assert r["passed"] is False
        assert any("泄密扫描" in f for f in r["fails"])
        assert any("追踪新鲜" in f for f in r["fails"])
