---
name: ilongrun-resume
description: Resume an existing ILongRun run from .copilot-ilongrun, converge pending workstreams and gates, and avoid redoing completed work.
allowed-tools: "*"
user-invocable: true
disable-model-invocation: false
---

恢复已有 run 时，优先最小化推进：

- 不要新建 run-id
- 不要重复已 complete 的 workstream
- 先读取 `scheduler.json`、`strategy.md`、`plan.md`、`task-list-N.md`
- 识别当前卡在哪个 gate：workstream / phase / coding review / finalize

特殊规则：
- 如果 supervisor context 明确说“Perform pending GPT-5.4 final audit only”，则只执行 final audit：
  - 读取现有代码/结果
  - 用 GPT-5.4 产出 `reviews/gpt54-final-review.md`
  - 列出 `Must-fix / Suggested fixes / Residual risks`
  - 不要擅自重跑全量工作流
- 如果只是账本漂移，优先 reconcile + verify，不要重做执行任务
- 如果收到 fleet 后处理上下文，则只负责 fleet 之后的整合、验证和后续 gate 推进
