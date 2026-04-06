---
name: ilongrun-prompt
description: Generate an ILongRun mission prompt skeleton with completeness inference, planner-of-planners decomposition, backend decisions, and final-audit reminders for coding tasks.
allowed-tools: ["view", "glob", "grep"]
user-invocable: true
disable-model-invocation: false
---

当用户想先看策略骨架，而不是立即启动时使用。

输出必须包含：
- 任务画像
- 推荐模式：Direct Lane / Wave Swarm / Super Swarm / Fleet Governor / Sentinel Watch
- 模式选择理由
- 建议 phase / wave / workstream 数量
- 哪些适合 `internal`，哪些未来可尝试 `/fleet`
- coding 任务的最终终审提醒
- 推荐执行命令：`ilongrun "..."`
