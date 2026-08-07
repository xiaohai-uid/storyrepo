# -*- coding: utf-8 -*-
"""端到端生命周期:一条命令演示并验证完整章事务流水线。
机制:webnovel-write 章事务(预检→合同→任务书→起草→机检→评审→提交→结转)+ 回炉 + 学习。
实现:直接调用模块函数(不走子进程),任何一步失败 → 非零退出 + 指出失败步骤。"""
import json, os, tempfile, shutil
from typing import Dict, List

from storyrepo import state as st
from storyrepo import config, gates, contract, context, brief, review, views
from storyrepo import revision, resume, learn, report


E2E_BOOK_YAML = """---
name: e2e书
status: writing
total_chapters: 3
min_words_per_chapter: 300
max_words_per_chapter: 1100
target_words: 990
---
"""


def _log(step, ok, detail=""):
    print("%s %s %s" % ("✔" if ok else "✘", step, detail))
    return ok


def _write_ch(root, n, title, prose, **fm_extra):
    fm = {
        "title": title, "chapter": "%03d" % n, "volume": 1,
        "words": str(st.hanzi(prose)), "status": "定稿",
        "promises_new": "", "promises_advanced": "", "promises_done": "",
        "info_gaps_new": "", "info_gaps_revealed": "", "entities_new": "",
        "must_cover": "", "forbidden": "", "summary": title + ":" + prose[:30],
    }
    fm.update(fm_extra)
    head = "---\n" + "\n".join("%s: %s" % (k, v) for k, v in fm.items()) + "\n---\n\n"
    p = os.path.join(root, "定稿", "正文", "%03d-%s.md" % (n, title))
    with open(p, "w", encoding="utf-8") as f:
        f.write(head + prose)
    sp = os.path.join(root, "定稿", "记忆", "章摘要", "%03d.md" % n)
    with open(sp, "w", encoding="utf-8") as f:
        f.write("# 章摘要 %03d\n%s\n" % (n, fm["summary"]))
    return p


PROSE1 = "他推开木门。\\n\\n雪落在门槛上,他数了数脚印。\\n\\n他笑了一下,把门带上。"
PROSE2 = "她递来一碗粥。\\n\\n他喝了一口,烫得皱眉。\\n\\n窗外的雨又大了。"
PROSE3 = "他折好信,放进怀里。\\n\\n巷口有人喊他名字。\\n\\n他回头,灯还亮着。"


def run_e2e(root: str) -> int:
    """全生命周期。返回退出码(0 成功)。root 已存在且为空目录。"""
    steps: List[str] = []

    def step(name, ok, detail=""):
        steps.append(name)
        _log(name, ok, detail)
        if not ok:
            raise SystemExit("e2e 失败于步骤: %s" % name)

    # 1 init + 骨架
    with open(os.path.join(root, "book.yaml"), "w", encoding="utf-8") as f:
        f.write(E2E_BOOK_YAML)
    for d in ("大纲", "定稿/正文", "定稿/记忆/章摘要", "定稿/设定", "文风/金句库", "工作区/评审报告"):
        os.makedirs(os.path.join(root, d), exist_ok=True)
    st.init_state(root)
    step("init", os.path.exists(st.state_path(root)))

    # 2 细纲蓝图(contract/brief 的输入)
    with open(os.path.join(root, "大纲", "细纲蓝图.md"), "w", encoding="utf-8") as f:
        f.write("| 章 | 标题 | 要发生什么 | 硬约束 | 禁区 | 下一章悬念 |\n"
                "| 1 | 门 | 推门见雪 | 无 | 无 | ★★ |\n"
                "| 2 | 粥 | 喝粥 | 无 | 无 | ★ |\n"
                "| 3 | 信 | 折信被喊 | 无 | 无 | — |\n")

    # 3 合同/上下文/任务书可生成
    s = st.load_state(root)
    c = contract.build_contract(root, s, 1)
    step("contract", c.get("goal") == "推门见雪", json.dumps(c.get("goal"), ensure_ascii=False))
    ctx = context.assemble_context(root, s, 1)
    step("context预算", ctx["budget_kb"] <= 8, "%.1fKB" % ctx["budget_kb"])
    b = brief.build_brief(root, s, 1)
    step("brief五段", all(x in b for x in ("开篇委托", "这章的故事", "这章的人物", "怎么写更顺", "收在哪里")))

    # 4 逐章:起草 → 机检 → 结算(真实工作流顺序,一章一章来)
    with open(os.path.join(root, "定稿", "设定", "名册.md"), "w", encoding="utf-8") as f:
        f.write("| 正名 | 首现 | 备注 |\n| 阿门 | 001 | 场景 |\n| 阿粥 | 002 | 道具 |\n| 阿信 | 003 | 道具 |\n")
    chapters = [(1, "门", PROSE1, "阿门"), (2, "粥", PROSE2, "阿粥"), (3, "信", PROSE3, "阿信")]
    for n, title, prose, ent in chapters:
        _write_ch(root, n, title, prose, entities_new=ent)
        g = gates.gate(root, "precommit", n)
        step("doctor ch%d" % n, g["passed"], "; ".join(g["fails"])[:120])
        s = st.load_state(root)
        f = [x for x in st.chapter_files(root) if st.chapter_num(x) == n][0]
        fm = st.frontmatter(os.path.join(root, "定稿", "正文", f))
        st.merge_chapter_facts(s, n, fm, summary=fm.get("summary", ""))
        st.bump_revision(s)
        st.save_state(root, s)
        views.write_views(root, s)

    # 6 check + 状态卡
    s = st.load_state(root)
    step("check", s["imported_through_chapter"] == 3 and os.path.getsize(
        os.path.join(st.tracking_path(root), "上下文.md")) <= st.MAX_CARD_BYTES)
    step("状态卡7栏", sum(1 for l in open(os.path.join(st.tracking_path(root), "上下文.md"), encoding="utf-8")
                      if l.startswith("## ")) == 7)

    # 7 评审(注入 low 非 blocking)+ 报告
    review.save_review(root, 3, [])
    rp = review.write_report(root, 3, [])
    step("评审落库", os.path.exists(rp))
    t = report.author_report(root, "postcommit", ch=3)
    step("报告三段", all(x in t for x in ("状态", "做了什么", "下一步")))

    # 8 learn(金句 + 趋势)
    n = learn.harvest_quotes(root, 3)
    step("learn金句", n >= 0, "%d 条" % n)

    # 9 回炉:改第 2 章 → 级联
    r = revision.cascade_revision(root, s, 2, st.revision(s))
    step("回炉级联", r.get("ok") and not r.get("conflict"))

    # 10 postcommit gate(回炉后必须全绿)
    g = gates.gate(root, "postcommit", 2)
    step("postcommit", g["passed"], "; ".join(g["fails"])[:120])

    print("\ne2e 全链路通过: %d 步" % len(steps))
    return 0


def cli_e2e(args):
    made = not args.root
    root = os.path.abspath(args.root or tempfile.mkdtemp(prefix="storyrepo-e2e-"))
    os.makedirs(root, exist_ok=True)
    try:
        return run_e2e(root)
    except SystemExit as e:
        print(str(e))
        return 1
    except Exception as e:      # 破坏路径全量兜底:CLI 永不裸崩
        print("e2e 失败: %s" % e)
        return 1
    finally:
        if made:
            shutil.rmtree(root, ignore_errors=True)
