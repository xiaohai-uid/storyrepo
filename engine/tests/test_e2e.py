# -*- coding: utf-8 -*-
"""e2e 测试:全生命周期通过 + 人为破坏 → 非零退出。"""
import os
from conftest import make_book
from storyrepo import e2e as e2e_mod


def _run(root):
    try:
        return e2e_mod.run_e2e(root), ""
    except SystemExit as e:
        return 1, str(e)


class TestE2E:
    def test_full_lifecycle_ok(self, tmp_path):
        root = str(tmp_path / "书")
        os.makedirs(root)
        code, msg = _run(root)
        assert code == 0, msg
        # 产物齐全
        assert os.path.exists(os.path.join(root, "追踪", "_tracking-state.json"))
        assert os.path.exists(os.path.join(root, "追踪", "上下文.md"))
        assert os.path.exists(os.path.join(root, "追踪", "伏笔.md"))
        assert os.path.exists(os.path.join(root, "文风", "金句库"))
        assert len(os.listdir(os.path.join(root, "定稿", "正文"))) == 3

    def test_sabotage_todo_blocks(self, tmp_path):
        """人为破坏:先跑通,再破坏 e2e 不会重写的源头(追踪状态 JSON)→ 非零退出。"""
        root = str(tmp_path / "书")
        os.makedirs(root)
        code, msg = _run(root)
        assert code == 0, msg
        sp = os.path.join(root, "追踪", "_tracking-state.json")
        with open(sp, "w", encoding="utf-8") as f:
            f.write("{broken json")
        # 走 CLI 入口(退出码契约在此层)
        from types import SimpleNamespace
        from storyrepo import e2e as e2e_mod
        code = e2e_mod.cli_e2e(SimpleNamespace(root=root))
        assert code != 0, "损坏状态不应通过 e2e"
