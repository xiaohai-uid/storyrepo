# 仓库协议(目录/命名/commit/retcon/双视图)

> 机制来源:webnovel-writer v7 spec + oh-story 追踪,适配纯 Markdown+git 环境。

## 1. 目录

```
<书名>/
├── book.yaml                  # 全书配置 + 写作计划(chapters: status/wordCount/retryCount)
├── 偏好记忆.md                # 用户偏好(favoriteGenres/protagonist/风格,chinese-novelist 思路)
├── 大纲/
│   ├── 总纲.md                 # 主题、金手指、结局承诺
│   ├── 卷纲_第X卷.md
│   ├── 细纲_第X章.md           # 蓝图条目:role/purpose/suspense/foreshadow/twist/summary(给下章注入)
│   ├── 承诺/、信息差/           # P-/S- 单页 + 总表
│   └── 大纲安全审查记录.md      # 批次级:情绪发动机/主角护栏/可证伪降级检查
├── 定稿/
│   ├── 正文/NNN-标题.md        # + front matter(§3)
│   ├── 设定/{世界观,力量,时间线,名册,角色/,信息差/}
│   └── 记忆/章摘要/
├── 作品风格/风格宪法.md · 金句库/
├── 追踪/                       # 唯一权威 + 派生视图(工具重建,禁手改)
│   ├── _tracking-state.json
│   ├── 上下文.md               # 续写状态卡 固定7栏 ≤12KB
│   ├── 伏笔.md                 # 每 ID 一行
│   ├── 角色状态/{名}.md
│   ├── 作者真相.md · 读者已知.md
│   ├── 逐章记录/第NNN章.md      # ≤1536B 目标 / 3072B 上限
│   └── 时间线.md
├── 工作区/                     # 合同/草稿/评审/gitignored
├── scripts/ doctor.py · tracking.py · stats.py
```

## 2. 状态卡固定 7 栏(跟踪:上下文.md,≤12288B)

1. 当前进度(卷/章/字数)
2. 下一章合同(章纲摘 + 必须履行承诺)
3. 活跃伏笔(≤N,超期标⏰)
4. 核心角色状态(快照,每人一行)
5. 最近章节结尾(≤3 章,接写锚)
6. 未曝光信息差(边界一句话)
7. 风格锚点(三律)

> 第 N 章之前本章 6 栏更新为最新;该章写完须剔除已曝光项。缺失就按「旧信息查找步骤」定点查,不整读逐章增量。

## 3. 命名与 front matter

- 章文件 `NNN-标题.md`(零填充);正文一律正名,别名进名册。
- front matter(平铺):title/chapter/volume/words/status/promises_new|advanced|done/info_gaps_new/entities_new/contract(本章合同摘要)。
- commit:`ch(NNN)|vol|retcon|fix` + 副行 `承诺:+P ~P $P;信息差:+S 曝光S`。

## 4. 设定变更(retcon)

- 定稿只增不改;改设定 = 追踪事务 `--mode revision` 级联(见 tracking.md §5),禁止手改派生。
- 版本/回溯用 git;不另造提交链。

## 5. 双视图原则(作者真相 vs 读者已知)

- `作者真相.md`:发生了什么(完全事实,含下卷欲回收的伏笔实情)。
- `读者已知.md`:读者目前能看到/推断出什么(曝光门槛)。
- 写作时若正文会把 S- 提前暴露 → 先改设计再动笔;追踪由工具一次事件合并三轨,禁止分别手改。