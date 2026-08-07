# -*- coding: utf-8 -*-
"""CLI 层测试(评审 M5 补课):main() 直接调用,覆盖 commit 幂等、check、revision、损坏状态。"""
import os, json
from storyrepo.cli import main
from conftest import make_book, add_chapter
from storyrepo import state as st


def run(*argv):
    return main(list(argv))


class TestCLI:
    def test_init_and_status(self, tmp_path):
        root = make_book(str(tmp_path / "书"))
        assert run("init", "--root", root) == 0
        assert run("status", "--root", root) == 0

    def test_commit_then_reject_double(self, tmp_path):
        root = make_book(str(tmp_path / "书"), minw=100)
        add_chapter(root, 1, prose="甲。", promises_new="P-001", entities_new="阿米")
        with open(os.path.join(root, "定稿", "设定", "名册.md"), "w", encoding="utf-8") as f:
            f.write("| 阿米 | 001 | 主角 |\n")
        assert run("commit", "--root", root, "--chapter", "1") == 0
        # M1:重复 commit 应被拒绝
        assert run("commit", "--root", root, "--chapter", "1") == 1
        s = st.load_state(root)
        facts = [e for e in s["timeline"] if e.get("ch") == 1]
        assert len(facts) == 1  # 时间线未被污染

    def test_commit_gate_blocks_placeholder(self, tmp_path):
        root = make_book(str(tmp_path / "书"), minw=100)
        add_chapter(root, 1, prose="这里有个TODO占位。", entities_new="阿米")
        # precommit 会因占位符 fail → commit 被 gate 阻断(无 --force)
        assert run("commit", "--root", root, "--chapter", "1") == 1
        # --force 可强行提交(流程纪律由作者掌握)
        assert run("commit", "--root", root, "--chapter", "1", "--force") == 0

    def test_check_passes_after_commit(self, tmp_path):
        root = make_book(str(tmp_path / "书"))
        add_chapter(root, 1, prose="甲。", entities_new="阿米")
        run("commit", "--root", root, "--chapter", "1")
        assert run("check", "--root", root) == 0

    def test_corrupt_state_friendly_error(self, tmp_path):
        root = make_book(str(tmp_path / "书"))
        p = st.state_path(root)
        with open(p, "w", encoding="utf-8") as f:
            f.write("{broken json")
        # 不裸崩:doctor/status 应给出中文救援提示(或可恢复)
        assert run("status", "--root", root) == 1

    def test_doctor_negative_cases(self, tmp_path):
        root = make_book(str(tmp_path / "书"), minw=100)
        add_chapter(root, 1, prose="甲。", entities_new="阿米")  # 未登记名册 → 应 fail
        assert run("doctor", "--root", root, "--stage", "precommit", "--chapter", "1") == 1
        # 修复后通过
        with open(os.path.join(root, "定稿", "设定", "名册.md"), "w", encoding="utf-8") as f:
            f.write("| 阿米 | 001 | 主角 |\n")
        assert run("doctor", "--root", root, "--stage", "precommit", "--chapter", "1") == 0


class TestRevisionOrder:
    def test_timeline_order_preserved(self, tmp_path):
        """评审 M4:重放后非 fact 事件保持 (ch, 原序) 交错,不落到末尾。"""
        root = make_book(str(tmp_path / "书"))
        add_chapter(root, 1, prose="a。", summary="s1")
        add_chapter(root, 2, prose="b。", summary="s2")
        add_chapter(root, 3, prose="c。", summary="s3")
        s = st.load_state(root)
        for n in (1, 2, 3):
            f = [x for x in st.chapter_files(root) if st.chapter_num(x) == n][0]
            st.merge_chapter_facts(s, n, st.frontmatter(os.path.join(root, "定稿", "正文", f)), "s%d" % n)
        # 手工插入一个 ch2 的 private 事件(三轨之一)
        s["timeline"].append({"ch": 2, "event": "私注", "kind": "private"})
        st.save_state(root, s)
        from storyrepo.revision import _replay
        fresh = _replay(root, s)
        kinds = [(e.get("ch"), e.get("kind")) for e in fresh["timeline"]]
        # ch2 private 必须在 ch2 fact 之后、ch3 fact 之前
        idx2f = kinds.index((2, "fact")); idx2p = kinds.index((2, "private")); idx3f = kinds.index((3, "fact"))
        assert idx2f < idx2p < idx3f

    def test_unknown_top_level_keys_preserved(self, tmp_path):
        root = make_book(str(tmp_path / "书"))
        add_chapter(root, 1, prose="a。", summary="s1")
        s = st.load_state(root)
        s["custom_note"] = {"x": 1}
        st.save_state(root, s)
        from storyrepo.revision import _replay
        fresh = _replay(root, s)
        assert fresh.get("custom_note") == {"x": 1}


class TestBatchParsing:
    """v3 评审修复回归:--chapters 解析边界。"""

    def test_reversed_range_rejected(self, tmp_path):
        root = make_book(str(tmp_path / "书"))
        assert run("batch", "--root", root, "create", "--chapters", "35-31") == 2

    def test_empty_rejected(self, tmp_path):
        root = make_book(str(tmp_path / "书"))
        assert run("batch", "--root", root, "create", "--chapters", "") == 2

    def test_mixed_rejected(self, tmp_path):
        root = make_book(str(tmp_path / "书"))
        assert run("batch", "--root", root, "create", "--chapters", "31,33-34,xx") == 2

    def test_parse_ok(self, tmp_path):
        root = make_book(str(tmp_path / "书"))
        assert run("batch", "--root", root, "create", "--chapters", "31-33") == 0
        import glob
        plans = glob.glob(os.path.join(root, "工作区", "批次-*.json"))
        assert len(plans) == 1
        import json
        plan = json.load(open(plans[0], encoding="utf-8"))
        assert [c["chapter"] for c in plan["chapters"]] == [31, 32, 33]
        assert plan.get("expected_revision") == 1
