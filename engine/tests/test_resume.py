# -*- coding: utf-8 -*-
import os
from conftest import add_chapter
from storyrepo import models, resume, review as rv, state as st


def merged_ch1(book):
    add_chapter(book, 1, prose="甲", promises_new="P-001")
    s = st.load_state(book)
    f = [x for x in st.chapter_files(book) if st.chapter_num(x) == 1][0]
    st.merge_chapter_facts(s, 1, st.frontmatter(os.path.join(book, "定稿", "正文", f)))
    st.save_state(book, s)
    return s


class TestDiagnose:
    def test_not_started_empty_book(self, book):
        d = resume.diagnose(book)
        assert d["status"] == "not_started"
        assert d["files"] == {"正文": False, "评审报告": False, "追踪已合并": False, "状态卡新鲜": True}
        assert "第1章" in d["next_step"]

    def test_not_started_next_chapter(self, book):
        add_chapter(book, 1, prose="甲")
        d = resume.diagnose(book)          # ch=None → 最新章+1
        assert d["status"] == "not_started"
        assert "第2章" in d["next_step"]

    def test_draft_after_body(self, book):
        add_chapter(book, 1, prose="甲")
        d = resume.diagnose(book, 1)
        assert d["status"] == "draft"
        assert d["files"]["正文"] is True and d["files"]["评审报告"] is False

    def test_draft_with_blocking(self, book):
        add_chapter(book, 1, prose="甲")
        rv.save_review(book, 1, [models.ReviewIssue("critical", "logic", "第1段", "设定冲突")])
        d = resume.diagnose(book, 1)
        assert d["status"] == "draft"
        assert "blocking" in d["next_step"]

    def test_draft_with_corrupt_review(self, book):
        add_chapter(book, 1, prose="甲")
        p = rv.review_path(book, 1)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w", encoding="utf-8").write("{bad")
        d = resume.diagnose(book, 1)
        assert d["status"] == "draft"
        assert "损坏" in d["next_step"]

    def test_reviewed_not_committed(self, book):
        add_chapter(book, 1, prose="甲")
        rv.save_review(book, 1, [models.ReviewIssue("low", "pacing", "x", "略拖")])
        d = resume.diagnose(book, 1)
        assert d["status"] == "reviewed"
        assert d["files"]["追踪已合并"] is False

    def test_committed(self, book):
        merged_ch1(book)
        rv.save_review(book, 1, [models.ReviewIssue("low", "pacing", "x", "略拖")])
        d = resume.diagnose(book, 1)
        assert d["status"] == "committed"
        assert d["files"]["追踪已合并"] is True
        assert "第2章" in d["next_step"]

    def test_committed_stale_card_warns(self, book):
        merged_ch1(book)
        rv.save_review(book, 1, [models.ReviewIssue("low", "pacing", "x", "略拖")])
        d = resume.diagnose(book, 1)
        assert d["status"] == "committed"
        assert d["files"]["状态卡新鲜"] is False
        assert "状态卡" in d["next_step"]

    def test_unknown_review_without_body(self, book):
        rv.save_review(book, 2, [models.ReviewIssue("low", "pacing", "x", "略拖")])
        d = resume.diagnose(book, 2)
        assert d["status"] == "unknown"

    def test_missing_tracking_state(self, book):
        add_chapter(book, 1, prose="甲")
        os.remove(st.state_path(book))
        d = resume.diagnose(book, 1)
        assert d["status"] == "draft"
        assert "追踪" in d["next_step"]
