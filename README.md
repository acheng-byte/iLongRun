# iLongRun

> 让 GitHub Copilot CLI 从“单层 plan”升级为真正可恢复、可裁决、可长跑的 **Planner-of-Planners 蜂群编排内核**。

开发者：**zscc.in / 知识船仓**

---

## iLongRun 是什么

iLongRun 不是一个 prompt 模板集合，而是一个围绕 Copilot CLI 构建的 **长运行任务编排内核**。

它的核心真值是：

```text
scheduler.json + workstreams/*/status.json
```

在这个真值之上，iLongRun 提供：

- `mission.md / strategy.md / plan.md / task-list-N.md` 的多层投影
- `Mission Governor + Planner-of-Planners + Ledger Syncer + Recovery + Audit` 的分层角色体系
- `/fleet` 波次级后端分发与自动降级
- coding 场景下独立的 review / audit / finalize 门禁
- evidence-based verify / completion score / delivery audit

从 **v0.7.0** 开始，`ilongrun-coding` 进一步升级为带 Superpowers 方法学强化层的 **Coding Discipline Kernel**：

- 保留原有蜂群骨架：`serial / swarm-wave / super-swarm`
- 保留原有生命周期：`define → plan → build → verify → review → audit → finalize`
- 新增方法学真值：`methodologyOverlay / workspaceIsolationPolicy / taskMicrocycle / claimVerificationPolicy / debugPolicy / skillEngineeringPolicy`
- 新增账本字段：`workspaceIsolation / phaseGuards / claimVerification`
- 新增 workstream 字段：`specRef / microcycleState / reviewSequence / freshEvidence / rootCauseRecord`
- finalize 前强制检查 fresh evidence
- recovery 前强制要求 root cause record
- skills 本身也进入 lint + pressure scenario 检查链路

---

## v0.7.0 的核心升级

### 1. `ilongrun-coding` 从 Coding Swarm Protocol 升级为 Coding Discipline Kernel

这次不是推翻旧体系，而是在原有蜂群编排之上加上一层更科学的方法学纪律：

- **Spec before execution**：先定义再执行
- **Isolation before mutation**：先评估工作区隔离再动手
- **Microcycle per task**：每个 build workstream 都要走固定小闭环
- **Evidence before claims**：没有 fresh evidence 不得 claim done
- **Root cause before fix**：没有根因记录不得直接修

### 2. coding 协议真值继续升级

`config/coding-protocol.jsonc` 现在同时定义：

- coding 生命周期
- swarm 策略
- review matrix
- JS/TS 优先画像
- methodology overlay
- workspace isolation policy
- task microcycle
- claim verification policy
- debug policy
- skill engineering policy

### 3. scheduler / workstream 账本升级

scheduler 顶层新增：

- `workspaceIsolation`
- `phaseGuards`
- `claimVerification`

workstream 新增：

- `specRef`
- `microcycleState`
- `reviewSequence`
- `freshEvidence`
- `rootCauseRecord`

### 4. finalize / recovery 更严格

- finalize 缺 fresh evidence 时直接阻断
- failed / blocked workstream 缺 root cause record 时直接阻断 recovery
- build workstream 未完成 microcycle / review sequence 时，不能算完整完成

### 5. skill engineering 正式进入协议层

- 顶层 skill 的 frontmatter description 改成 `Use when...`
- `ilongrun-coding` 新增：
  - `workspace-isolation.md`
  - `task-microcycle.md`
  - `claim-verification.md`
  - `recovery-debug.md`
  - `skill-engineering.md`
- 新增 `lint_ilongrun_skills.py`
- 新增压力场景参考：
  - `references/skill-engineering-checklist.md`
  - `references/skill-pressure-scenarios.md`

---

## 一键安装（推荐）

```bash
curl -fsSL https://raw.githubusercontent.com/izscc/iLongRun/main/install.sh | bash
```

安装完成后建议先检查：

```bash
command -v ilongrun
command -v ilongrun-coding
ilongrun-doctor --refresh-model-cache
ilongrun-doctor --notify-test
```

### 当前安装器会做什么

- 先彻底清理旧 `ilongrun / longrun / copilot-mission-control` 安装残留
- 安装 shell launchers、skills、agents、helpers
- 安装 `~/.copilot-ilongrun/config/model-policy.jsonc`
- 安装 `~/.copilot-ilongrun/config/coding-protocol.jsonc`
- 安装 `~/.copilot-ilongrun/vendor/agent-skills/`
- 输出中文安装看板与 doctor 看板
- 在安装看板中显示当前版本号

---

## 30 秒快速上手

### 1）直接启动长跑

```bash
ilongrun "修复登录流程并补充测试，最后整理交付说明"
```

### 2）显式启动 coding 长跑

```bash
ilongrun-coding "实现一个 TypeScript 模块，补测试，完成 review gate 和最终终审"
```

### 3）查看状态

```bash
ilongrun-status latest
```

### 4）继续上一次长跑

```bash
ilongrun-resume latest
```

### 5）只看策略骨架

```bash
ilongrun-prompt "调研 3 个 AI Agent 编排方案，并输出中文对比结论"
```

---

## 核心命令

```bash
ilongrun
ilongrun-coding
ilongrun-prompt
ilongrun-resume
ilongrun-status
ilongrun-doctor
copilot-ilongrun
```

其中：

- `ilongrun`：推荐通用入口，自动推断 profile
- `ilongrun-coding`：显式 coding 入口，强制 `profile=coding`
- `copilot-ilongrun`：底层兼容 / 高级入口
- `ilongrun-doctor`：检查命令入口、登录、模型缓存、自检、`/fleet` 能力、coding protocol bundle

---

## coding run 的本质是什么

从 v0.7.0 开始，coding run 不再只是“带 review gate 的 coding swarm”。

它本质上是一个：

> **带依赖图、wave、write set、handoff 合同、方法学门禁、review matrix 和 release blocker 的长运行编码协议内核。**

### 默认 coding phases

- `phase-define`：锁定目标、边界、假设、成功标准
- `phase-plan`：生成依赖图、wave 划分、worker mini-contract
- `phase-build`：按 slice 推进 build，并在必要时评估 `/fleet`
- `phase-verify`：固定测试 / 构建 / 接线 / 运行证据
- `phase-review`：执行 code / test-evidence / security 三类专项评审
- `phase-audit`：最终终审与 release blocker 裁决
- `phase-finalize`：完成态收尾、completion 报告、发布前闭环

### 0.7.0 新增的关键方法学门禁

- `workspaceIsolation`
- `taskMicrocycle`
- `claimVerification`
- `rootCauseBeforeFix`

### review gate 默认要求

- `review-code`
- `review-test-evidence`
- `review-security`

即使某项不适用，也应该留下显式结论，而不是静默跳过。

---

## `/fleet` 在 iLongRun 里的位置

`/fleet` 只是某个 wave 的执行后端，不是状态真值源。

只有满足这些条件才会自动尝试：

- 当前 wave 的 workstreams 彼此不互相依赖
- 写集不冲突
- phase 允许外部分发（coding 仅限 build）
- 降级回 internal 后仍可恢复

运行态证据会进入：

- `runtime.fleetCapability`
- `runtime.fleetDispatch`

status / verify / completion score 都会读取这些证据。

---

## 工作区目录

每次运行都会在当前工作区生成：

```text
.copilot-ilongrun/
```

关键文件：

- `mission.md`
- `strategy.md`
- `plan.md`
- `scheduler.json`
- `projection-sync.jsonl`
- `task-list-N.md`
- `workstreams/ws-*/`
- `reviews/gpt54-final-review.md`
- `reviews/adjudication.md`
- `reviews/delivery-audit.md`
- `COMPLETION.md`

---

## 文档

- [快速开始](./docs/快速开始.md)
- [架构与运行机制](./docs/架构与运行机制.md)
- [Superpowers 研究方案](./docs/ilongrun+superpowers.md)
- [发版说明 v0.7.0](./docs/发版说明-v0.7.0.md)
- [更新日志](./CHANGELOG.md)

---

## 开发与发布

当前版本：**0.7.0**

推荐发布流程：

1. 在功能分支完成实现与自测
2. 合并到 `main`
3. 打 tag：`v0.7.0`
4. 以 `docs/发版说明-v0.7.0.md` 作为 GitHub Release 正文

---

## 核心结论

iLongRun 的核心不是“让 Copilot 跑更久”，而是：

> **让长运行任务拥有清晰账本、明确 phase、可审计 gate、可恢复执行和真实交付判断。**
