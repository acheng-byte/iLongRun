---
name: ilongrun
description: Run a persistent ILongRun mission with scheduler.json as the source of truth, planner-of-planners decomposition, optional fleet wave dispatch, recovery, and GPT-5.4 coding audit gates.
allowed-tools: "*"
user-invocable: true
disable-model-invocation: false
---

仅在用户明确要"长时间自主执行 / 分层编排 / 可恢复长跑 / 更完整交付"时使用本技能。

## 总原则

- 真值源是 `scheduler.json` + `workstreams/*/status.json`
- `plan.md` / `strategy.md` / `task-list-N.md` 都是投影，不是最终真值
- 先做 **Completeness Inference**，再决定模式、phase、wave、workstream
- 主代理只负责：策略、裁决、重规划、收尾
- 子规划代理负责：拆 phase / wave / task list
- 除 `Direct Lane` 外，不要让主代理亲自吞掉全部执行

## Coding 生命周期感知

当 `profile=coding` 时，执行遵循六阶段指导性生命周期：

```
DEFINE → PLAN → BUILD → VERIFY → REVIEW → SHIP
```

- **DEFINE**: mission.md 中明确目标、边界、假设；surfaced assumptions 必须列出
- **PLAN**: strategy.md 中采用垂直切片拆分，task-list-N.md 用 XS/S/M/L 大小标记
- **BUILD**: 遵循 TDD 纪律（Red-Green-Refactor）+ 增量实现（薄垂直切片）
- **VERIFY**: stop-the-line 规则——出错时先停再诊断，不继续推进
- **REVIEW**: 五轴审查（正确性/可读性/架构/安全性/性能）
- **SHIP**: 质量门控通过后才能 finalize

编码纪律详细规范见 `skills/ilongrun-coding/SKILL.md`（单一真值源）。
参考清单见 `references/` 目录。

## 常见合理化借口防御

> 识别并拒绝跳过纪律的借口：

| 借口 | 反驳 |
|------|------|
| "时间不够写测试" | 没测试的 debug 更费时间 |
| "这只是原型" | 原型经常变成产品代码 |
| "AI 生成的应该没问题" | AI 会自信地生成错误代码 |
| "改动太小不用审查" | 小改动大影响的案例数不胜数 |
| "之后再补安全检查" | 之后 = 永远不会 |

## Red Flags（出现时立即停下检查）

- 代码变更未经测试就标记 done
- 一个 workstream 混入了无关改动
- 捕获异常但不处理
- 硬编码的密钥或敏感数据
- 跳过 review 直接 finalize

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
   - Status（XS/S/M/L 大小标记）

3. 若当前 wave backend 已标记为 `fleet`：
   - 不要在主规划 pass 里亲自执行这些 fleet-tagged workstreams
   - 只完成策略、拆解、任务清单和状态落盘
   - 把执行留给 supervisor 的外部 `/fleet` dispatch

## coding 任务特殊规则

- finalize 前必须存在 `reviews/gpt54-final-review.md`
- 必须同步生成 `reviews/adjudication.md`
- 若 `must-fix` 非空，禁止 finalize complete
- 若当前会话不是 GPT-5.4，且只剩 final audit，应留下 checkpoint，等待 supervisor 拉起 GPT-5.4 终审
- coding workstream 的 executor 必须遵循 `ilongrun-coding` 技能中的纪律
- 代码审查可调用 `ILongRun Code Reviewer` 代理进行五轴审查

## 收尾要求

- gate 失败先 Recovery，再重规划，不要直接重开整局任务
- 如果 deliverables 与 verify 已满足，应尽快 finalize，不要无意义长跑

## Verification Checklist

任务完成前，主代理必须确认：

- [ ] 所有 required workstream 状态为 `done`
- [ ] scheduler.json 与投影文件已同步
- [ ] coding 任务：测试覆盖主要路径 + 边界
- [ ] coding 任务：无硬编码密钥或敏感数据
- [ ] coding 任务：代码审查 must-fix 为空
- [ ] GPT-5.4 终审报告存在且 must-fix 为空
- [ ] adjudication.md 已产出
