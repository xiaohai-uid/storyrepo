# 追踪系统(单一权威 + 双视图)

> 来源:oh-story tracking_commit.py 的事务模型(简化实现,自研代码,机制照抄)。
> 铁律:`追踪/_tracking-state.json` 是唯一结构化权威,派生视图全部由 `tracking.py` 重建,程序不反向解析 Markdown,禁止手改派生。

## 1. 状态文件 `_tracking-state.json`(节选字段)

```json
{
  "spec": 1,
  "book": "零界道种",
  "imported_through_chapter": 152,
  "state_revision": 43,
  "chapters": {"152": {"status":"committed","words":3120,"volume":5}},
  "promises": {"P-031": {"status":"open","opened_ch":112,"last_advance_ch":149,"due_ch":160}},
  "info_gaps": {"S-007": {"revealed":false,"planned_reveal_ch":210}},
  "timeline": [{"ch":152,"event":"...","kind":"fact"}],
  "reader_knowledge": {"version":43},
  "entity_states": {"林川": {"location":"北境","goal":"...","known_by_reader":false}}
}
```

## 2. 逐章记录(第NNN.md,≤1.5K 目标/3K 硬限)

只许六类紧密变化:①result(本章结果)②角色变化 ③伏笔变化(±/~)④时间与揭示 ⑤约束(能力上限/规则)⑥下一章承诺。**不重放正文、不存长摘要。**

## 3. 命令

```bash
python3 scripts/tracking.py init                 # 建仓(幂等)
python3 scripts/tracking.py commit --chapter 152 --facts facts.json [--mode revision]
python3 scripts/tracking.py check                 # 全绿才能写下一章
python3 scripts/tracking.py card                  # 重生成状态卡 7 栏(≤12KB)
```

- `commit`:读 `expected_state_revision` → 合并 facts → 重建全部派生视图 → revision+1。冲突(状态已变)则拒绝,需重读重构,禁止强写。
- `check`:状态有效、逐章连续未超限、派生一致、状态卡恰好 7 栏且 ≤12288B。

## 4. 大修级联(`--mode revision`,回炉专用)

1. 备份原稿;
2. 重算受影响章增量(旧版本中未来仍有效的结果才保留,被推翻结论删除);
3. 伏笔当前值:从 X 章查到最后已写 M 章,重提交「截至 M 章的当前状态」;删除线用 action=delete,后文仍引用时列为冲突;
4. **三轨合并**:客观事实 / 读者截至 M 章的认知 / 实际揭示状态。读者视图由事件合并推演,禁止手改;
5. 核心角色快照:按 身份/位置/目标/能力/关系/已知信息/未结事项 整份重算;
6. `expected_state_revision` 并发控制;失败保留事务 JSON 重跑同一 commit;
7. check 全绿后才许写下一章;输出后续影响清单(changed X → 后续章节需同步检查)。

## 5. 状态卡 7 栏(派生重建,固定顺序,防手改)

1 当前卷/进度 2 下一章合同 3 活跃伏笔(⏰ 超期标) 4 核心角色状态 5 最近结尾(≤3) 6 未曝光信息差 7 风格锚点。
共识:正文手改 → 只重跑该章 commit;章节删除 → action=action;绝不走"顺手删派生"。