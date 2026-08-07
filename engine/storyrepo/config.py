# -*- coding: utf-8 -*-
"""book.yaml 配置加载。平铺 KV(front-matter 风格),数值字段转 int。"""
import os, re
from typing import Dict

DEFAULTS = {
    "name": "未命名",
    "total_chapters": 330,
    "min_words_per_chapter": 3000,
    "max_words_per_chapter": 3800,   # 默认 min+800,可由配置覆盖
    "target_words": 990000,
}

def book_path(root: str) -> str:
    return os.path.join(root, "book.yaml")

def load_config(root: str) -> Dict:
    """读 book.yaml,缺失字段补默认;文件缺失抛 FileNotFoundError。"""
    p = book_path(root)
    if not os.path.exists(p):
        raise FileNotFoundError("缺 book.yaml(先跑 storyrepo init 或 init-book.sh): %s" % p)
    cfg = dict(DEFAULTS)
    with open(p, encoding="utf-8") as f:
        t = f.read()
    if t.startswith("---"):
        t = t.split("---", 2)[1]
    for line in t.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        k, v = line.split(":", 1)
        k, v = k.strip(), v.strip()
        if not k:
            continue
        v = v.strip("\"'")
        m = re.fullmatch(r"-?\d+", v)
        cfg[k] = int(v) if m else v
    if cfg.get("max_words_per_chapter", 0) < cfg.get("min_words_per_chapter", 0):
        cfg["max_words_per_chapter"] = cfg["min_words_per_chapter"] + 800
    return cfg
