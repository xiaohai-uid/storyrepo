# -*- coding: utf-8 -*-
"""storyrepo CLI:长篇生产引擎的完整命令面。
用法: storyrepo <cmd> [--root R] [--chapter N] ...
机制:webnovel-writer 章事务(预检→合同→任务书→起草→机检→评审→提交→结转)+ oh-story 追踪 + AI_Novel 上下文。
"""
import argparse, json, os, re, sys, time

from storyrepo import config, state as st
from storyrepo import checks, gates, views, contract, context, brief
from storyrepo import review, revision, resume, learn, report, e2e


def find_root(args):
    return os.path.abspath(args.root or os.getcwd())


def cmd_init(args):
    root = find_root(args)
    if not os.path.exists(os.path.join(root, "book.yaml")):
        print("✘ 缺 book.yaml: 请先建仓(init-book.sh 或手工)。"); return 1
    created = st.init_state(root)
    views.write_views(root, st.load_state(root))
    print("✅ 追踪初始化(%s)%s" % (os.path.join(root, "追踪"), " 新建" if created else " 已存在"))
    return 0


def cmd_doctor(args):
    root = find_root(args)
    try:
        r = gates.gate(root, args.stage, args.chapter)
    except FileNotFoundError as e:
        print("✘", e); return 1
    for s in r["oks"]: print("  ✔", s)
    for s in r["fails"]: print("  ✘", s)
    print("gate %s: %s" % (args.stage, "PASS" if r["passed"] else "FAIL"))
    return 0 if r["passed"] else 1


def cmd_contract(args):
    root = find_root(args)
    c = contract.build_contract(root, st.load_state(root), args.chapter)
    print(json.dumps(c, ensure_ascii=False, indent=1)); return 0


def cmd_context(args):
    root = find_root(args)
    ctx = context.assemble_context(root, st.load_state(root), args.chapter)
    print("budget: %.1fKB %s" % (ctx["budget_kb"], "OK" if ctx["budget_kb"] <= 8 else "超限!"))
    for k, v in ctx.items():
        if k == "budget_kb": continue
        print("\n[%s]" % k)
        for item in (v if isinstance(v, list) else [v]):
            print("  " + str(item)[:200])
    return 0


def cmd_brief(args):
    root = find_root(args)
    print(brief.build_brief(root, st.load_state(root), args.chapter)); return 0


def cmd_review(args):
    root = find_root(args)
    p = args.json
    if not os.path.exists(p):
        print("✘ 评审 JSON 不存在:", p); return 1
    issues, errs = review.load_review(p)
    for e in errs: print("  ⚠", e)
    if not review.has_blocking(issues):
        review.save_review(root, args.chapter, issues)
        print("✅ 评审落库(0 blocking),报告:", review.write_report(root, args.chapter, issues))
        return 0
    print("✘ 存在 blocking(%d):" % sum(1 for i in issues if i.blocking))
    for i in issues:
        if i.blocking: print("   - [%s/%s] %s" % (i.severity, i.category, i.description))
    print("  请定点修复或用户裁决后再 review。")
    return 1


def cmd_commit(args):
    root = find_root(args)
    ch = args.chapter or st.latest_chapter(root)
    fs = [f for f in st.chapter_files(root) if st.chapter_num(f) == ch]
    if not fs:
        print("✘ 章 %d 无正文" % ch); return 1
    # L11:提交前提示(不强拦,流程纪律靠 author)
    try:
        g = gates.gate(root, "precommit", ch)
        if not g["passed"]:
            print("⚠ precommit gate 未过(%d 项失败),提交将带着问题入账。用 --force 显式确认。" % len(g["fails"]))
            if not args.force:
                print("  (阻断:先修 gate 或加 --force)")
                return 1
    except FileNotFoundError:
        pass
    # M1:幂等守卫——该章已提交则拒绝重复合并(防止时间线污染)
    s = st.load_state(root)
    if str(ch) in s.get("chapters", {}):
        print("✘ 章 %d 已提交过(rev %d)。重写走 storyrepo revision --chapter %d(重放式级联);新章节请另建批次计划。" % (ch, st.revision(s), ch))
        return 1
    fm = st.frontmatter(os.path.join(root, "定稿", "正文", fs[0]))
    warns = st.merge_chapter_facts(s, ch, fm, fm.get("summary", ""))
    st.bump_revision(s)
    st.save_state(root, s)
    views.write_views(root, s)
    print("✅ commit ch%d (rev %d),派生视图已重建" % (ch, st.revision(s)))
    for w in warns:
        print("  ⚠", w)
    return 0


def cmd_check(args):
    root = find_root(args)
    try:
        s = st.load_state(root)
    except FileNotFoundError as e:
        print("✘", e); return 1
    fails = []
    if not os.path.exists(os.path.join(st.tracking_path(root), "上下文.md")):
        fails.append("缺派生 上下文.md")
    if not views.card_size_ok(root):
        fails.append("状态卡超 12KB")
    chs = sorted(int(k) for k in s["chapters"])
    if chs and chs != list(range(1, max(chs) + 1)):
        fails.append("章节记录不连续")
    if s["imported_through_chapter"] != (max(chs) if chs else 0):
        fails.append("imported_through_chapter 与最新章不符")
    print("==== tracking check ====")
    for f in fails: print("  ✘", f)
    if not fails: print("  ✔ 状态有效 / 派生一致 / 状态卡 ≤12KB")
    return 1 if fails else 0


def cmd_status(args):
    root = find_root(args)
    try:
        s = st.load_state(root)
    except FileNotFoundError:
        s = {}
    print(json.dumps({
        "book": s.get("book"), "rev": st.revision(s) if s else None,
        "through": s.get("imported_through_chapter"),
        "chapters": len(s.get("chapters", {})),
        "latest_chapter_file": st.latest_chapter(root),
        "words": sum(st.hanzi(st.body(os.path.join(root, "定稿", "正文", f))) for f in st.chapter_files(root)),
        "promises_open": len(st.active_promises(s)) if s else None,
        "gaps_unrevealed": len(st.unrevealed_gaps(s)) if s else None,
    }, ensure_ascii=False, indent=1))
    return 0


def cmd_revision(args):
    root = find_root(args)
    try:
        s = st.load_state(root)
    except (FileNotFoundError, ValueError) as e:
        print("✘", e); return 1
    expected = args.expected_revision if args.expected_revision is not None else st.revision(s)
    r = revision.cascade_revision(root, s, args.chapter, expected)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r.get("ok") else 1


def cmd_resume(args):
    root = find_root(args)
    print(json.dumps(resume.diagnose(root, args.chapter), ensure_ascii=False, indent=1))
    return 0


def cmd_learn(args):
    root = find_root(args)
    if args.absorb:
        if not args.chapter:
            print("✘ learn --absorb 需要 --chapter N"); return 2
        n = learn.absorb_review(root, args.chapter)
        print("✅ 吸收反例 %d 条(ch%s)→ 文风/审查反例库.md(机检红线已动态生效)" % (n, args.chapter))
        return 0
    if args.trend:
        for d in learn.trend(root, args.trend):
            print("  ch%s: %s" % (d.get("chapter"), {k: v for k, v in d.items() if k != "chapter"}))
        return 0
    n = learn.harvest_quotes(root, args.chapter)
    sts = learn.style_stats(root)
    print("金句收割 %d 条(ch%s);全书风格统计:" % (n, args.chapter))
    for ch, d in list(sts.items())[:10]:
        print("  ch%s: %s" % (ch, d))
    return 0


def _parse_chapters(spec):
    """解析 --chapters:单章 31 / 区间 31-35 / 列表 31,33,34;非法→ ValueError。"""
    spec = (spec or "").strip()
    if not spec:
        raise ValueError("--chapters 不能为空(例:31 / 31-35 / 31,33,34)")
    out = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"(\d+)-(\d+)", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a > b:
                raise ValueError("区间反序: %s-%s" % (a, b))
            out.extend(range(a, b + 1))
        elif re.fullmatch(r"\d+", part):
            out.append(int(part))
        else:
            raise ValueError("无法解析章节: %r(例:31 / 31-35 / 31,33,34)" % part)
    if not out:
        raise ValueError("--chapters 解析为空")
    return out


def cmd_batch(args):
    from storyrepo import batch
    root = find_root(args)
    if args.batch_cmd == "create":
        try:
            chapters = _parse_chapters(args.chapters)
        except ValueError as e:
            print("✘ %s" % e)
            return 2
        plan = batch.create_batch_plan(root, chapters)
        out = os.path.join(root, "工作区", "批次-%s.json" % time.strftime("%Y%m%d-%H%M%S"))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=1)
        print("✅ 批次计划已生成: %s(%d 章, mode=%s)" % (out, len(plan["chapters"]), plan["mode"]))
        print("   worker 协议:每个子代理读 状态卡+合同(计划内) → 写正文+front matter → doctor precommit 通过 → 返回")
        return 0
    if args.batch_cmd == "merge":
        with open(args.plan, encoding="utf-8") as f:
            plan = json.load(f)
        r = batch.merge_batch(root, plan)
        print(json.dumps({k: v for k, v in r.items() if k != "detail"}, ensure_ascii=False, indent=1))
        return 0 if r.get("ok", False) else 1
    return 1


def cmd_stats(args):
    root = find_root(args)
    files = st.chapter_files(root)
    tot = sum(st.hanzi(st.body(os.path.join(root, "定稿", "正文", f))) for f in files)
    try:
        cfg = config.load_config(root)
        target = cfg.get("target_words", 0)
    except FileNotFoundError:
        target = 0
    for f in files:
        print("%s %7d 字" % (f, st.hanzi(st.body(os.path.join(root, "定稿", "正文", f)))))
    print("-" * 30)
    print("正文合计: %d 字 (%.2f 万)%s" % (tot, tot / 10000,
          (" / 目标 %d 万 (%.2f%%)" % (target // 10000, tot / target * 100) if target else "")))
    return 0


def cmd_report(args):
    root = find_root(args)
    print(report.author_report(root, args.stage, args.chapter))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="storyrepo", description="storyrepo 长篇生产引擎")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(subp):
        subp.add_argument("--root", default="", help="书仓根(默认当前目录)")
        return subp

    add(sub.add_parser("init"))
    d = add(sub.add_parser("doctor")); d.add_argument("--stage", default="precommit", choices=["prewrite", "precommit", "postcommit"]); d.add_argument("--chapter", type=int)
    c = add(sub.add_parser("contract")); c.add_argument("--chapter", type=int, required=True)
    x = add(sub.add_parser("context")); x.add_argument("--chapter", type=int, required=True)
    b = add(sub.add_parser("brief")); b.add_argument("--chapter", type=int, required=True)
    r = add(sub.add_parser("review")); r.add_argument("--chapter", type=int, required=True); r.add_argument("--json", required=True)
    m = add(sub.add_parser("commit")); m.add_argument("--chapter", type=int); m.add_argument("--force", action="store_true", help="precommit gate 未过时仍提交")
    add(sub.add_parser("check"))
    add(sub.add_parser("status"))
    rv = add(sub.add_parser("revision")); rv.add_argument("--chapter", type=int, required=True); rv.add_argument("--expected-revision", type=int, help="并发控制:期望修订号(默认取当前)")
    rs = add(sub.add_parser("resume")); rs.add_argument("--chapter", type=int)
    l = add(sub.add_parser("learn")); l.add_argument("--chapter", type=int); l.add_argument("--absorb", action="store_true", help="吸收该章评审反例到 文风/审查反例库.md"); l.add_argument("--trend", type=int, nargs="?", const=10, help="输出近 N 章文风趋势(默认10)")
    bc = add(sub.add_parser("batch")); bc.add_argument("batch_cmd", choices=["create", "merge"]); bc.add_argument("--chapters", default="", help="如 31-35 或 31,32,33"); bc.add_argument("--plan", default="", help="merge 用:批次计划 JSON 路径")
    add(sub.add_parser("stats"))
    add(sub.add_parser("e2e"))
    rp = add(sub.add_parser("report")); rp.add_argument("--stage", default="write"); rp.add_argument("--chapter", type=int)

    args = p.parse_args(argv)
    fn = {"init": cmd_init, "doctor": cmd_doctor, "contract": cmd_contract,
          "context": cmd_context, "brief": cmd_brief, "review": cmd_review,
          "commit": cmd_commit, "check": cmd_check, "status": cmd_status,
          "revision": cmd_revision, "resume": cmd_resume, "learn": cmd_learn,
          "batch": cmd_batch,
          "stats": cmd_stats, "e2e": e2e.cli_e2e, "report": cmd_report}.get(args.cmd)
    if fn is None:
        p.print_help(); return 2
    try:
        return fn(args)
    except Exception as e:
        print("✘ %s: %s" % (type(e).__name__, e))
        return 1


if __name__ == "__main__":
    sys.exit(main())
