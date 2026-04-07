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
- coding 场景下的独立 review / audit / finalize 门禁
- evidence-based verify / completion score / delivery audit

从 **v0.6.0** 开始，`ilongrun-coding` 进一步升级为完整的 **Coding Swarm Protocol**：

- 有机器真值：`config/coding-protocol.jsonc`
- 有内部 playbooks：`skills/ilongrun-coding/*`
- 有 vendorized 方法库：`vendor/agent-skills/`
- 有独立 `phase-review` gate
- 有 `code / test-evidence / security` 三类专项评审

---

## v0.6.0 的核心升级

### 1. `ilongrun-coding` 不再只是“编码纪律文案”

现在它是一个完整协议层：

- 元技能入口：`skills/ilongrun-coding/SKILL.md`
- phase playbooks：
  - `phase-define.md`
  - `phase-plan.md`
  - `phase-build.md`
  - `phase-verify.md`
  - `phase-review.md`
  - `phase-ship.md`
  - `swarm-policy.md`
  - `js-ts-profile.md`

### 2. coding run 固定采用新生命周期

```text
phase-define
→ phase-plan
→ phase-build
→ phase-verify
→ phase-review
→ phase-audit
→ phase-finalize
```

不再让新的 coding run 复用旧的泛化 `phase-execution`。

### 3. coding 协议字段正式进入 scheduler

新增顶层字段：

- `codingProtocol`
- `swarmPolicy`
- `dependencyGraph`
- `reviewMatrix`

新增 workstream 字段：

- `skillPack`
- `swarmMode`
- `writeSet`
- `handoffArtifacts`
- `entryCriteria`
- `exitCriteria`
- `verificationClass`
- `reviewRequired`

### 4. 独立 `phase-review` gate 成为 finalize 前硬门禁

coding run 默认要求以下 review gate：

- `review-code`
- `review-test-evidence`
- `review-security`

并新增两个专项 agents：

- `agents/ilongrun-test-engineer.agent.md`
- `agents/ilongrun-security-auditor.agent.md`

### 5. build 波次才允许评估 `/fleet`

从 v0.6.0 开始：

- 仅 `phase-build` 可评估 `/fleet`
- `review / audit / finalize / git / release` 一律 `internal`
- 共享上游依赖、但彼此写集不冲突的 build slices，可以合法进入 fleet wave 评估

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

> 如果你要保留已有的自定义模型策略，请先备份 `~/.copilot-ilongrun/config/model-policy.jsonc`。

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

## 默认模型与配置文件

主配置文件：

```bash
~/.copilot-ilongrun/config/model-policy.jsonc
```

coding 协议文件：

```bash
~/.copilot-ilongrun/config/coding-protocol.jsonc
```

vendor 快照目录：

```bash
~/.copilot-ilongrun/vendor/agent-skills/
```

### 默认命令 → 模型映射

| 命令 | 默认模型 |
|------|----------|
| `ilongrun` / `status` / `prompt` / `resume` / `doctor` | `claude-sonnet-4.6` |
| `ilongrun-coding` | `claude-opus-4.6` |
| coding 最终终审 | `gpt-5.4` |

### 选模优先级

```text
--model > commandDefaults > skillDefaults > roleModels > fallback
```

---

## coding run 的本质是什么

从 v0.6.0 开始，coding run 不再只是“生成很多 task-list”。

它本质上是一个：

> **带依赖图、wave、write set、handoff 合同、review matrix 和 release blocker 的长运行编码协议。**

### 默认 coding phases

- `phase-define`：锁定目标、边界、假设、成功标准
- `phase-plan`：生成依赖图、wave 划分、worker mini-contract
- `phase-build`：按 slice 推进 build，并在必要时评估 `/fleet`
- `phase-verify`：固定测试/构建/接线/运行证据
- `phase-review`：执行 code / test-evidence / security 三类专项评审
- `phase-audit`：最终终审与 release blocker 裁决
- `phase-finalize`：完成态收尾、completion 报告、发布前闭环

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
- [发版说明 v0.6.0](./docs/发版说明-v0.6.0.md)
- [更新日志](./CHANGELOG.md)

---

## 开发与发布

当前版本：**0.6.0**

推荐发布流程：

1. 在功能分支完成实现与自测
2. 合并到 `main`
3. 打 tag：`v0.6.0`
4. 以 `docs/发版说明-v0.6.0.md` 作为 GitHub Release 正文

---

## 核心结论

iLongRun 的核心不是“让 Copilot 跑更久”，而是：

> **让长运行任务拥有清晰账本、明确 phase、可审计 gate、可恢复执行和真实交付判断。**
