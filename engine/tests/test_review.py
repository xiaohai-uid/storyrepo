# -*- coding: utf-8 -*-
import os, json
import pytest
from storyrepo import models, review as rv


def two_issues():
    return [
        models.ReviewIssue("critical", "continuity", "第3段", "时间线冲突",
                           evidence="原文引用", fix_hint="改为次日"),
        models.ReviewIssue("low", "pacing", "第5段", "节奏略拖", blocking=False),
    ]


class TestSaveReview:
    def test_structure(self, book):
        p = rv.save_review(book, 3, two_issues())
        assert p == rv.review_path(book, 3)
        data = json.load(open(p, encoding="utf-8"))
        assert data["chapter"] == 3
        assert data["issues_count"] == 2
        assert data["blocking_count"] == 1
        assert data["has_blocking"] is True
        assert data["issues"][0]["severity"] == "critical"
        assert data["issues"][0]["blocking"] is True

    def test_zero_padded_name(self, book):
        p = rv.save_review(book, 152, [])
        assert p.endswith(os.path.join("工作区", "评审报告", "第152章.json"))


class TestLoadReview:
    def test_ok(self, book):
        rv.save_review(book, 3, two_issues())
        issues, errors = rv.load_review(rv.review_path(book, 3))
        assert errors == []
        assert len(issues) == 2
        assert issues[0].blocking is True
        assert issues[1].blocking is False

    def test_missing_optional_fields_ok(self, book):
        rv.save_review(book, 5, [models.ReviewIssue("high", "logic", "第1段", "问题")])
        p = rv.review_path(book, 5)
        data = json.load(open(p, encoding="utf-8"))
        del data["issues"][0]["evidence"]
        del data["issues"][0]["fix_hint"]
        json.dump(data, open(p, "w", encoding="utf-8"), ensure_ascii=False)
        issues, errors = rv.load_review(p)
        assert errors == []
        assert issues[0].evidence == "" and issues[0].fix_hint == ""

    def test_bad_severity_in_errors(self, book):
        rv.save_review(book, 2, [models.ReviewIssue("low", "other", "l", "d")])
        p = rv.review_path(book, 2)
        data = json.load(open(p, encoding="utf-8"))
        data["issues"][0]["severity"] = "urgent"
        json.dump(data, open(p, "w", encoding="utf-8"), ensure_ascii=False)
        issues, errors = rv.load_review(p)
        assert issues == []
        assert any("severity" in e for e in errors)

    def test_bad_category_in_errors(self, book):
        rv.save_review(book, 2, [models.ReviewIssue("low", "other", "l", "d")])
        p = rv.review_path(book, 2)
        data = json.load(open(p, encoding="utf-8"))
        data["issues"][0]["category"] = "typo"
        json.dump(data, open(p, "w", encoding="utf-8"), ensure_ascii=False)
        issues, errors = rv.load_review(p)
        assert issues == []
        assert any("category" in e for e in errors)

    def test_missing_issues_key(self, book):
        p = rv.review_path(book, 1)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump({"chapter": 1}, open(p, "w", encoding="utf-8"), ensure_ascii=False)
        issues, errors = rv.load_review(p)
        assert issues == [] and errors and "issues" in errors[0]

    def test_invalid_json(self, book):
        p = rv.review_path(book, 1)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w", encoding="utf-8").write("{ 这不是 json")
        issues, errors = rv.load_review(p)
        assert issues == [] and errors and "非法" in errors[0]

    def test_top_level_not_object(self, book):
        p = rv.review_path(book, 1)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump([1, 2], open(p, "w", encoding="utf-8"))
        issues, errors = rv.load_review(p)
        assert issues == [] and errors and "顶层" in errors[0]

    def test_missing_file_raises(self, book):
        with pytest.raises(FileNotFoundError):
            rv.load_review(rv.review_path(book, 99))


class TestHasBlocking:
    def test_critical_blocks(self):
        assert rv.has_blocking([models.ReviewIssue("critical", "logic", "l", "d")]) is True

    def test_nonblocking(self):
        assert rv.has_blocking([models.ReviewIssue("high", "logic", "l", "d")]) is False
        assert rv.has_blocking([]) is False


class TestWriteReport:
    def test_content(self, book):
        rv.save_review(book, 3, two_issues())
        p = rv.write_report(book, 3, two_issues())
        t = open(p, encoding="utf-8").read()
        assert "第3章" in t and "blocking" in t
        assert "时间线冲突" in t and "第3段" in t and "改为次日" in t
        assert "未放行" in t

    def test_no_issues(self, book):
        p = rv.write_report(book, 4, [])
        t = open(p, encoding="utf-8").read()
        assert "未发现问题" in t and "无 blocking" in t


class TestApplyBlocking:
    def test_blocking_not_released(self, book):
        rv.save_review(book, 3, two_issues())
        assert rv.apply_blocking(book, 3) is False

    def test_clean_released(self, book):
        rv.save_review(book, 3, [models.ReviewIssue("medium", "pacing", "l", "拖")])
        assert rv.apply_blocking(book, 3) is True

    def test_missing_raises(self, book):
        with pytest.raises(FileNotFoundError):
            rv.apply_blocking(book, 3)

    def test_corrupt_raises_valueerror(self, book):
        p = rv.review_path(book, 3)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w", encoding="utf-8").write("{bad")
        with pytest.raises(ValueError):
            rv.apply_blocking(book, 3)
