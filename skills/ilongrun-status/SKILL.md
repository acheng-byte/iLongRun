---
name: ilongrun-status
description: Use when the user wants a read-only Chinese status board for an iLongRun run, including phases, waves, workstreams, quality gates, and methodology guard state.
allowed-tools: ["view", "glob", "grep", "bash"]
user-invocable: true
disable-model-invocation: false
---

这是只读技能，不要修改任何文件。

## Resolve run

- 若 prompt 指定 run-id，就用它。
- 否则读取 `.copilot-ilongrun/state/latest-run-id`。
- 若不存在 run 目录，直接说明当前工作区还没有 ILongRun 状态。

## 读取顺序

按下面顺序读取，够用即停：

1. `scheduler.json`
2. `plan.md`
3. `strategy.md`
4. `task-list-N.md`
5. `workstreams/ws-*/status.json`（按需）
6. `reviews/gpt54-final-review.md`（若存在）
7. `reviews/adjudication.md`（若存在）
8. `COMPLETION.md`（若存在）
9. `journal.jsonl` 尾部（仅在需要解释错误 / 限流时）

## 输出要求

- 默认简体中文
- 默认显示 phase / wave / workstream / quality gate / methodology guard
- coding run 要额外展示：
  - workspace isolation
  - task microcycle
  - review sequence
  - claim verification
  - recovery root cause gate
- 不要夸大完成度；有 guard 未收敛时必须说清楚
