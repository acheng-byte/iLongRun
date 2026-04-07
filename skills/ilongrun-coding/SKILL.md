---
name: ilongrun-coding
description: iLongRun Coding Swarm Protocol。为 coding 任务提供可长跑、可恢复、可审计的生命周期编排与工程纪律真值。
allowed-tools: "*"
user-invocable: false
disable-model-invocation: false
---

仅当 iLongRun mission 的 `profile=coding` 时自动加载。
本技能是 **Coding Swarm Protocol 的协议入口**，而不是单个大而全的纪律说明书。

- 用户入口：`ilongrun-coding` shell 命令
- 机器真值：`config/coding-protocol.jsonc`
- 上游快照：`vendor/agent-skills/`
- 内部 playbooks：当前目录下的 `phase-*.md`、`swarm-policy.md`、`js-ts-profile.md`

---

## 0. 协议定位

iLongRun coding 任务遵循：

```text
DEFINE → PLAN → BUILD → VERIFY → REVIEW → AUDIT → FINALIZE
```

这不是纯文案分层，而是：

- scheduler phase 的生成规则
- workstream 合同的最小字段集
- wave 并行边界
- review / audit / release gate
- resume / recovery 的最小恢复单元

---

## 1. 入口职责

当本 skill 生效时，主代理必须：

1. 读取 `config/coding-protocol.jsonc`
2. 只在 `profile=coding` 下应用本协议
3. 把任务拆成 **协调器 + worker + 依赖图 + 波次** 的蜂群模式
4. 让 scheduler/workstream 的字段与协议保持一致
5. 把纪律落实到 phase，而不是混成一团

---

## 2. 生命周期路由

### `phase-define`
读取：`phase-define.md`

- 明确目标、边界、约束、假设
- 写出 surfaced assumptions
- 识别语言/框架/测试/构建工具
- 输出最小可行依赖图草案

### `phase-plan`
读取：`phase-plan.md`

- 输出 dependency graph
- 划分 swarm wave / super swarm / serial
- 每个 workstream 必须带迷你需求文档合同
- 给出 handoff artifacts 与 writeSet

### `phase-build`
读取：`phase-build.md` + `js-ts-profile.md`

- 遵循 TDD、增量实现、薄垂直切片
- foundation → implementation → integration
- 只有 build wave 才可能进入 `/fleet`

### `phase-verify`
读取：`phase-verify.md`

- 检查测试、构建、接线、运行态证据
- Stop-the-Line：发现错误先停再诊断
- 对 fake completion / unwired module / placeholder provider 保持高敏感

### `phase-review`
读取：`phase-review.md`

- 默认包含三类 review：code / test-evidence / security
- 缺任一 review 证据，不得视为 complete
- review gate 不能被 final audit 代替

### `phase-audit`
读取：`phase-ship.md`

- 只做最终终审、adjudication、release blocker 判断
- 若仍有 `must-fix`，必须回流前序 workstream

### `phase-finalize`
读取：`phase-ship.md`

- 生成 completion report
- 清理 active pointer
- 确认 release 就绪

---

## 3. wave / backend 规则

蜂群规则详见：`swarm-policy.md`

硬约束：

- `phase-build` 才允许考虑 `fleet`
- `phase-review` / `phase-audit` / `phase-finalize` 一律 `internal`
- 涉及 Git / release / security gate / adjudication 的任务，一律 `internal`
- 多 worker 并行必须满足：
  - writeSet 不重叠
  - handoffArtifacts 明确
  - 依赖图明确
  - 可重试

---

## 4. workstream 最小合同字段

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

任务描述必须像一份 **迷你需求文档**，禁止模糊描述。

---

## 5. JS/TS 优先画像

若检测到 Node / JS / TS / React / Next / Vite：

- 优先关注 import graph / entry wiring
- evidence 必须至少包含：test + build + runtime / integration 之一
- review 时额外检查：
  - 未接主链模块
  - 双份核心模块
  - noop / placeholder provider
  - web 输入边界与 secret handling

详见：`js-ts-profile.md`

---

## 6. 恢复与裁决

- resume 只补当前 gate，不重做已通过 gate
- recovery 优先最小修复，不整局重开
- must-fix 只允许通过返工 workstream 清零，不能口头跳过
- finalize 之前必须满足：
  - review gate 完整
  - final audit 存在
  - adjudication 已写入
  - verification 通过

---

## 7. 机器可读约束

- 任何与本协议冲突的自由发挥，都以 `config/coding-protocol.jsonc` 为准
- 空节统一写 `- None.`
- coding run 不允许绕过 `phase-review` 直接 complete
- `reviews/gpt54-final-review.md` 仍保留兼容文件名
