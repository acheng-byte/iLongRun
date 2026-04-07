---
name: ilongrun-coding
description: Use when an iLongRun mission is in profile=coding and needs the Coding Discipline Kernel with workspace isolation, task microcycles, fresh-evidence claims, and recovery guards.
allowed-tools: "*"
user-invocable: false
disable-model-invocation: false
---

仅当 iLongRun mission 的 `profile=coding` 时自动加载。
本技能是 **Coding Discipline Kernel 的协议入口**，不负责塞入所有细节，而是负责把方法学路由到对应 playbook。

- 用户入口：`ilongrun-coding` shell 命令
- 机器真值：`config/coding-protocol.jsonc`
- 方法学参考：`docs/ilongrun+superpowers.md`
- 上游快照：`vendor/agent-skills/`
- 内部 playbooks：当前目录下的 `phase-*.md`、`swarm-policy.md`、`workspace-isolation.md`、`task-microcycle.md`、`claim-verification.md`、`recovery-debug.md`、`skill-engineering.md`

## 协议定位

iLongRun coding 任务遵循：

```text
DEFINE → PLAN → BUILD → VERIFY → REVIEW → AUDIT → FINALIZE
```

这套协议同时约束：

- scheduler phase 的生成规则
- workstream 合同的最小字段集
- wave 并行边界
- review / audit / finalize gate
- resume / recovery 的最小恢复单元
- 方法学硬门禁（workspace isolation / microcycle / fresh evidence / root cause）

## 生命周期路由

### `phase-define`
读取：`phase-define.md`

- 锁定目标、边界、假设、技术画像、成功标准
- 形成可引用的 spec contract

### `phase-plan`
读取：`phase-plan.md` + `swarm-policy.md`

- 输出 dependency graph
- 划分 serial / swarm-wave / super-swarm
- 为每个 worker 写迷你需求文档合同

### `phase-build`
读取：`phase-build.md` + `workspace-isolation.md` + `task-microcycle.md` + `js-ts-profile.md`

- build 前先做 workspace isolation assessment
- 每个 build workstream 必须遵循固定 microcycle
- 只有 build wave 才可能进入 `/fleet`

### `phase-verify`
读取：`phase-verify.md` + `claim-verification.md`

- 检查测试、构建、接线、运行态证据
- 没有 fresh evidence，不得宣称完成
- Stop-the-Line：发现错误先停再诊断

### `phase-review`
读取：`phase-review.md`

- 默认包含 code / test-evidence / security 三类 review
- 缺任一 review 证据，不得视为 complete
- review gate 不能被 final audit 代替

### `phase-audit`
读取：`phase-ship.md`

- 只做最终终审、adjudication、release blocker 判断
- 若仍有 `must-fix`，必须回流前序 workstream

### `phase-finalize`
读取：`phase-ship.md` + `claim-verification.md`

- 只有 claim verification 完整时才允许完成声明
- 生成 completion report
- 清理 active pointer

## 方法学硬门禁

### workspace isolation
详见：`workspace-isolation.md`

- build 前必须先评估工作区隔离策略
- 不一定强制 worktree，但必须留下 assessment 结论

### task microcycle
详见：`task-microcycle.md`

每个 build workstream 最少遵循：

```text
spec-lock → red → verify-red → green → verify-green → self-review → spec-review → quality-review → handoff
```

### claim verification
详见：`claim-verification.md`

- 没有 fresh evidence，不得 claim done
- finalize 只认新鲜命令证据，不认“我感觉已经好了”

### recovery debug
详见：`recovery-debug.md`

- failed / blocked workstream 先写 root cause record
- 再允许 minimal fix
- 再返回主流程

## wave / backend 规则

- `phase-build` 才允许考虑 `fleet`
- `phase-review` / `phase-audit` / `phase-finalize` 一律 `internal`
- 涉及 Git / release / security gate / adjudication 的任务，一律 `internal`
- 多 worker 并行必须满足：
  - writeSet 不重叠
  - handoffArtifacts 明确
  - 依赖图明确
  - 可重试

## workstream 最小合同字段

每个 coding workstream 至少必须定义：

- Goal
- Inputs
- Outputs
- Owner Role / Owner Model
- Swarm Mode
- Write Set
- Handoff Artifacts
- Entry Criteria
- Exit Criteria
- Acceptance
- Verify
- Retry Budget
- Status
- Spec Ref
- Microcycle State
- Review Sequence
- Fresh Evidence
- Root Cause Record

任务描述必须像一份 **迷你需求文档**，禁止模糊描述。

## Skill Engineering

详见：`skill-engineering.md`

- description 只写 “Use when...” 触发条件
- 高频 skill 保持短、准、强交叉引用
- skill 自己也要通过 lint 与压力场景检查

## 机器可读约束

- 与本协议冲突的自由发挥，以 `config/coding-protocol.jsonc` 为准
- 空节统一写 `- None.`
- coding run 不允许绕过 `phase-review` 直接 complete
- `reviews/gpt54-final-review.md` 仍保留兼容文件名
