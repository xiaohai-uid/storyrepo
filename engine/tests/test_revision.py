# -*- coding: utf-8 -*-
import os
from conftest import add_chapter
from storyrepo import state as st
from storyrepo import revision as rev


def merge_all(root, s):
    for f in st.chapter_files(root):
        n = st.chapter_num(f)
        st.merge_chapter_facts(s, n, st.frontmatter(os.path.join(root, "定稿", "正文", f)))
    return s


def chapter_path(root, n):
    return os.path.join(root, "定稿", "正文",
                        [f for f in st.chapter_files(root) if st.chapter_num(f) == n][0])


def rewrite_fm(root, n, drop_keys):
    fp = chapter_path(root, n)
    fm = st.frontmatter(fp)
    for k in drop_keys:
        fm.pop(k, None)
    head = "---\n" + "\n".join("%s: %s" % (k, v) for k, v in fm.items()) + "\n---\n\n"
    with open(fp, "w", encoding="utf-8") as f:
        f.write(head + st.body(fp))


class TestCascadeRevision:
    def test_conflict_refuses_and_keeps_state(self, book):
        add_chapter(book, 1, prose="甲")
        s = st.load_state(book)
        r = rev.cascade_revision(book, s, 1, st.revision(s) + 5)
        assert r["ok"] is False and r["conflict"] is True
        assert st.revision(st.load_state(book)) == 1      # 状态未被写
        assert "期望修订号" in r["notes"][0]

    def test_ok_replays_and_bumps(self, book):
        add_chapter(book, 1, prose="甲", title="开局", promises_new="P-001")
        add_chapter(book, 2, prose="乙", promises_advanced="P-001")
        s = merge_all(book, st.load_state(book))
        st.save_state(book, s)
        assert s["promises"]["P-001"]["adv_ch"] == 2
        r = rev.cascade_revision(book, s, 1, 1)
        assert r["ok"] is True and r["conflict"] is False
        s2 = st.load_state(book)
        assert st.revision(s2) == 2
        assert s2["chapters"]["2"]["title"] == "第2章"
        assert s2["promises"]["P-001"]["adv_ch"] == 2
        assert st.revision(s) == 2                        # 调用方引用同步为新状态

    def test_impact_scan_after_rewrite(self, book):
        add_chapter(book, 1, prose="甲", promises_new="P-001", gaps_new="S-001")
        add_chapter(book, 2, prose="乙", promises_advanced="P-001")
        add_chapter(book, 3, prose="丙", promises_done="P-001")
        s = merge_all(book, st.load_state(book))
        st.save_state(book, s)
        assert s["promises"]["P-001"]["done_ch"] == 3
        # 回炉第 2 章:不再推进 P-001;第 3 章仍引用 P-001(应被 impact 扫描命中)
        rewrite_fm(book, 2, ["promises_advanced"])
        r = rev.cascade_revision(book, s, 2, 1)
        assert r["ok"] is True
        s2 = st.load_state(book)
        assert s2["promises"]["P-001"]["adv_ch"] == 1        # 推进被重放回滚
        assert any("第3章" in x and "P-001" in x for x in r["impact"])
        assert not any("S-001" in x for x in r["impact"])      # 未变项不误报

    def test_timeline_three_track_preserved(self, book):
        add_chapter(book, 1, prose="甲", summary="第一章小结")
        s = st.load_state(book)
        s["timeline"] = [{"ch": 1, "event": "读者已见", "kind": "reveal"},
                         {"ch": 1, "event": "作者独知", "kind": "private"}]
        r = rev.cascade_revision(book, s, 1, 1)
        assert r["ok"] is True
        s2 = st.load_state(book)
        kinds = [e["kind"] for e in s2["timeline"]]
        assert kinds.count("fact") == 1
        assert "reveal" in kinds and "private" in kinds
        assert any(e["event"] == "第一章小结" for e in s2["timeline"])

    def test_empty_book(self, book):
        s = st.load_state(book)
        r = rev.cascade_revision(book, s, 1, 1)
        assert r["ok"] is True and r["conflict"] is False
        assert r["impact"] == []
        s2 = st.load_state(book)
        assert st.revision(s2) == 2
        assert s2["chapters"] == {}
        assert s2["promises"] == {}
