# -*- coding: utf-8 -*-
"""模块 2 视图契约测试:card7 七栏/12KB 上限、write_views 全量重建、幂等与缺字段容错。"""
import os

from storyrepo import state as st, views
from conftest import make_book, add_chapter, write_file


def _merge(root, s, ch, summary=None):
    f = [x for x in st.chapter_files(root) if st.chapter_num(x) == ch][0]
    fm = st.frontmatter(os.path.join(root, "定稿", "正文", f))
    st.merge_chapter_facts(s, ch, fm, summary=fm.get("summary", ""))


def _populated(root, n=3):
    """3 章标准书:2 伏笔、2 信息差、2 实体、私密/揭示事件各一。"""
    add_chapter(root, 1, title="开局", prose="第一行。\n\n第二行。\n\n他笑了笑。",
                promises_new="P-001, P-002", gaps_new="S-001", entities_new="阿米,米粒",
                summary="阿米登场", must_cover="阿米,米粒", forbidden="赵三")
    add_chapter(root, 2, title="夜行", prose="风声。\n\n——本章完——\n\n米粒出发了。",
                promises_advanced="P-001", gaps_new="S-002", entities_new="米粒",
                summary="米粒夜行")
    add_chapter(root, 3, title="追兵", prose="马蹄声近。\n\n追兵到了。",
                promises_done="P-002", gaps_revealed="S-001", summary="追兵围城")
    s = st.load_state(root)
    for n in range(1, n + 1):
        _merge(root, s, n)
    s["timeline"].append({"ch": 2, "event": "作者私注:米粒的真实身份", "kind": "private"})
    s["timeline"].append({"ch": 3, "event": "追兵头领是故人", "kind": "reveal"})
    s["promises"]["P-001"]["note"] = "身世之谜"
    s["entity_states"]["阿米"]["where"] = "城门口"
    s["entity_states"]["阿米"]["state"] = "重伤"
    st.save_state(root, s)
    return root


class TestCard7:
    def test_fixed_title_and_section_order(self, book):
        card = views.card7(book, st.load_state(book))
        assert card.startswith("# 续写状态卡(7 栏)")
        idx = [card.find("## %d." % i) for i in range(1, 8)]
        assert all(i >= 0 for i in idx)
        assert idx == sorted(idx)          # 7 栏固定顺序

    def test_progress_numbers(self, book):
        root = _populated(book)
        card = views.card7(root, st.load_state(root))
        assert "最新章: 3 / 计划: 330" in card
        assert "活跃承诺: 1" in card       # P-002 已回收
        assert "未曝光信息差: 1" in card   # S-002 未曝光

    def test_promise_and_gap_lines(self, book):
        root = _populated(book)
        card = views.card7(root, st.load_state(root))
        assert "- P-001 身世之谜" in card
        assert "- P-002" not in card.split("## 3. 活跃伏笔")[1]   # 已回收,不列
        assert "- S-002" in card
        assert "S-001" not in card.split("## 6. 未曝光信息差")[1]

    def test_entity_lines(self, book):
        root = _populated(book)
        card = views.card7(root, st.load_state(root))
        assert "- 阿米: 首现第1章 城门口" in card
        assert "- 米粒: 首现第1章" in card   # 无位置则不尾缀

    def test_recent_endings_skip_banner_and_truncate(self, book):
        root = _populated(book)
        card = views.card7(root, st.load_state(root))
        assert "- 第2章: 米粒出发了。" in card   # ——本章完—— 横幅被跳过
        assert "- 第3章: 追兵到了。" in card
        long_end = "句" * 300
        add_chapter(root, 4, prose="前段。\n\n" + long_end, summary="长尾章")
        s = st.load_state(root)
        _merge(root, s, 4)
        card = views.card7(root, s)
        seg = card.split("## 5. 最近章节结尾", 1)[1].split("## 6.", 1)[0]
        assert "句" * 150 in seg
        assert "句" * 151 not in seg

    def test_next_contract_line(self, book):
        write_file(book, "大纲/细纲蓝图.md",
                   "# 细纲蓝图\n\n- [x] 第1章: 开局\n- [ ] 第2章: 米粒夜行,埋下 S-002\n- [ ] 第3章: 追兵\n")
        card = views.card7(book, st.load_state(book))
        assert "米粒夜行,埋下 S-002" in card
        write_file(book, "大纲/细纲蓝图.md", "- [ ] %s\n" % ("长" * 300))
        card = views.card7(book, st.load_state(book))
        seg = card.split("## 2. 下一章合同", 1)[1].split("## 3.", 1)[0]
        assert "长" * 120 in seg
        assert "长" * 121 not in seg

    def test_no_outline_placeholder(self, book):
        card = views.card7(book, st.load_state(book))
        assert "无未勾选细纲" in card

    def test_empty_book(self, book):
        card = views.card7(book, st.load_state(book))
        assert "最新章: 0 / 计划: 330" in card
        assert "（无正文,待首章落笔）" in card
        assert "（无）" in card
        assert "风格锚点" in card

    def test_active_promises_capped_at_10(self, book):
        add_chapter(book, 1, prose="x",
                    promises_new=",".join("P-%03d" % i for i in range(1, 13)))
        s = st.load_state(book)
        _merge(book, s, 1)
        card = views.card7(book, s)
        assert "- P-001" in card and "- P-010" in card
        assert "- P-011" not in card and "- P-012" not in card

    def test_oversize_card_truncated_to_12kb(self, book):
        add_chapter(book, 1, prose="x",
                    promises_new=",".join("P-%03d" % i for i in range(10)))
        s = st.load_state(book)
        _merge(book, s, 1)
        for pid, v in s["promises"].items():
            v["note"] = "注" * 2000            # 10×6KB,必然超限
        card = views.card7(book, s)
        assert len(card.encode("utf-8")) <= st.MAX_CARD_BYTES == 12288

    def test_card_size_ok(self, book):
        root = _populated(book)
        views.write_views(root, st.load_state(root))
        assert views.card_size_ok(root) is True
        with open(os.path.join(root, "追踪", "上下文.md"), "w", encoding="utf-8") as f:
            f.write("大" * 6000)               # 18KB > 12KB
        assert views.card_size_ok(root) is False
        os.remove(os.path.join(root, "追踪", "上下文.md"))
        assert views.card_size_ok(root) is False


class TestWriteViews:
    def test_all_files_created(self, book):
        root = _populated(book)
        views.write_views(root, st.load_state(root))
        tk = os.path.join(root, "追踪")
        for rel in ("上下文.md", "伏笔.md", "作者真相.md", "读者已知.md", "时间线.md",
                    "角色状态/阿米.md", "角色状态/米粒.md",
                    "逐章记录/ch001.md", "逐章记录/ch002.md", "逐章记录/ch003.md"):
            assert os.path.exists(os.path.join(tk, rel)), rel

    def test_context_equals_card7(self, book):
        root = _populated(book)
        s = st.load_state(root)
        views.write_views(root, s)
        with open(os.path.join(root, "追踪", "上下文.md"), encoding="utf-8") as f:
            assert f.read() == views.card7(root, s)

    def test_vault_table(self, book):
        root = _populated(book)
        views.write_views(root, st.load_state(root))
        with open(os.path.join(root, "追踪", "伏笔.md"), encoding="utf-8") as f:
            t = f.read()
        assert "| P-001 | adv | 1 | 2 |  | 身世之谜 |" in t
        assert "| P-002 | done | 1 | 1 | 3 |  |" in t
        assert "| S-001 | 已曝光 | 1 |  | 3 |  |" in t
        assert "| S-002 | 未曝光 | 2 |  |  |  |" in t

    def test_author_vs_reader_views(self, book):
        root = _populated(book)
        views.write_views(root, st.load_state(root))
        with open(os.path.join(root, "追踪", "作者真相.md"), encoding="utf-8") as f:
            a = f.read()
        with open(os.path.join(root, "追踪", "读者已知.md"), encoding="utf-8") as f:
            r = f.read()
        # 作者真相:全量时间线 + 未曝光信息差
        assert "- 1. 阿米登场" in a
        assert "作者私注:米粒的真实身份" in a
        assert "追兵头领是故人" in a
        assert "- S-002" in a
        assert "S-001" not in a.split("## 未曝光信息差")[1]
        # 读者已知:只 fact/reveal + 已曝光信息差
        assert "作者私注:米粒的真实身份" not in r
        assert "追兵头领是故人" in r
        assert "阿米登场" in r
        assert "- S-001" in r
        assert "S-002" not in r.split("## 已曝光信息差")[1]

    def test_entity_files(self, book):
        root = _populated(book)
        views.write_views(root, st.load_state(root))
        with open(os.path.join(root, "追踪", "角色状态", "阿米.md"), encoding="utf-8") as f:
            t = f.read()
        assert "# 角色状态:阿米" in t
        assert "- 首现章: 1" in t
        assert "- 位置: 城门口" in t
        assert "- 状态: 重伤" in t

    def test_entity_name_sanitized(self, book):
        s = st.load_state(book)
        s["entity_states"]["A/B"] = {"first_ch": 1, "where": "", "state": ""}
        views.write_views(book, s)
        assert os.path.exists(os.path.join(book, "追踪", "角色状态", "A_B.md"))

    def test_chapter_logs_six_fields(self, book):
        root = _populated(book)
        views.write_views(root, st.load_state(root))
        with open(os.path.join(root, "追踪", "逐章记录", "ch001.md"), encoding="utf-8") as f:
            t = f.read()
        assert t.startswith("# 逐章记录:第1章《开局》")
        for field in ("结果:", "角色变化:", "伏笔变化:", "时间与揭示:", "约束:", "下一章承诺:"):
            assert field in t, field
        assert "阿米登场" in t
        assert "首现:阿米(位置:城门口,状态:重伤)" in t
        assert "首现:米粒" in t
        assert "新埋:P-001,P-002" in t and "推进:P-002" in t
        assert "埋设:S-001" in t
        assert "必覆盖:阿米,米粒" in t and "禁区:赵三" in t
        assert "下一章承诺: P-001, P-002, S-001" in t
        with open(os.path.join(root, "追踪", "逐章记录", "ch003.md"), encoding="utf-8") as f:
            t3 = f.read()
        assert "回收:P-002" in t3
        assert "揭示:S-001" in t3
        assert "揭示信息差:S-001" in t3
        assert "追兵头领是故人" in t3          # reveal 事件入时间与揭示
        assert "下一章承诺: 无" in t3

    def test_chapter_log_truncated_to_3072(self, book):
        add_chapter(book, 1, prose="x",
                    entities_new=",".join("角色%d" % i for i in range(80)))
        s = st.load_state(book)
        _merge(book, s, 1)
        for i in range(80):
            s["entity_states"]["角色%d" % i]["state"] = "状态" * 20   # 每行 >120B
        views.write_views(book, s)
        with open(os.path.join(book, "追踪", "逐章记录", "ch001.md"), encoding="utf-8") as f:
            t = f.read()
        assert len(t.encode("utf-8")) <= 3072

    def test_timeline_table_append_only(self, book):
        root = _populated(book)
        views.write_views(root, st.load_state(root))
        with open(os.path.join(root, "追踪", "时间线.md"), encoding="utf-8") as f:
            t = f.read()
        assert "append-only" in t
        assert "| 1 | fact | 阿米登场 |" in t
        assert "| 2 | private | 作者私注:米粒的真实身份 |" in t
        assert "| 3 | reveal | 追兵头领是故人 |" in t

    def test_empty_book(self, book):
        views.write_views(book, st.load_state(book))
        tk = os.path.join(book, "追踪")
        for rel in ("上下文.md", "伏笔.md", "作者真相.md", "读者已知.md", "时间线.md"):
            assert os.path.exists(os.path.join(tk, rel)), rel
        assert os.listdir(os.path.join(tk, "逐章记录")) == []

    def test_idempotent(self, book):
        root = _populated(book)
        views.write_views(root, st.load_state(root))
        with open(os.path.join(root, "追踪", "伏笔.md"), encoding="utf-8") as f:
            before = f.read()
        views.write_views(root, st.load_state(root))   # 重复调用不炸
        with open(os.path.join(root, "追踪", "伏笔.md"), encoding="utf-8") as f:
            assert f.read() == before
        assert views.card_size_ok(root) is True

    def test_missing_fields_tolerant(self, book):
        for s in ({}, {"spec": 1}, {"promises": {}, "timeline": [], "chapters": {}}):
            views.write_views(book, s)               # 缺字段不炸
            assert views.card_size_ok(book) is True
        card = views.card7(book, {})
        assert "最新章: 0" in card
