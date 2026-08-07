# -*- coding: utf-8 -*-
"""tests/test_checks.py:collect_checks 十一项 + redlines 正则表。
覆盖:正常路径 + 失败路径 + 边界(空书、缺文件、超长卡、缺状态、非法参数)。"""
import os
import re

import pytest

from storyrepo import state as st
from storyrepo.checks import collect_checks, redlines
from conftest import add_chapter, make_book, write_file


def refresh(root):
    """重放全部章节事实并入档(让 state mtime 新于正文)。"""
    s = st.load_state(root)
    for f in st.chapter_files(root):
        p = os.path.join(root, "定稿", "正文", f)
        st.merge_chapter_facts(s, st.chapter_num(f), st.frontmatter(p))
    st.save_state(root, s)
    from storyrepo import views
    views.write_views(root, s)


def clean_prose(n):
    """恰好 n 个汉字、无重复 4-gram(每片段 ≤3 次)、避开占位符/红线词的单段正文。"""
    pool = "".join(chr(0x4E00 + i) for i in range(2000))
    return (pool * (n // 2000 + 1))[:n]


def check_of(checks, name):
    return next(c for c in checks if c["name"] == name)


class TestRedlines:
    def test_table_shape(self):
        rl = redlines()
        assert len(rl) >= 4
        for pat, name in rl:
            assert isinstance(pat, str) and isinstance(name, str)
            re.compile(pat)                      # 必须可编译
        names = [n for _, n in rl]
        for want in ("章末总结体", "预告体", "万能比喻", "抽象升华"):
            assert want in names
        # 兼容 templates/doctor.py 既有红线(learn/report 复用同一张表)
        pats = [p for p, _ in rl]
        for canon in (r"他终于明白", r"他不知道的是", r"无人入眠", r"像潮水般|如闪电般|仿佛春风"):
            assert canon in pats

    def test_each_pattern_hits_its_sentence(self):
        hits = {
            "章末总结体": "本章讲述了主角的成长。",
            "预告体": "下一章将揭晓真相。",
            "万能比喻": "这场景仿佛一幅画卷。",
            "抽象升华": "或许,这就是命运的安排。",
        }
        for cat, sentence in hits.items():
            assert any(re.search(p, sentence) for p, n in redlines() if n.startswith(cat)), cat

    def test_doctor_patterns_hit(self):
        cases = ("他终于明白了。", "这一夜注定不平静。", "他不知道的是,风雨将至。",
                 "无人入眠。", "月光像潮水般涌来。")
        for s in cases:
            assert any(re.search(p, s) for p, _ in redlines()), s

    def test_plain_prose_no_hit(self):
        for pat, _ in redlines():
            assert not re.search(pat, "他推开门,走了进去。风从走廊尽头吹来。")


class TestNumbering:
    def test_contiguous_ok(self, book):
        for i in range(1, 4):
            add_chapter(book, i, prose="第%d章正文。" % i)
        assert check_of(collect_checks(book), "编号连续且唯一")["ok"]

    def test_gap_fails(self, book):
        for i in (1, 2, 4):
            add_chapter(book, i, prose="正文。")
        c = check_of(collect_checks(book), "编号连续且唯一")
        assert not c["ok"] and "编号不连续" in c["detail"]

    def test_duplicate_fails(self, book):
        add_chapter(book, 1, title="开局", prose="a")
        add_chapter(book, 1, title="备用开局", prose="b")
        add_chapter(book, 2, prose="c")
        c = check_of(collect_checks(book), "编号连续且唯一")
        assert not c["ok"]

    def test_empty_ok(self, book):
        assert check_of(collect_checks(book), "编号连续且唯一")["ok"]


class TestWords:
    def test_in_window_ok(self, book):
        add_chapter(book, 1, prose=clean_prose(3000))
        assert check_of(collect_checks(book), "字数窗口")["ok"]

    def test_boundaries_ok(self, book):
        add_chapter(book, 1, prose=clean_prose(2600))    # 下限 min-400
        add_chapter(book, 2, prose=clean_prose(4000))    # 上限 max+200
        assert check_of(collect_checks(book), "字数窗口")["ok"]

    def test_below_fails(self, book):
        add_chapter(book, 1, prose=clean_prose(2599))
        c = check_of(collect_checks(book), "字数窗口")
        assert not c["ok"] and "低于下限" in c["detail"]

    def test_above_fails(self, book):
        add_chapter(book, 1, prose=clean_prose(4001))
        c = check_of(collect_checks(book), "字数窗口")
        assert not c["ok"] and "超出上限" in c["detail"]

    def test_custom_max_words(self, tmp_path):
        root = make_book(str(tmp_path / "b"))
        write_file(root, "book.yaml",
                   "---\nname: b\nmin_words_per_chapter: 3000\nmax_words_per_chapter: 5000\n---\n")
        add_chapter(root, 1, prose=clean_prose(4001))    # 4001 <= 5000+200
        assert check_of(collect_checks(root), "字数窗口")["ok"]

    def test_chapter_param(self, book):
        add_chapter(book, 1, prose=clean_prose(3000))
        add_chapter(book, 2, prose=clean_prose(100))
        assert not check_of(collect_checks(book), "字数窗口")["ok"]
        assert check_of(collect_checks(book, chapter=1), "字数窗口")["ok"]
        assert not check_of(collect_checks(book, chapter=2), "字数窗口")["ok"]

    def test_missing_chapter_fails(self, book):
        add_chapter(book, 1, prose=clean_prose(3000))
        c = check_of(collect_checks(book, chapter=9), "字数窗口")
        assert not c["ok"] and "不存在" in c["detail"]

    def test_empty_ok(self, book):
        assert check_of(collect_checks(book), "字数窗口")["ok"]


class TestPlaceholder:
    def test_todo_fails(self, book):
        add_chapter(book, 1, prose="这段 TODO 还没写完。")
        c = check_of(collect_checks(book), "占位符")
        assert not c["ok"] and "TODO" in c["detail"]

    def test_brace_fails(self, book):
        add_chapter(book, 1, prose="这里 {NAME} 待补。")
        c = check_of(collect_checks(book), "占位符")
        assert not c["ok"] and "{NAME}" in c["detail"]

    def test_clean_ok(self, book):
        add_chapter(book, 1, prose="一切正常,没有遗漏内容。")
        assert check_of(collect_checks(book), "占位符")["ok"]

    def test_empty_ok(self, book):
        assert check_of(collect_checks(book), "占位符")["ok"]


class TestLeaks:
    def _gap_book(self, book):
        add_chapter(book, 1, prose="第一章正文。", gaps_new="S-001, S-002")
        refresh(book)

    def test_leak_fails(self, book):
        self._gap_book(book)
        add_chapter(book, 2, prose="他知道了 S-001 的秘密。")
        c = check_of(collect_checks(book), "泄密扫描")
        assert not c["ok"] and "S-001" in c["detail"]

    def test_no_leak_ok(self, book):
        self._gap_book(book)
        add_chapter(book, 2, prose="他知道了那个秘密。")
        assert check_of(collect_checks(book), "泄密扫描")["ok"]

    def test_frontmatter_excluded(self, book):
        # front matter 的 info_gaps_new/revealed 字段不算泄密(只扫 st.body)
        add_chapter(book, 1, prose="第一章正文。", gaps_new="S-001")
        refresh(book)
        add_chapter(book, 2, prose="风平浪静。", gaps_revealed="S-001")
        assert check_of(collect_checks(book), "泄密扫描")["ok"]

    def test_revealed_gap_allowed(self, book):
        add_chapter(book, 1, prose="第一章正文。", gaps_new="S-001")
        add_chapter(book, 2, prose="第二章正文。", gaps_revealed="S-001")
        refresh(book)
        add_chapter(book, 3, prose="真相是 S-001。")   # 已曝光 → 允许
        assert check_of(collect_checks(book), "泄密扫描")["ok"]

    def test_chapter_param(self, book):
        add_chapter(book, 1, prose="第一章正文。", gaps_new="S-001")
        refresh(book)
        add_chapter(book, 2, prose="秘密 S-001 被提起。")
        assert check_of(collect_checks(book, chapter=1), "泄密扫描")["ok"]
        assert not check_of(collect_checks(book, chapter=2), "泄密扫描")["ok"]

    def test_missing_state_fails(self, book):
        add_chapter(book, 1, prose="正文。")
        os.remove(st.state_path(book))
        c = check_of(collect_checks(book), "泄密扫描")
        assert not c["ok"] and "缺追踪状态" in c["detail"]


class TestEntities:
    def test_registered_ok(self, book):
        write_file(book, "定稿/设定/名册.md", "# 名册\n阿米\n米粒\n")
        add_chapter(book, 1, prose="阿米和米粒同行。", entities_new="阿米, 米粒")
        assert check_of(collect_checks(book), "实体登记")["ok"]

    def test_missing_roster_fails(self, book):
        add_chapter(book, 1, prose="阿米登场。", entities_new="阿米")
        c = check_of(collect_checks(book), "实体登记")
        assert not c["ok"] and "名册" in c["detail"]

    def test_partial_fails(self, book):
        write_file(book, "定稿/设定/名册.md", "阿米")
        add_chapter(book, 1, prose="阿米和米粒同行。", entities_new="阿米,米粒")
        c = check_of(collect_checks(book), "实体登记")
        assert not c["ok"] and "米粒" in c["detail"]

    def test_no_entities_ok(self, book):
        add_chapter(book, 1, prose="正文。")
        assert check_of(collect_checks(book), "实体登记")["ok"]


class TestFiles:
    def test_ok(self, book):
        add_chapter(book, 1, prose="正文。")
        assert check_of(collect_checks(book), "章文件齐全")["ok"]

    def test_missing_summary_fails(self, book):
        add_chapter(book, 1, prose="正文。")
        os.remove(os.path.join(book, "定稿", "记忆", "章摘要", "001.md"))
        c = check_of(collect_checks(book), "章文件齐全")
        assert not c["ok"] and "章摘要" in c["detail"]

    def test_no_frontmatter_fails(self, book):
        write_file(book, "定稿/正文/001-无头.md", "# 第1章\n\n正文内容。\n")
        c = check_of(collect_checks(book), "章文件齐全")
        assert not c["ok"] and "front matter" in c["detail"]


class TestRedlineCheck:
    def test_hit_fails_with_snippet(self, book):
        add_chapter(book, 1, prose="他走到窗前,本章讲述了今日的经过。")
        c = check_of(collect_checks(book), "AI红线")
        assert not c["ok"] and "章末总结体" in c["detail"] and "片段" in c["detail"]

    def test_all_four_kinds_fail(self, book):
        cases = ("本章讲述了主角的成长。", "下一章将揭晓真相。",
                 "这场景仿佛一幅画卷。", "或许,这就是命运的安排。")
        for i, prose in enumerate(cases, 1):
            add_chapter(book, i, prose=prose)
        c = check_of(collect_checks(book), "AI红线")
        assert not c["ok"] and "第2章" in c["detail"]

    def test_clean_ok(self, book):
        add_chapter(book, 1, prose="他推开门,走了进去。")
        assert check_of(collect_checks(book), "AI红线")["ok"]


class TestRepeat:
    def test_adjacent_common5_fails(self, book):
        add_chapter(book, 1, prose="今天天气真好,我们出发吧。\n\n今天天气真不错,继续前行。")
        c = check_of(collect_checks(book), "复读检测")
        assert not c["ok"] and "相邻" in c["detail"]

    def test_common4_ok(self, book):
        add_chapter(book, 1, prose="今天天气真好。\n\n今天天气还行。")
        assert check_of(collect_checks(book), "复读检测")["ok"]

    def test_4gram_six_fails(self, book):
        add_chapter(book, 1, prose="阿米阿米阿米阿米阿米阿米阿米")
        c = check_of(collect_checks(book), "复读检测")
        assert not c["ok"] and "出现" in c["detail"]

    def test_4gram_five_ok(self, book):
        add_chapter(book, 1, prose="阿米阿米阿米阿米")
        assert check_of(collect_checks(book), "复读检测")["ok"]

    def test_clean_long_prose_ok(self, book):
        add_chapter(book, 1, prose=clean_prose(3000))
        assert check_of(collect_checks(book), "复读检测")["ok"]


class TestContract:
    def test_must_cover_ok(self, book):
        add_chapter(book, 1, prose="阿米和米粒在河边相遇。", must_cover="阿米, 米粒")
        assert check_of(collect_checks(book), "合同断言")["ok"]

    def test_must_cover_missing_fails(self, book):
        add_chapter(book, 1, prose="阿米独自在河边。", must_cover="阿米, 米粒")
        c = check_of(collect_checks(book), "合同断言")
        assert not c["ok"] and "米粒" in c["detail"]

    def test_forbidden_hit_fails(self, book):
        add_chapter(book, 1, prose="赵三出现在街角。", forbidden="赵三")
        c = check_of(collect_checks(book), "合同断言")
        assert not c["ok"] and "禁区" in c["detail"]

    def test_both_fail(self, book):
        add_chapter(book, 1, prose="赵三独自在河边。", must_cover="阿米", forbidden="赵三")
        c = check_of(collect_checks(book), "合同断言")
        assert not c["ok"] and "阿米" in c["detail"] and "赵三" in c["detail"]

    def test_no_contract_ok(self, book):
        add_chapter(book, 1, prose="正文。")
        assert check_of(collect_checks(book), "合同断言")["ok"]


class TestFresh:
    def test_fresh_ok(self, book):
        add_chapter(book, 1, prose=clean_prose(3000))
        refresh(book)
        assert check_of(collect_checks(book), "追踪新鲜")["ok"]

    def test_stale_fails(self, book):
        add_chapter(book, 1, prose=clean_prose(3000))
        refresh(book)
        add_chapter(book, 2, prose=clean_prose(3000))    # 状态未跟上
        c = check_of(collect_checks(book), "追踪新鲜")
        assert not c["ok"] and "早于" in c["detail"]

    def test_card_oversize_fails(self, book):
        write_file(book, "追踪/上下文.md", "字" * 13000)
        c = check_of(collect_checks(book), "追踪新鲜")
        assert not c["ok"] and "超过" in c["detail"] and "字节" in c["detail"]

    def test_prewrite_skips(self, book):
        add_chapter(book, 1, prose=clean_prose(3000))
        refresh(book)
        add_chapter(book, 2, prose=clean_prose(3000))    # 状态过期,但 prewrite 不查
        c = check_of(collect_checks(book, stage="prewrite"), "追踪新鲜")
        assert c["ok"] and "跳过" in c["detail"]

    def test_missing_state_fails(self, book):
        os.remove(st.state_path(book))
        c = check_of(collect_checks(book), "追踪新鲜")
        assert not c["ok"] and "缺追踪状态" in c["detail"]

    def test_no_chapters_ok(self, book):
        assert check_of(collect_checks(book), "追踪新鲜")["ok"]


class TestSummary:
    def test_empty_fails(self, book):
        add_chapter(book, 1, prose="正文。", fm_extra={"summary": "  "})
        c = check_of(collect_checks(book), "摘要非空")
        assert not c["ok"] and "为空" in c["detail"]

    def test_ok(self, book):
        add_chapter(book, 1, prose="正文。")
        assert check_of(collect_checks(book), "摘要非空")["ok"]


class TestCollect:
    def test_shape(self, book):
        checks = collect_checks(book)
        assert isinstance(checks, list) and len(checks) == 11
        for c in checks:
            assert set(c) == {"ok", "name", "detail"}
            assert isinstance(c["ok"], bool)
            assert isinstance(c["name"], str) and isinstance(c["detail"], str)

    def test_names_order(self, book):
        names = [c["name"] for c in collect_checks(book)]
        assert names[0] == "编号连续且唯一"
        assert names[1] == "字数窗口"
        assert names[9] == "追踪新鲜"
        assert names[-1] == "摘要非空"

    def test_invalid_stage(self, book):
        with pytest.raises(ValueError):
            collect_checks(book, stage="release")

    def test_invalid_chapter(self, book):
        with pytest.raises(ValueError):
            collect_checks(book, chapter="abc")

    def test_missing_book_yaml(self, tmp_path):
        root = str(tmp_path / "无书")
        os.makedirs(root)
        with pytest.raises(FileNotFoundError):
            collect_checks(root)

    def test_clean_book_all_ok(self, book):
        for i in (1, 2):
            add_chapter(book, i, prose=clean_prose(3000))
        refresh(book)
        for c in collect_checks(book):
            assert c["ok"], c
