---
name: ilongrun
description: Run a persistent ILongRun mission with scheduler.json as the source of truth, planner-of-planners decomposition, optional fleet wave dispatch, recovery, and GPT-5.4 coding audit gates.
allowed-tools: "*"
user-invocable: true
disable-model-invocation: false
---

仅在用户明确要“长时间自主执行 / 分层编排 / 可恢复长跑 / 更完整交付”时使用本技能。

## 总原则

- 真值源是 `scheduler.json` + `workstreams/*/status.json`
- `plan.md` / `strategy.md` / `task-list-N.md` 都是投影，不是最终真值
- 先做 **Completeness Inference**，再决定模式、phase、wave、workstream
- 主代理只负责：策略、裁决、重规划、收尾
- 子规划代理负责：拆 phase / wave / task list
- 除 `Direct Lane` 外，不要让主代理亲自吞掉全部执行

## 必须优先使用的 helpers

- `prepare_ilongrun_run.py`
- `write_ilongrun_scheduler.py`
- `reconcile_ilongrun_run.py`
- `verify_ilongrun_run.py`
- `finalize_ilongrun_run.py`

## 固定结构要求

初始化后必须确保至少存在：
- `mission.md`
- `strategy.md`
- `plan.md`
- `scheduler.json`
- 至少一个 `task-list-N.md`
- `workstreams/ws-*/brief.md`
- `workstreams/ws-*/status.json`

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
   - 不要在主规划 pass 里亲自执行这些 fleet-tagged workstreams
   - 只完成策略、拆解、任务清单和状态落盘
   - 把执行留给 supervisor 的外部 `/fleet` dispatch

## coding 任务特殊规则

- finalize 前必须存在 `reviews/gpt54-final-review.md`
- 必须同步生成 `reviews/adjudication.md`
- 若 `must-fix` 非空，禁止 finalize complete
- 若当前会话不是 GPT-5.4，且只剩 final audit，应留下 checkpoint，等待 supervisor 拉起 GPT-5.4 终审

## 收尾要求

- gate 失败先 Recovery，再重规划，不要直接重开整局任务
- 如果 deliverables 与 verify 已满足，应尽快 finalize，不要无意义长跑
