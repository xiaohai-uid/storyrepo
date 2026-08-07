# storyrepo · 长篇小说写作 skill

> **给 AI 写作 agent 用的长篇生产技能**:装进你的 agent(pi / Claude Code / Codex / opencode),对它说一句"写小说",它就会按完整的生产流水线干活——大纲、伏笔、机检、追踪、批次并行,让 100 万字连载不爆上下文、不忘设定、不丢伏笔。

`storyrepo` 是一个 **agent skill**(SKILL.md + 写作规范 + 模板),自带一个**零依赖 Python 引擎**(`engine/`)作为支撑工具:机检门禁、状态追踪、字数账本这些机械活由脚本干,创作决策留给人或 agent。

## 为什么是 skill

长篇最难的不是第一章,而是第 80、200 章以后依然:角色动机不漂移、战力时间线不打架、伏笔有登记有回收、每章事实沉淀成可检索状态。这套"必须记住、不能写崩"的约束,做成 **skill 才有用**——因为它是 agent 每次动笔前的操作宪法,不是要人记住的文档。

## 安装(三选一)

```bash
# ① 一键装进本机所有 agent(pi / codex / .agents / claude / opencode)
git clone https://github.com/xiaohai-uid/storyrepo
cd storyrepo && bash scripts/install.sh --with-engine

# ② 只装 skill,不要引擎(纯协议模式,agent 也能用)
bash scripts/install.sh

# ③ 手动:把 SKILL.md + references/ + templates/ 拷进你的 agent 技能目录
#   pi:        ~/.pi/agent/skills/storyrepo/
#   claude:    ~/.claude/skills/storyrepo/
#   codex:     ~/.codex/skills/storyrepo/
#   .agents:   ~/.agents/skills/storyrepo/
```

装完直接对 agent 说:**"写一本小说" / "续写第 N 章" / "用 storyrepo 开新书"**,它会自动加载本技能按流水线执行。

## 引擎(支撑工具,可选)

```bash
# 想用机检/追踪/账本(推荐):装引擎
python3 -m venv --without-pip engine/.venv
engine/.venv/bin/python engine/vendor/get-pip.py
engine/.venv/bin/pip install -e engine
# 无 pip 环境也 OK,vendor/ 自带 get-pip 引导器;214 个测试见 engine/tests
```

## 流水线(agent 按 SKILL.md 自动执行)

```
开书:三层问答 → 建仓(init-book.sh)→ 规划确认 → 模式选择
章事务:contract → context/brief → 起草 → doctor(三重机检门禁)→ review → commit → check
维护:revision(回炉级联)· batch(批次并行)· learn(反例吸收)· resume(断点恢复)
```

一本书 = 一个 git 仓库:大纲/ 定稿/(只增不改) 文风/ 追踪/(单一权威状态+7栏状态卡) 工作区/。

## 机制出处(全部对照开源先贤实现)

| 机制 | 来自 |
|---|---|
| 章事务 + 三重 gate + 五段任务书 | [lingfengQAQ/webnovel-writer](https://github.com/lingfengQAQ/webnovel-writer) |
| 四路上下文 + 下一章钩子注入 | [YILING0013/AI_NovelGenerator](https://github.com/YILING0013/AI_NovelGenerator) |
| 单一权威追踪 + 作者/读者双视图 | oh-story tracking 系统 |
| 开书三层问答 + 批次并行 | [PenglongHuang/chinese-novelist-skill](https://github.com/PenglongHuang/chinese-novelist-skill) |
| 去 AI 味三律 + 反例吸收 | [worldwonderer/oh-story-claudecode](https://github.com/worldwonderer/oh-story-claudecode) |

详见 [references/provenance.md](references/provenance.md)。

## 真实案例

《零界道种》——100 万字目标连载中,第 001-002 章经完整流水线产出,机检连环拦截 4 处真实文风缺陷(口头禅/归属词/句式重复)。引擎 214 测试全绿。

## 许可

MIT © 2026 xiaohai-uid
