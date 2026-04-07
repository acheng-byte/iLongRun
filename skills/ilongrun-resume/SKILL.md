---
name: ilongrun-resume
description: Use when you need to resume an existing iLongRun run, converge only the unfinished gates, and avoid redoing work that already passed ledger checks.
allowed-tools: "*"
user-invocable: true
disable-model-invocation: false
---

恢复已有 run 时，优先最小化推进：

- 不要新建 run-id
- 只使用 canonical run 目录 `.copilot-ilongrun/runs/<run-id>/`
- 若环境变量里提供了 `LONGRUN_RUN_DIR` / `LONGRUN_SCHEDULER_PATH` / `LONGRUN_WORKSTREAMS_DIR`，必须把它们当作唯一真值路径
- 不要自己创建 `.copilot-ilongrun/<run-id>/`
- 不要重复已 complete 的 workstream
- 先读取 `scheduler.json`、`strategy.md`、`plan.md`、`task-list-N.md`
- 识别当前卡在哪个 gate：workstream / phase / coding review / finalize / methodology guard

特殊规则：
- 如果 supervisor context 明确说 “Perform pending final audit only”，则只执行 final audit
- 如果只是账本漂移，优先 reconcile + verify，不要重做执行任务
- 如果是 legacy coding run，允许 best-effort 迁移到 0.7.0 最小字段，但无法满足新 gate 时必须明确阻断
- 如果当前阻塞原因是 `freshEvidence` / `rootCauseRecord` / `reviewSequence`，先补 gate，再继续主流程
