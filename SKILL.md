---
name: storyrepo
description: 长篇小说「故事仓库」v2 生产系统——完整复刻 webnovel-writer / oh-story / AI_NovelGenerator / chinese-novelist 的实现机制。当用户要求写、续写、规划、回炉、审查长篇小说(百万字、网文连载、零界道种 等项目)时使用。触发词:写小说、续写、写第N章、长篇小说、网文、百万字、开书、大纲、卷纲、细纲、设定、伏笔、信息差、去AI味、回炉、重写第N章、storyrepo。
---

# 故事仓库 v2 · 长篇生产系统

机制来源(全部对照实现,见 references/provenance.md):
- **webnovel-write**:章事务 8 步 + 三重 gate + 恢复契约 + 充分性闸门
- **context-agent**:五段写作任务书(权重与红线照抄)
- **AI_NovelGenerator**:四路上下文组装(最近3章结尾+摘要+检索+下一章蓝图)
- **oh-story**:单一权威追踪(_tracking-state.json)+ 作者/读者双视图 + 固定 7 栏状态卡 ≤12KB
- **chinese-novelist**:开书三层问答 + 规划二次确认 + 写作模式选择 + 疯狂创作阶段
- 自研(标注):状态卡脚本化生成(源自 oh-story 思想,简化实现)

## 一、开书流(新书必经,见 references/opening.md)

1. **偏好加载**:读 `偏好记忆.md`(若有);中断续写检测(有追踪/正文→先恢复)。
2. **三层问答**:L1 核心定位 3 问(题材/主角+关系/核心冲突,必答)→ L2 深度定制 5 问(世界观/视角基调/核心主题/读者定位/章节数)→ L3 标题生成 3 候选。
3. **建仓**:`bash templates/init-book.sh <书名> <章数> <每章字数>` → 生成 人物档案/大纲/细纲蓝图/写作计划(book.yaml)+ `tracking.py init`。
4. **二次确认**:展示 书名/总章数/目标字数/主要人物 摘要,等用户确认。
5. **模式选择**:serial(主agent串行,默认)/ subagent-parallel(批次并行,中长篇推荐)/ agent-teams。

## 二、章事务(每章一轮,顺序不可倒置)

> 所有机械步骤由引擎 CLI 执行(安装:bash scripts/install.sh --with-engine;命令面:init/doctor/contract/context/brief/review/commit/check/revision/resume/learn/batch/e2e/stats/status/report)。

### Step 0 预检(gate)
```bash
storyrepo doctor --stage prewrite [--root 书仓]
```
项目完整性 / 编号连续 / 占位符。

### Step 1 合同
```bash
storyrepo contract --chapter N [--root 书仓]
```
从 章纲当前行 + 承诺/信息差总表 + 上章摘要 组装**本章合同**:目标 / 硬约束 / 禁区(信息差边界)/ 伏笔处理清单(超期必处理,可选 ≤5)/ 结尾要求。合同必须与 章纲 逐字一致,禁止占位 query。

### Step 2 任务书(五段,references/task-brief.md)
```bash
storyrepo context --chapter N    # 四路上下文
storyrepo brief --chapter N      # 五段任务书
```
按 context-agent 规则组装五段:①开篇委托(书名/章号/一句话目标)②这章的故事(前文摘要/目标/节点/禁区/RAG线索)③这章的人物(每人:状态/驱动/作用/说话倾向)④怎么写更顺(风格裁决/节奏/反模式)⑤收在哪里(结尾感觉+未完感)。
数据权重:用户要求 > 章纲 > 设定 > 承诺/信息差 > 上章摘要。事实冲突/时空承接/能力来源/动机断裂/合同一致 五查全过才算完。

### Step 3 起草
四路上下文,只从任务书写:
1. 最近 3 章结尾(各 ≤800 字,含上章钩子)
2. 章摘要链(全书摘要由 记忆/章摘要 渐进合成)
3. 定点检索:只查本合同涉及的角色卡/设定页/承诺页(≤3 张),不整读
4. **下一章蓝图注入**:细纲里下一章的 悬念等级/伏笔/转折 → 本章结尾必须给它留钩子
输出纯正文,无占位符。

### Step 4 机检(gate,脚本)
```bash
storyrepo doctor --stage precommit --chapter N
```
硬检查:字数窗口 / 占位符 / **信息差泄密扫描**(S- 未到曝光章不得出现关键词)/ 新专名 vs 名册(未登记即 fail)/ 禁词与复读 / 章末总结体 / 合同断言(目标、必覆盖节点、禁区零命中)。任一 fail 回 Step 3。

### Step 5 评审(子代理,独立上下文)
- 必须用子代理,禁止主流程伪造 JSON;评审 JSON 由 `storyrepo review --json f --chapter N` 校验并落库。
- 只返回 schema JSON(severity/category/location/description/evidence/fix_hint/blocking),不写文件、不评分。
- 只跑一轮。blocking=true 定点修复(不改剧情不破设定)后直接进 Step 6;无法修 → 用户裁决(接受/手修/放弃)。
- `--fast` 只查 setting/timeline/continuity。
- 评审结果落 工作区/评审报告/第NNN章.json + 审查报告.md。

### Step 6 润色
顺序:非 blocking 修复 → 风格适配 → 排版 → **Anti-AI 终检**(references/anti-ai-flavor.md 三遍法)。只改表达不改事实;Anti-AI fail 不进 Step 7。

### Step 7 结算(data-agent + 追踪事务)
1. 事实提取:履行结果(合同目标达成?)/ 消歧(别名/同名)/ 新事实清单(角色状态/关系/持有物/新实体)。
2. 追踪事务:`storyrepo commit --chapter N` — 从 front matter 合并事实到 `追踪/_tracking-state.json` → 重建全部派生视图(状态卡7栏/伏笔/角色状态/作者真相/读者已知/逐章记录/时间线)。
3. 金句收割:`storyrepo learn --chapter N`(可选)。
4. 状态卡 ≤12KB 强制(tracking 自动检查)。

### Step 8 结转
```bash
storyrepo doctor --stage postcommit --chapter N
storyrepo check
storyrepo stats
git add -A && git commit -m "ch(NNN): 标题"   # 副行:承诺 +P/~P/$P;信息差 +S/曝光S
```

## 三、恢复契约

- 每章执行前查断点:`storyrepo resume --chapter NNN` 根据 正文/评审/追踪/commit 状态给出续跑建议(只建议,不覆盖)。
- 正文被手改过、章纲晚于正文、已 accepted 重跑 → 停下问用户(沿用/重写/只看状态)。
- 失败只补跑失败步骤,不回退已完成的 Step。
- 少打扰:默认推进;只有 创作方向/事实一致性/覆盖风险/blocking 无法定点处理 才问,给 2-3 个有限选项。

## 四、回炉(大修,references/tracking.md §5)

1. 定位章(编号或关键词)→ 备份原稿 `第NNN章_原稿_日期.md` → 确认范围(全文/局部)。
2. 载入上下文:本章 + 前/后一章 + 状态卡 + 相关角色动态快照。
3. 修改;字数差 >30% 或 >800 提醒。
4. **级联**:`tracking.py commit --mode revision` — 重算该章增量、伏笔当前值重算到 M 章、三轨(客观事实/读者认知/揭示状态)、角色快照整份重算、并发控制(expected state_revision)。改完 `tracking.py check` 全绿才许写下一章。
5. 输出后续影响清单:哪些后续章需同步调整。

## 五、上下文预算(硬约束,references/context-budget.md)

- 正文只写不读;续写冷启动 = 状态卡 7 栏(≤12KB)+ 本章合同 + ≤3 张角色卡;读盘 ≤8K token。
- 逐章记录目标 ≤1536B(硬上限 3072B):只记影响后续连续性的紧凑变化,不重放全文。
- 批次 ≤3–5 章(≈2 万字)后:结转 + 开新会话/子代理;写评分离强制。
- 追踪工具是唯一写入方;禁止手改派生视图(状态卡/伏笔.md/角色状态/双视图)。

## 六、关联文件

| 文件 | 内容 |
|---|---|
| engine/ | **可执行引擎**(纯标准库 CLI,214 测试;支撑工具,可选安装) |
| references/opening.md | 开书问答 3 层 + 偏好记忆 + 规划确认 + 模式选择 |
| references/protocol.md | 目录规范/命名/commit/retcon/边界 |
| references/task-brief.md | 五段任务书 + 权重 + 红线校验 |
| references/tracking.md | 追踪系统 JSON 结构/逐章记录/双视图/级联大修 |
| references/review-schema.md | 评审 JSON schema + blocking 门禁 |
| references/anti-ai-flavor.md | Anti-AI 三遍法 + 禁词表 |
| references/provenance.md | 机制出处对照(复刻自证) |
| templates/init-book.sh | 建仓脚本(调 CLI) |