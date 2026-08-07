# -*- coding: utf-8 -*-
import os
from conftest import add_chapter, make_book
from storyrepo import models, report, review as rv, state as st


class TestAuthorReport:
    def test_empty_book(self, book):
        t = report.author_report(book, "prewrite")
        assert "最新章: 0" in t
        assert "活跃承诺: 0" in t
        assert "未曝光信息差: 0" in t
        assert "下一步" in t

    def test_full_state(self, tmp_path):
        # 用低字数下限的书仓,构造一节能通过 postcommit 机检的章
        root = make_book(str(tmp_path / "长篇"), total=120, minw=100)
        prose = "\n\n".join([
            "晨光落在青石板上。", "他推开吱呀的木门。", "桌上茶盏还冒着热气。",
            "巷口传来叫卖声。", "她低头缝补旧衣。", "雨点敲打着窗棂。",
            "少年握紧了拳头。", "老者捋了捋胡须。", "案上摊开一卷地图。",
            "远处钟声悠扬传来。", "风穿过空荡的回廊。", "他蘸墨写下首行。",
            "灯花噼啪爆了一声。", "猫儿蜷在灶台边。", "她提起裙摆跨过门槛。",
            "酒旗在风中招展。", "他翻过泛黄的书页。", "树影婆娑落在院墙。",
            "河水缓缓流过石桥。", "他掩上门,长叹一声。",
        ]) + "\n\n"
        add_chapter(root, 1, prose=prose, summary="第一章",
                    promises_new="P-001", gaps_new="S-001")
        s = st.load_state(root)
        f = [x for x in st.chapter_files(root) if st.chapter_num(x) == 1][0]
        st.merge_chapter_facts(s, 1, st.frontmatter(os.path.join(root, "定稿", "正文", f)))
        st.save_state(root, s)
        from storyrepo import views
        views.write_views(root, s)      # 真实流程:commit 后必重建派生视图
        rv.save_review(root, 1, [models.ReviewIssue("low", "pacing", "x", "略拖")])
        t = report.author_report(root, "postcommit", ch=1)
        assert "最新章: 1" in t
        assert "活跃承诺: 1" in t
        assert "未曝光信息差: 1" in t
        assert ("%d 字" % st.hanzi(prose)) in t
        assert "已结算" in t
        assert "机检(postcommit)" in t and "放行" in t
        assert "结转" in t

    def test_blocking_advice(self, book):
        add_chapter(book, 1, prose="甲")
        rv.save_review(book, 1, [models.ReviewIssue("critical", "logic", "第1段", "设定冲突")])
        t = report.author_report(book, "review", ch=1)
        assert "blocking" in t
        assert "定点修复" in t

    def test_gate_fail_advice(self, book):
        # 默认夹具(每章下限 3000 字)下短正文必过不了机检 → 报告给出修复建议
        add_chapter(book, 1, prose="甲")
        t = report.author_report(book, "precommit", ch=1)
        assert "机检" in t
        assert "未放行" in t
        assert "机检未放行" in t

    def test_unknown_stage_ok(self, book):
        t = report.author_report(book, "whatever")
        assert t.strip() != ""
