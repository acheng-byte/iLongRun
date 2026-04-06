---
name: ilongrun-status
description: Inspect ILongRun scheduler state, phases, waves, workstreams, coding audit gate, fleet decisions, and next action.
allowed-tools: ["view", "glob", "grep", "bash"]
user-invocable: true
disable-model-invocation: false
---

这是只读技能。

读取顺序：
1. `scheduler.json`
2. `plan.md`
3. `strategy.md`
4. `task-list-N.md`
5. `reviews/gpt54-final-review.md`（若存在）
6. `reviews/adjudication.md`（若存在）
7. `COMPLETION.md`（若存在）

输出必须简洁说明：
- run id
- state / active phase / mode
- phase 完成情况
- wave backend（internal / fleet）
- workstream 完成度
- coding review gate 状态
- adjudication 状态
- 当前 blocker
- 下一步建议
