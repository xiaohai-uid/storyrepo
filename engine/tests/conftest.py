# -*- coding: utf-8 -*-
"""共享测试夹具:临时书仓构造。所有模块测试都基于它。"""
import os, sys, json

ENGINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ENGINE not in sys.path:
    sys.path.insert(0, ENGINE)

import pytest
from storyrepo import state as st


def make_book(root, total=330, minw=3000, name="测试书"):
    """建标准书仓骨架(目录 + book.yaml + tracking init)。"""
    os.makedirs(root, exist_ok=True)
    for d in ("大纲", "大纲/承诺", "大纲/信息差", "大纲/卷纲", "定稿/正文", "定稿/设定",
              "定稿/设定/角色", "定稿/设定/信息差", "定稿/记忆/章摘要", "文风/金句库",
              "工作区/评审报告"):
        os.makedirs(os.path.join(root, d), exist_ok=True)
    with open(os.path.join(root, "book.yaml"), "w", encoding="utf-8") as f:
        f.write("---\nname: %s\nstatus: writing\ntotal_chapters: %d\nmin_words_per_chapter: %d\nmax_words_per_chapter: %d\n---\n"
                % (name, total, minw, minw + 800))
    st.init_state(root)
    return root


def add_chapter(root, n, title=None, fm_extra=None, prose="", summary=None,
                promises_new="", promises_advanced="", promises_done="",
                gaps_new="", gaps_revealed="", entities_new="", must_cover="", forbidden=""):
    """写一章(正文 + front matter + 章摘要)。返回正文路径。"""
    title = title or "第%d章" % n
    fm = {
        "title": title, "chapter": "%03d" % n, "volume": 1,
        "words": str(len(prose)), "status": "定稿",
        "promises_new": promises_new, "promises_advanced": promises_advanced,
        "promises_done": promises_done, "info_gaps_new": gaps_new,
        "info_gaps_revealed": gaps_revealed, "entities_new": entities_new,
        "must_cover": must_cover, "forbidden": forbidden,
        "summary": summary or (prose[:40] if prose else title),
    }
    if fm_extra:
        fm.update(fm_extra)
    head = "---\n" + "\n".join("%s: %s" % (k, v) for k, v in fm.items()) + "\n---\n\n"
    p = os.path.join(root, "定稿", "正文", "%03d-%s.md" % (n, title))
    with open(p, "w", encoding="utf-8") as f:
        f.write(head + (prose or "# %s\n\n正文。\n" % title))
    sp = os.path.join(root, "定稿", "记忆", "章摘要", "%03d.md" % n)
    with open(sp, "w", encoding="utf-8") as f:
        f.write("# 章摘要 %03d\n%s\n" % (n, fm["summary"]))
    return p


def write_file(root, rel, content):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    return p


@pytest.fixture()
def book(tmp_path):
    return make_book(str(tmp_path / "书"))


@pytest.fixture()
def book_with_ch1(book):
    add_chapter(book, 1, title="开局", prose="第一行。\n\n第二行。\n\n他笑了笑。",
                promises_new="P-001", gaps_new="S-001", entities_new="阿米,米粒",
                must_cover="阿米,米粒", forbidden="赵三")
    st.merge_chapter_facts(st.load_state(book), 1, st.frontmatter(st.chapter_files(book) and os.path.join(book, "定稿", "正文", st.chapter_files(book)[0])))
    return book
