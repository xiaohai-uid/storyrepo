# -*- coding: utf-8 -*-
import os
import pytest
from storyrepo import state as st
from storyrepo.brief import build_brief
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
"""


def merged_state(book, *chs):
    s = st.load_state(book)
    for n in chs:
        f = [x for x in st.chapter_files(book) if st.chapter_num(x) == n][0]
        st.merge_chapter_facts(s, n, st.frontmatter(os.path.join(book, "定稿", "正文", f)))
    return s


class TestBuildBrief:
    def test_normal_five_sections(self, book):
        add_chapter(book, 1, prose="第一章第一段。\n\n第一章结尾段。", summary="摘要一",
                    gaps_new="S-001")
        add_chapter(book, 2, prose="第二章内容。\n\n第二章结尾段。", summary="摘要二")
        add_chapter(book, 3, prose="第三章内容。\n\n第三章结尾段。\n\n——本章完——", summary="摘要三")
        write_file(book, "大纲/细纲蓝图.md", OUTLINE)
        write_file(book, "定稿/设定/角色/阿米.md",
                   "阿米是隐世剑客。\n状态:重伤未愈。\n驱动:为师父复仇。\n"
                   "作用:主角的助力。\n说话倾向:寡言。\n")
        write_file(book, "定稿/设定/角色/米粒.md", "米粒,神秘少女。")
        write_file(book, "文风/风格宪法.md", "简洁有力,短句为主,少用成语。")

        b = build_brief(book, merged_state(book, 1, 2, 3), 4)
        assert b.startswith("# 第4章 写作任务书(测试书)")
        # 五段齐全
        for sec in ("一、开篇委托", "二、这章的故事", "三、这章的人物",
                    "四、怎么写更顺", "五、收在哪里"):
            assert sec in b
        # ① 开篇委托
        assert "书名:测试书" in b
        assert "章号:4" in b
        assert "标题:夜探" in b
        assert "夜探城主府" in b
        # ② 这章的故事
        assert "摘要一" in b and "摘要三" in b
        assert "必覆盖:不写血腥" in b
        assert "禁区:S-001、孙五" in b
        assert "【米粒】" in b and "【阿米】" in b
        # ③ 这章的人物(从角色卡提炼状态/驱动/作用/说话)
        assert "驱动:为师父复仇。" in b
        assert "说话倾向:寡言。" in b
        # ④ 怎么写更顺
        assert "简洁有力" in b
        assert "老者的伤" in b
        # ⑤ 收在哪里(上章结尾复述,横幅已去)
        assert "第三章结尾段。" in b
        assert "尚无上章" not in b

    def test_explicit_contract_and_context(self, book):
        c = {"goal": "定制目标", "hard_constraints": ["约束A"], "forbidden": ["禁B"],
             "foreshadow_todo": ["P-001"], "ending_requirement": "结尾埋伏笔X", "sources": {}}
        ctx = {"recent_endings": ["上章结尾语"], "summary_chain": "定制摘要",
               "entity_cards": ["【阿米】状态:冷静"], "next_chapter_injection": "注入Y",
               "budget_kb": 1.0}
        b = build_brief(book, st.load_state(book), 3, contract=c, context=ctx)
        assert "定制目标" in b and "约束A" in b and "禁B" in b
        assert "结尾埋伏笔X" in b
        assert "定制摘要" in b
        assert "上章结尾语" in b
        assert "状态:冷静" in b
        assert "无风格宪法文件" in b
        assert "尚无上章" not in b

    def test_no_outline_first_chapter(self, book):
        add_chapter(book, 1, prose="甲", entities_new="阿米")
        b = build_brief(book, merged_state(book, 1), 1)
        assert "(无细纲,依 大纲/总纲.md 一句话)" in b
        assert "暂无前文摘要" in b
        assert "尚无上章(本书开篇)" in b
        assert "角色卡缺失" in b                              # 无角色卡 → 占位提示
        assert "标题:第1章" in b

    def test_outline_row_missing_placeholder(self, book):
        write_file(book, "大纲/细纲蓝图.md", OUTLINE)
        b = build_brief(book, st.load_state(book), 9)
        assert "(细纲蓝图无第9章行)" in b

    def test_style_file_missing(self, book):
        add_chapter(book, 1, prose="甲")
        b = build_brief(book, merged_state(book, 1), 2)
        assert "无风格宪法文件" in b
