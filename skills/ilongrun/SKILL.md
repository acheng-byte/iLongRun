---
name: ilongrun
description: 当用户要启动可恢复、可长跑、分阶段编排并带最终交付门禁的 iLongRun 任务时使用。
allowed-tools: "*"
user-invocable: true
disable-model-invocation: false
---

仅在用户明确要“长时间自主执行 / 分层编排 / 可恢复长跑 / 更完整交付”时使用本技能。

## 总原则

- 真值源始终是 `scheduler.json` + `workstreams/*/status.json`
- `mission.md` / `strategy.md` / `plan.md` / `task-list-N.md` 都是投影，不是最终真值
- canonical run 目录只能是 `.copilot-ilongrun/runs/<run-id>/`
- 若环境变量里提供了 `LONGRUN_RUN_DIR` / `LONGRUN_SCHEDULER_PATH` / `LONGRUN_WORKSTREAMS_DIR`，必须把它们当作唯一真值路径
- 不要自己创建 `.copilot-ilongrun/<run-id>/`
- 先做 Completeness Inference，再决定模式、phase、wave、workstream
- 主代理负责：策略、裁决、重规划、收尾
- 执行代理负责：在既定 contract 内推进具体 workstream

## Coding 生命周期感知

当 `profile=coding` 时，执行遵循：

```text
DEFINE → PLAN → BUILD → VERIFY → REVIEW → AUDIT → FINALIZE
```

- **DEFINE**：先锁定目标、边界、假设与成功标准
- **PLAN**：先锁定 dependency graph、wave、write set、handoff
- **BUILD**：按切片推进，不直接吞掉所有实现任务
- **VERIFY**：发现问题先停，再补 fresh evidence
- **REVIEW**：code / test-evidence / security 三类 gate 独立存在
- **AUDIT**：最终终审与 adjudication 独立存在
- **FINALIZE**：只有 gate 收敛后才允许完成声明

编码纪律真值见 `skills/ilongrun-coding/SKILL.md` 与 `config/coding-protocol.jsonc`。

## 编排要求

1. `strategy.md` 必须解释：
   - 为什么选这个模式
   - 为什么这样拆 phase / wave / workstream
   - 哪些并行、哪些串行
   - 模型分配原因
   - 完成标准与阻塞标准
   - 降级路径
2. `task-list-N.md` 必须包含：
   - Goal
   - Inputs / Dependencies
   - Outputs
   - Owner Role / Owner Model
   - Acceptance
   - Verify
   - Retry Budget
   - Status
3. 若当前 wave backend 已标记为 `fleet`：
   - 主代理只负责策略、拆解、账本同步
   - 不要在主规划 pass 里亲自执行这些 `fleet` workstreams
   - 把执行留给 supervisor 的外部 `/fleet` dispatch

## coding 任务特殊规则

- `phase-build` 之外不要把 wave 交给 `fleet`
- finalize 前必须存在 `reviews/final-review.md`
- 必须同步生成 `reviews/adjudication.md`
- 若用户显式传入 `--model <slug>`，则 review / audit / finalize 也必须沿用该模型
- 若 `must-fix` 非空，禁止 finalize complete
- 若当前会话不是要求的最终终审模型，且只剩 final audit，应留下 checkpoint，等待 supervisor 拉起最终终审
- coding executor 必须遵循 `ilongrun-coding` 的方法学约束

## 收尾要求

- gate 失败先 recovery，再重规划，不要直接重开整局任务
- 若 deliverables 与 verify 已满足，应尽快 finalize，不要无意义长跑
- 若发现旧 run 为 legacy protocol，可做 best-effort reconcile，但不要假装新 gate 已天然满足

## Verification Checklist

- [ ] 所有 required workstream 状态与账本一致
- [ ] scheduler.json 与投影文件已同步
- [ ] coding 任务：review / audit / finalize gate 已收敛
- [ ] coding 任务：缺失 fresh evidence 时不允许 claim done
- [ ] coding 任务：blocked / failed workstream 已写 root cause record
- [ ] 最终终审报告存在且 must-fix 为空
- [ ] adjudication.md 已产出
