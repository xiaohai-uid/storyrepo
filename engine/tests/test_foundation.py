# -*- coding: utf-8 -*-
import os
from storyrepo import config, models, state as st
from conftest import make_book, add_chapter


class TestConfig:
    def test_defaults_merge(self, tmp_path):
        root = make_book(str(tmp_path / "b"), total=120, minw=2000)
        c = config.load_config(root)
        assert c["total_chapters"] == 120
        assert c["min_words_per_chapter"] == 2000
        assert c["max_words_per_chapter"] == 2800          # min+800
        assert c["target_words"] == 990000                 # 默认

    def test_missing_book_raises(self, tmp_path):
        import pytest
        with pytest.raises(FileNotFoundError):
            config.load_config(str(tmp_path / "无"))


class TestModels:
    def test_review_issue_roundtrip(self):
        i = models.ReviewIssue("critical", "continuity", "第3段", "冲突")
        d = i.to_dict()
        i2 = models.ReviewIssue.from_dict(d)
        assert i2.severity == "critical" and i2.blocking is True

    def test_bad_severity_raises(self):
        import pytest
        with pytest.raises(ValueError):
            models.ReviewIssue("urgent", "logic", "x", "y")

    def test_promise_gap_entity_roundtrip(self):
        p = models.Promise(status="adv", open_ch=1, adv_ch=5)
        assert models.Promise.from_dict(p.to_dict()) == p
        g = models.InfoGap(revealed=True, plant_ch=2, reveal_ch=30)
        assert models.InfoGap.from_dict(g.to_dict()) == g


class TestState:
    def test_init_idempotent(self, tmp_path):
        root = make_book(str(tmp_path / "b"))
        assert st.init_state(root) is False          # 已存在
        assert st.load_state(root)["state_revision"] == 1

    def test_merge_facts(self, book):
        add_chapter(book, 1, prose="甲", promises_new="P-001, P-002", gaps_new="S-001",
                    entities_new="阿米,米粒")
        s = st.load_state(book)
        st.merge_chapter_facts(s, 1, st.frontmatter(st.chapter_files(book) and __import__("os").path.join(book, "定稿", "正文", st.chapter_files(book)[0])))
        assert st.active_promises(s) == [("P-001", s["promises"]["P-001"]), ("P-002", s["promises"]["P-002"])]
        assert st.unrevealed_gaps(s) == [("S-001", s["info_gaps"]["S-001"])]
        assert s["entity_states"]["阿米"]["first_ch"] == 1
        assert s["imported_through_chapter"] == 1

    def test_promise_lifecycle(self, book):
        add_chapter(book, 1, prose="a", promises_new="P-001")
        add_chapter(book, 2, prose="b", promises_advanced="P-001")
        add_chapter(book, 3, prose="c", promises_done="P-001")
        s = st.load_state(book)
        for n in (1, 2, 3):
            fs = st.chapter_files(book)
            f = [x for x in fs if st.chapter_num(x) == n][0]
            st.merge_chapter_facts(s, n, st.frontmatter(os.path.join(book, "定稿", "正文", f)))
        assert st.active_promises(s) == []
        assert s["promises"]["P-001"]["done_ch"] == 3
        assert s["imported_through_chapter"] == 3

    def test_gap_reveal(self, book):
        add_chapter(book, 1, prose="a", gaps_new="S-001")
        add_chapter(book, 4, prose="d", gaps_revealed="S-001")
        s = st.load_state(book)
        for n in (1, 4):
            f = [x for x in st.chapter_files(book) if st.chapter_num(x) == n][0]
            st.merge_chapter_facts(s, n, st.frontmatter(os.path.join(book, "定稿", "正文", f)))
        assert st.unrevealed_gaps(s) == []
        assert s["info_gaps"]["S-001"]["reveal_ch"] == 4

    def test_revision_bump(self, book):
        s = st.load_state(book)
        assert st.bump_revision(s) == 2
        assert st.revision(s) == 2

    def test_latest_chapter(self, book):
        add_chapter(book, 1, prose="a")
        add_chapter(book, 2, prose="b")
        assert st.latest_chapter(book) == 2

    def test_hanzi(self):
        assert st.hanzi("hello 你好") == 2
