# -*- coding: utf-8 -*-
"""批次模式测试:假 worker(直接调用写章函数)模拟子代理产物,不起真子代理。
覆盖:计划结构 / 合并幂等 / 按章序 / 单章失败隔离 / 未返回章 / 与串行等价。
机制:规格「批次模式」;断言用已知良好字面量,不测内部实现。"""
import os

import pytest

from storyrepo import batch, state as st
from conftest import make_book, add_chapter, write_file


def fake_worker(root, ch, **kw):
    """假 worker:直接调用写章函数产出 正文+front matter(即子代理产物)。"""
    return add_chapter(root, ch, **kw)


def hand_plan(root, chs):
    """手工构造计划 dict(模拟 cli 从 JSON 加载;chapters 可不按升序)。"""
    s = st.load_state(root)
    return {
        "book": s.get("book", ""), "mode": batch.MODE, "created": "t",
        "chapters": [{
            "chapter": ch,
            "contract": {"goal": "目标%d" % ch},
            "output_path": os.path.join(root, "定稿", "正文", "%03d-*.md" % ch),
            "status": "pending",
        } for ch in chs],
    }


class TestPlan:
    def test_plan_structure_sorted_deduped(self, tmp_path):
        root = make_book(str(tmp_path / "书"))
        write_file(root, "大纲/细纲蓝图.md",
                   "| ch | 标题 | 要发生什么 | 硬约束 |\n"
                   "| --- | --- | --- | --- |\n"
                   "| 1 | 开局 | 主角醒来 | 不写梦境 |\n"
                   "| 2 | 相遇 | 遇见米粒 |  |\n"
                   "| 3 | 冲突 | 与赵三对峙 |  |\n")
        plan = batch.create_batch_plan(root, [3, 1, 2, 1])
        assert plan["mode"] == "subagent-parallel"
        chs = plan["chapters"]
        assert [it["chapter"] for it in chs] == [1, 2, 3]       # 升序去重
        assert [it["status"] for it in chs] == ["pending"] * 3
        for it in chs:
            assert set(it) == {"chapter", "contract", "output_path", "status"}
            assert set(it["contract"]) == {"goal", "hard_constraints", "forbidden",
                                           "foreshadow_todo", "ending_requirement", "sources"}
            assert it["output_path"].endswith(
                os.path.join("定稿", "正文", "%03d-*.md" % it["chapter"]))
        assert chs[0]["contract"]["goal"] == "主角醒来"          # 合同来自细纲蓝图
        assert chs[0]["contract"]["hard_constraints"] == ["不写梦境"]


class TestMergeOrder:
    def test_merge_walks_plan_in_chapter_order(self, tmp_path):
        root = make_book(str(tmp_path / "书"), minw=100)
        # 假 worker 产出;计划按 [2,1] 乱序,merge 须按章序 1→2 入账
        fake_worker(root, 1, prose="甲。", promises_new="P-001", summary="开局")
        fake_worker(root, 2, prose="乙。", promises_advanced="P-001", summary="推进")
        plan = hand_plan(root, [2, 1])
        r = batch.merge_batch(root, plan, {1: True, 2: True})
        assert r["merged"] == [1, 2]
        assert r["rejected"] == [] and r["skipped"] == [] and r["ok"] is True
        assert r["warns"] == {1: [], 2: []}                     # 先 1 后 2,推进无未知承诺警告
        s = st.load_state(root)
        assert [e["ch"] for e in s["timeline"]] == [1, 2]       # 时间线按章序
        assert s["promises"]["P-001"]["open_ch"] == 1
        assert s["promises"]["P-001"]["adv_ch"] == 2            # 乱序计划下仍先埋后推
        assert s["state_revision"] == 3                         # 1 初始 + 2 次 bump


class TestMergeIdempotent:
    def test_double_merge_rejected_by_guard(self, tmp_path):
        root = make_book(str(tmp_path / "书"), minw=100)
        for n in (1, 2, 3):
            fake_worker(root, n, prose="甲%d。" % n)
        plan = hand_plan(root, [1, 2, 3])
        r = batch.merge_batch(root, plan, {1: True, 2: True, 3: True})
        assert r["merged"] == [1, 2, 3] and r["revision"] == 4
        # M1:重复 merge 同一计划 → 幂等守卫拒绝并报错
        with pytest.raises(ValueError) as e:
            batch.merge_batch(root, plan, {1: True, 2: True, 3: True})
        assert "已提交" in str(e.value)
        s = st.load_state(root)
        assert s["state_revision"] == 4                         # 未被二次 bump
        assert len(s["timeline"]) == 3                          # 时间线未被污染


class TestFailureIsolation:
    def test_single_doctor_fail_marks_rejected_only(self, tmp_path):
        root = make_book(str(tmp_path / "书"), minw=100)
        # 前置:1-2 章经既有 commit 路径串行入账
        from storyrepo.cli import main
        for n in (1, 2):
            fake_worker(root, n, prose="先%d。" % n)
            assert main(["commit", "--root", root, "--chapter", str(n)]) == 0
        # 假 worker 产出 3-5;第 5 章含占位符 → 机检必败
        fake_worker(root, 3, prose="丙。")
        fake_worker(root, 4, prose="丁。")
        fake_worker(root, 5, prose="戊。这里还有个TODO占位。")
        plan = hand_plan(root, [3, 4, 5])
        r = batch.merge_batch(root, plan, {3: True, 4: True, 5: True})
        assert r["merged"] == [3, 4]                            # 其余章正常入账
        assert len(r["rejected"]) == 1 and r["rejected"][0]["chapter"] == 5
        assert any("占位符" in f for f in r["rejected"][0]["fails"])
        assert r["skipped"] == [] and r["ok"] is False
        s = st.load_state(root)
        assert sorted(int(k) for k in s["chapters"]) == [1, 2, 3, 4]   # 第 5 章未入账
        assert not any(e["ch"] == 5 for e in s["timeline"])
        # 修复后另建计划补入账(同计划重跑会被幂等守卫拒绝,见幂等测试)
        fake_worker(root, 5, prose="戊。")
        r2 = batch.merge_batch(root, hand_plan(root, [5]), {5: True})
        assert r2["merged"] == [5] and r2["ok"] is True
        assert str(5) in st.load_state(root)["chapters"]


class TestWorkerReturn:
    def test_unreturned_chapter_skipped(self, tmp_path):
        root = make_book(str(tmp_path / "书"), minw=100)
        fake_worker(root, 1, prose="甲。")
        fake_worker(root, 2, prose="乙。")   # 文件在,但 worker 未返回
        plan = hand_plan(root, [1, 2])
        r = batch.merge_batch(root, plan, {1: True})
        assert r["merged"] == [1] and r["skipped"] == [2] and r["ok"] is False
        assert sorted(int(k) for k in st.load_state(root)["chapters"]) == [1]

    def test_done_but_no_file_rejected(self, tmp_path):
        root = make_book(str(tmp_path / "书"), minw=100)
        fake_worker(root, 1, prose="甲。")
        plan = hand_plan(root, [1, 2])       # 第 2 章声称完成但无正文文件
        r = batch.merge_batch(root, plan, {1: True, 2: True})
        assert r["merged"] == [1]
        assert len(r["rejected"]) == 1 and r["rejected"][0]["chapter"] == 2
        assert "缺正文" in r["rejected"][0]["reason"]


class TestSerialEquivalence:
    def test_revision_and_timeline_match_serial(self, tmp_path):
        a = make_book(str(tmp_path / "串行"), minw=100)
        b = make_book(str(tmp_path / "批次"), minw=100)
        from storyrepo.cli import main
        for n in (1, 2, 3):
            add_chapter(a, n, prose="第%d章内容。" % n,
                        promises_new=("P-001" if n == 1 else ""),
                        summary="摘要%d" % n)
            assert main(["commit", "--root", a, "--chapter", str(n)]) == 0
        for n in (1, 2, 3):
            add_chapter(b, n, prose="第%d章内容。" % n,
                        promises_new=("P-001" if n == 1 else ""),
                        summary="摘要%d" % n)
        r = batch.merge_batch(b, hand_plan(b, [1, 2, 3]), {1: True, 2: True, 3: True})
        assert r["merged"] == [1, 2, 3]
        sa, sb = st.load_state(a), st.load_state(b)
        assert sb["state_revision"] == sa["state_revision"]     # 修订号等价
        assert sb["timeline"] == sa["timeline"]                 # 时间线等价
        assert sb["imported_through_chapter"] == sa["imported_through_chapter"]
        assert sorted(sb["chapters"]) == sorted(sa["chapters"])
