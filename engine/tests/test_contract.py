# -*- coding: utf-8 -*-
import os
import pytest
from storyrepo import state as st
from storyrepo.contract import build_contract, load_outline
from conftest import add_chapter

OUTLINE = """# 细纲蓝图

| ch | 标题 | 要发生什么 | 硬约束 | 禁区 | 角色 | suspense | foreshadow | twist |
|----|------|-----------|--------|------|------|----------|------------|-------|
| 1 | 开局 | 主角被追杀 | 无 | 赵三 | 阿米 | 神秘老者现身 | 断剑 | 老者是仇人 |
| 2 | 惊变 | 阿米出手救人 | 字数4000 | 赵三,钱四 | 阿米,米粒 | 老者身份 | 断剑来历 | 米粒是细作 |
| 3 | 迷雾 | 追查断剑来历 | | | 米粒 | 城主失踪 | | |
| 4 | 夜探 | 夜探城主府 | 不写血腥 | 孙五 | 米粒,阿米 | 密道 | 铜钥匙 | |
| 5 | 秘闻 | 发现密道 | | | 阿米 | 老者的伤 | | |
| 6 | 转折 | 老者身份揭晓 | | | | | | |
"""


def merged_state(book, *chs):
    """合并指定章事实,返回 state。"""
    s = st.load_state(book)
    for n in chs:
        f = [x for x in st.chapter_files(book) if st.chapter_num(x) == n][0]
        st.merge_chapter_facts(s, n, st.frontmatter(os.path.join(book, "定稿", "正文", f)))
    return s


class TestBuildContract:
    def test_normal(self, book):
        add_chapter(book, 1, prose="甲", promises_new="P-001, P-002, P-004",
                    gaps_new="S-001, S-002", entities_new="阿米")
        add_chapter(book, 2, prose="乙", promises_done="P-004", gaps_revealed="S-002")
        add_chapter(book, 3, prose="丙", promises_new="P-003")
        write_outline(book, OUTLINE)
        s = merged_state(book, 1, 2, 3)
        s["promises"]["P-001"]["note"] = "结尾回收"          # note 非空 → 入选
        # P-002: adv_ch=1,距 ch=4 为 3 → 入选;P-003: adv_ch=3,距 1 → 排除;P-004 done → 排除

        c = build_contract(book, s, 4)
        assert c["goal"] == "夜探城主府"
        assert c["hard_constraints"] == ["不写血腥"]
        assert c["forbidden"] == ["S-001", "孙五"]           # 未曝光信息差 + 禁区列
        assert c["foreshadow_todo"] == ["P-001", "P-002"]
        assert c["ending_requirement"] == "老者的伤"          # ch+1 行 suspense/foreshadow/twist 合并
        assert c["sources"]["细纲蓝图"].endswith(os.path.join("大纲", "细纲蓝图.md"))
        assert c["sources"]["追踪状态"].endswith("_tracking-state.json")
        assert "总纲" not in c["sources"]

    def test_ending_merges_multiple_cells(self, book):
        write_outline(book, "1|开局|目标1|约束1|禁区1|角色1|悬念1|伏笔1|反转1\n"
                            "2|二章|目标2||| |悬念2||反转2\n")
        c = build_contract(book, st.load_state(book), 1)
        assert c["ending_requirement"] == "悬念2；反转2"
        assert c["hard_constraints"] == ["约束1"]
        assert c["forbidden"] == ["禁区1"]

    def test_headerless_simple_rows(self, book):
        write_outline(book, "1|开局|主角开局|字数3000|赵三|阿米|悬念A|伏笔B|反转C\n"
                            "2|惊变||||||||\n")
        c = build_contract(book, st.load_state(book), 1)
        assert c["goal"] == "主角开局"
        assert c["hard_constraints"] == ["字数3000"]
        assert c["forbidden"] == ["赵三"]
        assert c["ending_requirement"] == ""                  # ch+1 行无 suspense/foreshadow/twist

    def test_no_outline_placeholder(self, book):
        add_chapter(book, 1, prose="甲", gaps_new="S-001")
        s = merged_state(book, 1)
        c = build_contract(book, s, 2)                        # 无细纲文件,不抛错
        assert c["goal"] == "(无细纲,依 大纲/总纲.md 一句话)"
        assert c["hard_constraints"] == []
        assert c["ending_requirement"] == ""
        assert c["forbidden"] == ["S-001"]                    # 信息差照常
        assert c["sources"]["总纲"].endswith(os.path.join("大纲", "总纲.md"))
        assert "细纲蓝图" not in c["sources"]

    def test_outline_without_row_for_ch(self, book):
        write_outline(book, OUTLINE)
        add_chapter(book, 1, prose="甲", gaps_new="S-001")
        s = merged_state(book, 1)
        c = build_contract(book, s, 9)
        assert c["goal"] == "(细纲蓝图无第9章行)"
        assert c["forbidden"] == ["S-001"]

    def test_foreshadow_todo_limit_and_gaps(self, book):
        add_chapter(book, 1, prose="甲", promises_new="P-001, P-002, P-003, P-004, P-005, P-006")
        s = merged_state(book, 1)                             # 全部 adv_ch=1,距 ch=4 均 ≥3
        c = build_contract(book, s, 4)
        assert len(c["foreshadow_todo"]) == 5                 # ≤5 条
        assert set(c["foreshadow_todo"]) <= {"P-001", "P-002", "P-003", "P-004", "P-005", "P-006"}


class TestLoadOutline:
    def test_missing_file(self, book):
        assert load_outline(book) == []

    def test_parses_and_sorts(self, book):
        write_outline(book, "1|开局|目标1\n3|三章|目标3\n2|二章|目标2\n")
        rows = load_outline(book)
        assert [r["ch"] for r in rows] == [1, 2, 3]
        assert rows[0]["goal"] == "目标1"

    def test_ignores_non_table_lines(self, book):
        write_outline(book, "# 标题行\n\n说明文字\n| ch | 要发生什么 |\n|---|---|\n| 1 | 目标 |\n")
        rows = load_outline(book)
        assert len(rows) == 1 and rows[0]["goal"] == "目标"


def write_outline(book, content):
    from conftest import write_file
    write_file(book, "大纲/细纲蓝图.md", content)
