# -*- coding: utf-8 -*-
import os
import pytest
from conftest import add_chapter
from storyrepo import learn


class TestHarvestQuotes:
    def test_harvest_ok(self, book):
        prose = ("他抬起头,望向远方。\n\n"
                 "命运从不会亏待努力的人。\n\n"
                 "他说:这不公平。\n\n"
                 "夜色渐深。\n\n")
        add_chapter(book, 1, prose=prose, summary="第一章")
        assert learn.harvest_quotes(book, 1) == 3
        t = open(os.path.join(book, "文风", "金句库", "001.md"), encoding="utf-8").read()
        assert "命运从不会亏待努力的人。" in t
        assert "他说" not in t

    def test_idempotent_and_cross_chapter_dedupe(self, book):
        add_chapter(book, 1, prose="命运从不会亏待努力的人。\n\n他笑了笑。\n\n", summary="第一章")
        assert learn.harvest_quotes(book, 1) == 2
        assert learn.harvest_quotes(book, 1) == 0      # 重复收割不新增
        add_chapter(book, 2, prose="命运从不会亏待努力的人。\n\n", summary="第二章")
        assert learn.harvest_quotes(book, 2) == 0      # 与既有文件去重

    def test_max_five_per_chapter(self, book):
        prose = "".join("金句%d。" % i + "\n\n" for i in range(1, 8))
        add_chapter(book, 1, prose=prose, summary="第一章")
        assert learn.harvest_quotes(book, 1) == 5

    def test_long_line_not_quote(self, book):
        prose = "这是一个非常非常非常非常非常非常非常非常非常非常非常长的句子,肯定超过二十五个字了。\n\n"
        add_chapter(book, 1, prose=prose, summary="第一章")
        assert learn.harvest_quotes(book, 1) == 0

    def test_missing_chapter_raises(self, book):
        with pytest.raises(FileNotFoundError):
            learn.harvest_quotes(book, 9)


class TestStyleStats:
    def test_stats(self, book):
        add_chapter(book, 1, prose="你好。\n\n她说:「早安。」\n\n他又说了一句。\n\n", summary="一")
        add_chapter(book, 2, prose="他摇了摇头。\n\n", summary="二")
        out = learn.style_stats(book)
        assert set(out) == {1, 2}
        assert out[1]["hanzi"] == 12
        assert out[1]["paragraphs"] == 3
        assert abs(out[1]["dialogue_ratio"] - 1.0 / 3) < 1e-9
        assert out[2]["dialogue_ratio"] == 0.0
        assert out[1]["redline_hits"] == 0

    def test_redline_hits_counted(self, book):
        # 对照 checks.redlines() 四类红线:章末总结体/预告体/万能比喻/抽象升华
        prose = ("这一章讲述了主角的抉择。\n\n"
                 "下一章,风雨将至。\n\n"
                 "仿佛一幅画卷。\n\n"
                 "或许这就是命运。\n\n")
        add_chapter(book, 1, prose=prose, summary="一")
        out = learn.style_stats(book)
        assert out[1]["redline_hits"] == 4

    def test_empty_book(self, book):
        assert learn.style_stats(book) == {}
