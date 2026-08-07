# -*- coding: utf-8 -*-
import os
import pytest
from storyrepo import state as st
from storyrepo.context import assemble_context, budget_check
from conftest import add_chapter, write_file

OUTLINE = """# 细纲蓝图

| ch | 标题 | 要发生什么 | 硬约束 | 禁区 | 角色 | suspense | foreshadow | twist |
|----|------|-----------|--------|------|------|----------|------------|-------|
| 1 | 开局 | 主角被追杀 | 无 | 赵三 | 阿米 | 神秘老者现身 | 断剑 | 老者是仇人 |
| 2 | 惊变 | 阿米出手救人 | 字数4000 | 赵三,钱四 | 阿米,米粒 | 老者身份 | 断剑来历 | 米粒是细作 |
| 3 | 迷雾 | 追查断剑来历 | | | 米粒 | 城主失踪 | | |
| 4 | 夜探 | 夜探城主府 | 不写血腥 | 孙五 | 米粒,阿米 | 密道 | 铜钥匙 | |
| 5 | 秘闻 | 发现密道 | | | 阿米 | 老者的伤 | | |
| 6 | 转折 | 老者身份揭晓 | | | | | | |
| 7 | 变局 | 老者的计划 | | | | | | |
"""


def merged_state(book, *chs):
    s = st.load_state(book)
    for n in chs:
        f = [x for x in st.chapter_files(book) if st.chapter_num(x) == n][0]
        st.merge_chapter_facts(s, n, st.frontmatter(os.path.join(book, "定稿", "正文", f)))
    return s


class TestAssembleContext:
    def test_normal(self, book):
        add_chapter(book, 1, prose="第一章第一段。\n\n第一章结尾段。", summary="摘要一")
        add_chapter(book, 2, prose="第二章内容。\n\n他转身离去。——", summary="摘要二")
        add_chapter(book, 3, prose="第三章内容。\n\n第三章结尾段。\n\n——本章完——", summary="摘要三")
        write_file(book, "大纲/细纲蓝图.md", OUTLINE)
        write_file(book, "定稿/设定/角色/米粒.md", "米粒,神秘少女。\n" * 20)
        write_file(book, "定稿/设定/角色/阿米.md", "阿米,隐世剑客。\n" * 20)

        ctx = assemble_context(book, st.load_state(book), 4)
        # 末段去横幅:ch2 尾部 —— 剥掉;ch3 末段为横幅 → 取上一段
        assert ctx["recent_endings"] == ["第一章结尾段。", "他转身离去。", "第三章结尾段。"]
        assert all(len(e) <= 800 for e in ctx["recent_endings"])
        assert "摘要一" in ctx["summary_chain"] and "摘要三" in ctx["summary_chain"]
        assert len(ctx["summary_chain"]) <= 1000
        # 细纲行角色列优先
        assert ctx["entity_cards"][0].startswith("【米粒】")
        assert "隐世剑客" in ctx["entity_cards"][1]
        # ch+1 行注入(goal + suspense 合并),截 150 字
        assert "发现密道" in ctx["next_chapter_injection"]
        assert "老者的伤" in ctx["next_chapter_injection"]
        assert len(ctx["next_chapter_injection"]) <= 150
        assert 0 < ctx["budget_kb"] < 8
        assert budget_check(ctx) is True

    def test_no_outline_falls_back_to_entity_states(self, book):
        add_chapter(book, 1, prose="甲", entities_new="阿米,米粒,赵六")
        s = merged_state(book, 1)
        write_file(book, "定稿/设定/角色/阿米.md", "阿米,剑客。")
        write_file(book, "定稿/设定/角色/米粒.md", "米粒,少女。")

        ctx = assemble_context(book, s, 2)
        assert ctx["next_chapter_injection"] == ""            # 无细纲 → 无注入
        assert len(ctx["entity_cards"]) == 3                  # entity_states 前 3
        assert ctx["entity_cards"][0].startswith("【阿米】")
        assert "角色卡缺失" in ctx["entity_cards"][2]         # 赵六无角色卡 → 占位
        assert budget_check(ctx) is True

    def test_over_budget(self, book):
        for n in range(1, 6):
            add_chapter(book, n, prose="字" * 850, summary="摘" * 200,
                        entities_new="阿米,米粒,赵六" if n == 1 else "")
        s = merged_state(book, 1, 2, 3, 4, 5)
        for name in ("阿米", "米粒", "赵六"):
            write_file(book, "定稿/设定/角色/%s.md" % name, "卡" * 450)
        write_file(book, "大纲/细纲蓝图.md",
                   "| ch | 要发生什么 | 角色 | suspense |\n"
                   "|----|-----------|------|----------|\n"
                   "| 5 | 第五幕 | 阿米 | 注 |\n"
                   "| 6 | 第六幕 | | |\n"
                   "| 7 | 第七幕 | | 长注入文本" + "注" * 200 + " |\n")

        ctx = assemble_context(book, s, 6)
        # 三路近满:3×800 字结尾 + 1000 字摘要链 + 3×400 字角色卡 + 150 字注入 → 远超 8KB
        assert ctx["budget_kb"] > 8
        assert budget_check(ctx) is False

    def test_first_chapter_empty(self, book):
        ctx = assemble_context(book, st.load_state(book), 1)
        assert ctx["recent_endings"] == []
        assert ctx["summary_chain"] == ""
        assert ctx["entity_cards"] == []                      # 无细纲无实体
        assert ctx["next_chapter_injection"] == ""
        assert budget_check(ctx) is True

    def test_missing_summary_file_skipped(self, book):
        add_chapter(book, 1, prose="甲", summary="摘要一")
        os.remove(os.path.join(book, "定稿", "记忆", "章摘要", "001.md"))
        ctx = assemble_context(book, st.load_state(book), 2)
        assert ctx["summary_chain"] == ""
        assert ctx["recent_endings"] == ["甲"]

    def test_banner_only_ending_becomes_empty(self, book):
        add_chapter(book, 1, prose="正文。\n\n——本章完——")
        ctx = assemble_context(book, st.load_state(book), 2)
        assert ctx["recent_endings"] == ["正文。"]
