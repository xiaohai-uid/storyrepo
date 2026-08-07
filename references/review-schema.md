# 评审 Schema(Step 5,子代理专用)

> 来源:webnovel-writer reviewer 输出协议。主流程禁止伪造评审 JSON。

## 输出(严格 JSON,不写文件、不评分、不口头总结)

```json
{
  "chapter": 152,
  "issues": [
    {
      "severity": "critical|high|medium|low",
      "category": "continuity|setting|character|timeline|ai_flavor|logic|pacing|other",
      "location": "第3段",
      "description": "一句话问题",
      "evidence": "原文引用或对照追踪事实",
      "fix_hint": "怎么修(不改剧情不破设定)",
      "blocking": true
    }
  ],
  "issues_count": 1,
  "blocking_count": 1,
  "has_blocking": true
}
```

## 门禁规则

- 任意 critical → blocking=true → 该章不得进 Step 6。
- blocking 处理:定点修复(Step 5 内部)或用户裁决(接受/手修/放弃)。**不重新调用评审**。
- 非 blocking → Step 6 润色消化。
- `--fast` 只查 setting/timeline/continuity 三类。
- `--minimal` 跳过评审,但必须写有效 review artifact(issues=[],review_skipped=true),Step 7 依赖它落库。

## 维度速查(映射 severity)

| 命中 | severity |
|---|---|
| 战力/称号/地名与设定或名册冲突 | critical |
| 信息差 S- 提前曝光 | critical |
| 合同必覆盖节点缺失 | critical |
| 角色 OOC(说话/行为不像) | high |
| 时间线冲突(倒计时跳跃/跨夜无过渡) | high |
| 一章未推进任何 P-/S- | medium(提醒) |
| Anti-AI 红线命中 | high |

## 评审后流程

评审 JSON → 落 工作区/评审报告/第NNN章.json + 审查报告.md(给人读的版本:问题清单+位置+建议,无原始 JSON)。