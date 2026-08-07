# 机制出处对照(复刻自证)

> 本表证明每个机制来自哪个项目实现,不是自创。本地克隆可回读:
> /tmp/novel-study/{webnovel-writer, oh-story-claudecode, AI_NovelGenerator, chinese-novelist-skill}

| 机制 | 来源 | 证据文件 |
|---|---|---|
| 章事务 8 步 + 三重 gate(prewrite/precommit/postcommit) | webnovel-writer | skills/webnovel-write/SKILL.md Step 0-6、write-gate |
| 合同刷新 + runtime contracts + write-gate 状态机 | webnovel-writer | skills/webnovel-write/SKILL.md「准备:刷新合同树」 |
| 五段任务书(开篇委托/故事/人物/怎么写/收尾) | webnovel-writer | agents/context-agent.md §7 输出格式 |
| 数据权重(用户>章纲>设定>reasoning>commit>检索) | webnovel-writer | agents/context-agent.md §1 |
| 伏笔处理清单(剩余≤5或超期必处理,可选≤5条) | webnovel-writer | agents/context-agent.md §3.4 |
| 红线校验 6 项 | webnovel-writer | agents/context-agent.md §6 |
| 评审:子代理独跑、JSON schema、只跑一轮、blocking 定点修复或用户裁决 | webnovel-writer | skills/webnovel-write/SKILL.md Step 3;agents/reviewer.md |
| 润色顺序 非blocking→风格→排版→Anti-AI 终检,只改表达不改事实 | webnovel-writer | skills/webnovel-write/SKILL.md Step 4 |
| data-agent 三产物(履行/消歧/提取) + 自动判定 accepted/rejected | webnovel-writer | skills/webnovel-write/SKILL.md Step 5;agents/data-agent.md |
| 失败隔离(只补跑失败步骤)+ run-ledger 断点 | webnovel-writer | skills/webnovel-write/SKILL.md「失败恢复」「作者友好…恢复契约」 |
| 充分性闸门 7 项 | webnovel-writer | skills/webnovel-write/SKILL.md「充分性闸门」 |
| 四路上下文(最近3章结尾800字/渐进摘要/向量检索/下一章蓝图注入) | AI_NovelGenerator | novel_generator/chapter.py build_chapter_prompt + summarize_recent_chapters + get_relevant_context_from_vector_store |
| 细纲蓝图字段(role/purpose/suspense/foreshadow/twist/summary) | AI_NovelGenerator | novel_generator/chapter.py 读 Novel_directory.txt |
| 下一章注入(下章 title/role/suspense/foreshadow → 本文章末钩子) | AI_NovelGenerator | novel_generator/chapter.py next_chapter_info |
| 检索分类标注 [TECHNIQUE]/[SETTING]/[GENERAL] | AI_NovelGenerator | novel_generator/chapter.py |
| 单一权威追踪 _tracking-state.json,派生视图全部由工具重建 | oh-story | skills/story-long-write/scripts/tracking_commit.py §562-570 区段 |
| 续写状态卡固定 7 栏 ≤12KB | oh-story | skills/story-long-write/SKILL.md §400-425 |
| 逐章记录 ≤1536B/3072B 硬上限,只记影响连续性的变化 | oh-story | skills/story-long-write/SKILL.md §562 |
| 作者真相 vs 读者已知 双视图;三轨(客观事实/读者认知/揭示状态) | oh-story | skills/story-long-write/references/workflow-revision.md Step 4.3 |
| 大修级联 + expected_state_revision 并发控制 | oh-story | skills/story-long-write/references/workflow-revision.md Step 4 |
| 大纲安全审查(情绪发动机 + 主角护栏 + 可证伪降级检查) | oh-story | skills/story-long-write/SKILL.md §244 |
| 开书 3 层问答(L1 必答 3 问/L2 定制/L3 标题) | chinese-novelist | references/flows/phase1-layer1-core.md, phase2 |
| 规划 JSON(chapters: status/wordCount/retryCount)+ 二次确认 | chinese-novelist | references/flows/phase2-planning.md |
| 写作模式 serial/subagent-parallel/agent-teams | chinese-novelist | references/flows/phase2-planning.md、phase3-writing.md |
| 疯狂创作(禁打断,写完才报告)+ 自动校验修复 | chinese-novelist | SKILL.md Phase 3 |
| 三大黄金法则(展示而非讲述/冲突驱动/悬念承上启下) | chinese-novelist | SKILL.md |
| 自研(标注):状态卡脚本生成 | 简化自 oh-story 思想 | templates/tracking.py(非照抄其 1100 行实现) |