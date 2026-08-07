# -*- coding: utf-8 -*-
"""pip 安装验证:全新 venv 里真实安装 storyrepo 并冒烟。
网络/无 pip 环境自动 skip(本机系统 Python 无 ensurepip 时,测试自带 --without-pip + get-pip 回退)。"""
import os, shutil, subprocess, sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # engine/
GET_PIP = os.path.join(HERE, "vendor", "get-pip.py")


def _has_pip(py):
    try:
        subprocess.run([py, "-m", "pip", "--version"], capture_output=True, timeout=30, check=True)
        return True
    except Exception:
        return False


def _bootstrap_venv(tmp):
    """建 venv:优先正常 ensurepip;失败则 --without-pip + get-pip.py(需要网络)。"""
    py = shutil.which("python3")
    if not py:
        return None
    v = os.path.join(tmp, "venv")
    r = subprocess.run([py, "-m", "venv", v], capture_output=True, timeout=120)
    if r.returncode != 0:
        r = subprocess.run([py, "-m", "venv", "--without-pip", v], capture_output=True, timeout=120)
        if r.returncode != 0:
            return None
        vpy = os.path.join(v, "bin", "python")
        if not os.path.exists(GET_PIP):
            return None
        r = subprocess.run([vpy, GET_PIP, "-q"], capture_output=True, timeout=300)
        if r.returncode != 0:
            return None
    return v


@pytest.mark.skipif(shutil.which("python3") is None, reason="无 python3")
def test_pip_install_smoke(tmp_path):
    v = _bootstrap_venv(str(tmp_path))
    if v is None:
        pytest.skip("无法建 venv(无 ensurepip 且无 get-pip.py/网络)")
    vpy = os.path.join(v, "bin", "python")
    if not _has_pip(vpy):
        pytest.skip("venv 无 pip")
    # 安装
    r = subprocess.run([vpy, "-m", "pip", "install", "-q", HERE], capture_output=True, timeout=600)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")[-2000:]
    # 冒烟:命令可用
    r = subprocess.run([os.path.join(v, "bin", "storyrepo"), "--help"], capture_output=True, timeout=60)
    assert r.returncode == 0 and b"storyrepo" in r.stdout
    # 冒烟:init 于临时书仓
    book = os.path.join(str(tmp_path), "书")
    os.makedirs(book)
    with open(os.path.join(book, "book.yaml"), "w", encoding="utf-8") as f:
        f.write("---\nname: 冒烟书\ntotal_chapters: 10\nmin_words_per_chapter: 100\n---\n")
    r = subprocess.run([os.path.join(v, "bin", "storyrepo"), "init", "--root", book], capture_output=True, timeout=60)
    assert r.returncode == 0, r.stdout.decode("utf-8", "replace")
    assert os.path.exists(os.path.join(book, "追踪", "_tracking-state.json"))
