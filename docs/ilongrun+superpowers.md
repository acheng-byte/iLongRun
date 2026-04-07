# iLongRun × Superpowers：面向 `ilongrun-coding` 的方法论升级研究

> 结论先行：**iLongRun 适合吸收 `obra/superpowers` 的方法论层，但不适合被替换为 Superpowers 式会话框架。最佳路线是对 `ilongrun-coding` 做“选择性深适配”，把其更科学的 skill discipline、task microcycle 与 verification 哲学，嫁接到 iLongRun 现有的账本化长运行编排内核之上。**

- 研究时间：2026-04-07
- 研究范围：仅覆盖 `ilongrun-coding`
- 当前结论：建议作为 **v0.7.0 方法论升级方向**，不回补 `v0.6.0`

---

## 1. 研究对象与当前基线

本次研究不是抽象对比，而是拿 iLongRun 当前已经落地的 coding 协议，与 Superpowers 的技能哲学逐项做映射。

### iLongRun 当前基线

当前 iLongRun 在 coding 场景的核心基线如下：

- 机器真值：`/Users/zscc.in/Desktop/AI/ilongrun-V2/ilongrun-repo/config/coding-protocol.jsonc`
- coding 元技能：`/Users/zscc.in/Desktop/AI/ilongrun-V2/ilongrun-repo/skills/ilongrun-coding/SKILL.md`
- 架构说明：`/Users/zscc.in/Desktop/AI/ilongrun-V2/ilongrun-repo/docs/架构与运行机制.md`

从这些文件可以确认，iLongRun v0.6.0 已经形成以下能力：

- 以 `scheduler.json + workstreams/*/status.json` 作为真值账本
- coding 采用固定生命周期：`phase-define → phase-plan → phase-build → phase-verify → phase-review → phase-audit → phase-finalize`
- coding protocol 已经收敛为机器配置，而不是散落 prompt
- 具备 review / audit / finalize 三层质量门禁
- 支持 `/fleet` 作为 build wave 的执行后端，但不是协议真值本身

### Superpowers 研究对象

本次重点研究这些一手来源：

- [Superpowers README](https://github.com/obra/superpowers)
- [using-superpowers](https://raw.githubusercontent.com/obra/superpowers/main/skills/using-superpowers/SKILL.md)
- [brainstorming](https://raw.githubusercontent.com/obra/superpowers/main/skills/brainstorming/SKILL.md)
- [writing-plans](https://raw.githubusercontent.com/obra/superpowers/main/skills/writing-plans/SKILL.md)
- [using-git-worktrees](https://raw.githubusercontent.com/obra/superpowers/main/skills/using-git-worktrees/SKILL.md)
- [subagent-driven-development](https://raw.githubusercontent.com/obra/superpowers/main/skills/subagent-driven-development/SKILL.md)
- [requesting-code-review](https://raw.githubusercontent.com/obra/superpowers/main/skills/requesting-code-review/SKILL.md)
- [test-driven-development](https://raw.githubusercontent.com/obra/superpowers/main/skills/test-driven-development/SKILL.md)
- [systematic-debugging](https://raw.githubusercontent.com/obra/superpowers/main/skills/systematic-debugging/SKILL.md)
- [verification-before-completion](https://raw.githubusercontent.com/obra/superpowers/main/skills/verification-before-completion/SKILL.md)
- [writing-skills](https://raw.githubusercontent.com/obra/superpowers/main/skills/writing-skills/SKILL.md)

---

## 2. 结论摘要：为什么不是直接照搬

### 2.1 Adopt：方法论可以深度借鉴

Superpowers 真正有价值的，不是“技能数量多”，而是它把软件开发过程压缩成了一套**强纪律、低歧义、可重复的 agent workflow**。其优势主要体现在：

1. **流程先于动作**：先 skill check，再提问，再设计，再计划，再执行
2. **任务先于编码**：没有经过 spec / plan 的实现被视为不可靠
3. **证据先于完成**：没有 fresh verification evidence，不允许 claim done
4. **根因先于修复**：没有 root cause investigation，不允许 fix
5. **技能本身也要测试**：把 process documentation 当作需要 RED/GREEN/REFACTOR 的对象

这些原则与 iLongRun 的长运行目标高度兼容，而且能弥补 iLongRun 当前在“工程过程细粒度约束”上的不足。

### 2.2 Reject：框架级替换不适合 iLongRun

不建议把 iLongRun 改造成 Superpowers 风格的纯 session 技能运行器，理由有三：

1. **真值层不同**
   - Superpowers 的主强项是 skill-triggered workflow
   - iLongRun 的主强项是 scheduler/workstream ledger、resume、recovery、adjudication
   - 前者偏会话控制；后者偏任务编排内核

2. **时间尺度不同**
   - Superpowers 天然适合一轮会话内的强纪律工程推进
   - iLongRun 强在跨 session、跨中断、跨 phase 的账本连续性

3. **系统职责不同**
   - Superpowers 倾向用 skill 和 hook 规范“此刻该怎么做”
   - iLongRun 倾向用 scheduler 和 gate 规范“系统当前处于什么状态、下一步允许什么”

**结论：Superpowers 适合成为 iLongRun 的方法学强化层，不适合成为新的调度真值层。**

---

## 3. Superpowers 核心哲学拆解

只提炼可迁移部分，不做全文复述。

### 3.1 Trigger-first

`using-superpowers` 的核心观念是：**如果有 1% 概率某个 skill 适用，也必须先检查 skill。**

这背后的本质不是“迷信技能”，而是防止 agent 在没有 process guard 的情况下直接行动。对于 iLongRun，这意味着：

- `phase-define` 和 `phase-plan` 需要比现在更强的前置约束
- coding 任务不能只因为用户“直接让它改代码”就跳过 define/plan discipline

### 3.2 Process skills first

Superpowers 强调：**流程型 skill 优先于实现型 skill。**

比如：

- 创造新功能前先 `brainstorming`
- 修 bug 前先 `systematic-debugging`
- 执行计划前先 `writing-plans`

这对 iLongRun 的启发是：

- `phase-define` 不能只是“写需求摘要”
- `phase-plan` 不能只是“拆任务”
- recovery 不能只是“修补失败 workstream”，而要先进入调试过程

### 3.3 Rigid vs Flexible

Superpowers 把技能大体分为两类：

- **Rigid discipline**：如 TDD、debugging、verification-before-completion，不能随意适配
- **Flexible pattern**：如架构设计、技能写法，可以按场景裁剪

这给 iLongRun 的启发是：

- coding protocol 里也应区分“硬性门禁”和“可裁剪建议”
- 不是所有 playbook 都等价
- `review / verification / debugging` 更适合做 protocol-level guard，而不是仅作为 prompt 建议

### 3.4 Skill TDD / Pressure Scenario

`writing-skills` 的核心价值极高：**技能不是写完就算，而是要先观察 agent 在无 skill 时如何失败，再写 skill 去抵消这些失败模式。**

它要求：

- 无 failing test first，不要新增 skill
- description 只写触发条件，不写流程摘要
- skill 需要 pressure scenario 进行抗 rationalization 测试
- 需要记录 agent 常见借口并逐步封堵

对 iLongRun 的含义是：

- `skills/ilongrun*` 不能只靠“我觉得写得清楚”
- 后续需要 skill lint + skill test methodology
- coding 协议之外，skill 工程本身应该变成一等公民

### 3.5 Evidence over claims

`verification-before-completion` 与 README 的 philosophy 高度一致：**没有新鲜验证证据，就不能宣称完成。**

对于 iLongRun，这是最值得硬接进协议层的原则之一。因为 iLongRun 目前已经有 verify / audit / completion score，只差把“fresh verification evidence”做成更明确的 claim gate。

### 3.6 Root cause before fix

`systematic-debugging` 的贡献，不是单纯教调试，而是把“修 bug 前先找到根因”提升为工程纪律。这非常适合 iLongRun 的 recovery 场景：

- 失败的 workstream 目前可以被 recovery 补救
- 但缺少统一的 root-cause record 语义
- 这会导致“修了但不知道为什么失败”的漂移风险

---

## 4. Skill 方法论拆解：对 iLongRun 最有价值的部分

### 4.1 description 只写“何时使用”

`writing-skills` 明确反对在 frontmatter description 中概述 workflow，而要求 description 只回答一个问题：**什么时候该加载这个 skill？**

这是一个非常值得吸收的点。原因是：

- 现在 iLongRun 的一些 skill 描述仍偏“功能总结型”
- 这容易让模型停留在描述层，而不是进入技能正文
- 对于 `ilongrun-coding` 这种协议 skill，触发条件比流程摘要更重要

### 4.2 token budget / cross-reference discipline

Superpowers 对“常驻高频 skill 应短小、重细节放 supporting file、跨 skill 用明确引用而不是把所有内容复制一遍”非常敏感。

iLongRun 当前已经做了一步正确动作：

- `skills/ilongrun-coding/SKILL.md` 作为元技能入口
- phase 细节拆到独立 playbook

但仍可进一步优化：

- 高层 skill 更像 router，不重复 phase 细节
- 高频 skill 的 description/frontmatter 更短更精准
- phase 文档之间采用稳定的 cross-reference 语义

### 4.3 subagent context isolation

`subagent-driven-development` 的一个核心哲学是：**子代理不继承主会话上下文，而是只拿到完成任务所需的精确上下文。**

这与 iLongRun 的 workstream contract 非常契合。下一阶段最值得做的，不是照搬 subagent prompt，而是让 iLongRun 的 workstream contract 更接近 Superpowers 的精确 handoff：

- 明确目标
- 精确上下文
- 明确文件范围
- 明确验证命令
- 明确 review 顺序

### 4.4 per-task review loop

Superpowers 的实现哲学不是“做完一波统一 review”，而是：

- implementer 完成
- spec reviewer 检查是否符合计划
- code quality reviewer 检查实现质量
- 有问题就回环

对 iLongRun 的启发是：

- `phase-review` 作为总 gate 仍然保留
- 但在 `phase-build` 内部，task/workstream 也可以引入更轻量的 review sequence
- 这样能把问题尽早截住，而不是全部堆到 phase-review 再爆发

### 4.5 worktree-first isolation

`using-git-worktrees` 的原则是：**在多代理/并行执行前，先确保隔离的工作区和干净基线。**

这点对 iLongRun 尤其重要，因为：

- iLongRun 已支持 wave/fleet
- 并行写集冲突是长运行系统的固有风险
- 但当前协议还没有把 workspace isolation 提升为明确 gate

---

## 5. 与 iLongRun 的兼容点 / 冲突点

### 5.1 高兼容点

| Superpowers 原则 | 与 iLongRun 的关系 | 建议 |
|---|---|---|
| Spec before execution | 与 `phase-define`/`phase-plan` 高度兼容 | 直接强化 |
| Evidence before claims | 与 verify/audit/finalize 高度兼容 | 直接硬接 |
| Root cause before fix | 与 recovery 高兼容 | 增加 root cause record |
| Task-level review loop | 与现有 review gate 兼容 | 做成 build 内环 |
| Skill TDD | 与 iLongRun skills 体系兼容 | 建立 skill engineering 标准 |

### 5.2 中度冲突点

| Superpowers 机制 | 冲突来源 | 处理方式 |
|---|---|---|
| 会话优先 skill orchestration | iLongRun 以 scheduler/gate 为真值 | 仅借鉴 discipline，不替换账本 |
| 同 session 下的 subagent 细粒度执行 | iLongRun 更偏 phase/wave 调度 | 只迁移 worker microcycle 模式 |
| worktree 默认成为执行前置 | iLongRun 不一定总在 git 项目下运行 | 改成 optional workspace isolation gate |

### 5.3 明确不兼容路线

以下内容不建议采用：

- 不整包 vendorize `obra/superpowers`
- 不让 `using-superpowers` 成为 iLongRun 总入口
- 不把 iLongRun 的 phase/gate 退化为单纯会话 checklist
- 不把所有 coding task 强制改成 Superpowers 原版文件布局或 docs 路径

---

## 6. 技能映射矩阵：Superpowers → iLongRun coding protocol

> 核心判断：**Superpowers 提供的是方法学强化层，不是新的 scheduler 真值层。**

| Superpowers skill | 当前作用 | iLongRun 对应位置 | 推荐适配方式 |
|---|---|---|---|
| `brainstorming` | 先设计、先澄清、先批准 | `phase-define` | 把 define 强化成 spec gate，而不是摘要阶段 |
| `writing-plans` | 把设计转成可执行任务计划 | `phase-plan` | 把 plan 强化成 implementation-contract gate |
| `using-git-worktrees` | 开工前做隔离工作区与干净基线 | `phase-build` 之前 | 新增 workspace isolation gate |
| `subagent-driven-development` | 每 task 一个 implementer + review loop | build wave 内部 | 引入 worker microcycle |
| `requesting-code-review` | 每 task / major feature 后及时 review | `phase-review` + build 内部 | 增加 review sequence，提前捕获偏差 |
| `verification-before-completion` | 无 fresh evidence 不得 claim 完成 | `phase-verify` + `phase-finalize` | 新增 claim verification policy |
| `systematic-debugging` | 修复前先做根因调查 | recovery / failed workstream | 新增 root cause record gate |
| `writing-skills` | 用 TDD 心态写 skill | iLongRun skill 工程 | 建 skill lint / skill test 标准 |

---

## 7. 最佳适配方案（coding-only）

本次建议只改 `ilongrun-coding`，不动通用 `ilongrun` 内核。最佳方案如下。

### 7.1 保留现有协议主骨架

保持这条主链不变：

```text
phase-define
→ phase-plan
→ phase-build
→ phase-verify
→ phase-review
→ phase-audit
→ phase-finalize
```

理由：

- 这是 iLongRun 的账本化优势所在
- review / audit / finalize 已经与长运行真值系统打通
- 没必要为了借鉴 Superpowers 而重做 phase 结构

### 7.2 在 build 前补一个 workspace isolation gate

建议在 `phase-build` 前增加一个可选但协议化的 gate：

- 如果当前任务具备 git 环境，且 build 会并行或有较高写集冲突风险，则评估：
  - 是否需要 worktree
  - 是否需要 feature branch
  - 当前 baseline 是否干净
- 若不具备 git/worktree 条件，则显式记录 `workspaceIsolation.skippedReason`

这能把“是否隔离工作区”从临时经验提升为结构化决策。

### 7.3 在每个 build workstream 内引入 microcycle

建议把 build 阶段的 workstream 执行细化为最小闭环：

```text
spec-lock
→ RED
→ verify-red
→ GREEN
→ verify-green
→ self-review
→ spec-review
→ quality-review
→ handoff
```

说明：

- `spec-lock`：锁定本 task 的目标、约束、写集、验收条件
- `RED / verify-red / GREEN / verify-green`：借鉴 TDD 微循环
- `self-review`：worker 自检，防止明显遗漏
- `spec-review`：检查是否偏离 plan/contract
- `quality-review`：检查代码质量/测试质量/安全问题
- `handoff`：把 evidence、结果、遗留风险写回账本

这样做的价值是：

- phase-review 不再成为唯一拦截点
- workstream 完成的含义更可验证
- build 阶段的 drift 能被更早发现

### 7.4 把 verification-before-completion 升为 finalize 硬门禁

建议 future protocol 明确：

- `phase-finalize` 不只是汇总报告
- 任何完成声明都必须带 **fresh verification evidence**
- evidence 要求至少包含：
  - 验证命令
  - 执行时间
  - exit code
  - 关键摘要

没有 fresh evidence 时：

- 可以说“已实现但未完成验证”
- 不得说“已完成 / 已通过 / ready to ship”

### 7.5 把 systematic-debugging 升为 recovery 入口纪律

未来 recovery 不应直接进入 fix，而应固定走：

```text
failure observed
→ root cause investigation
→ hypothesis
→ minimal test/fix
→ verify
→ rejoin workflow
```

并要求落盘 `rootCauseRecord`。这能显著减少：

- 多次修补但问题仍反复
- fix 了症状但没 fix 根因
- resume 后没人知道上次为什么失败

### 7.6 把 writing-skills 迁移为 iLongRun 的 skill engineering 标准

建议后续把 iLongRun 的 skill 工程从“写文档”升级成“写可验证的 process artifact”：

- description 只写触发条件
- skill 必须有清晰 required background / required sub-skill 语义
- 高频入口 skill 要求词数预算
- 新增或修改 skill 前，先设计 baseline failure case
- 通过 pressure scenario 验证 skill 是否真正减少 agent 偏差

---

## 8. 拟议协议升级项（建议字段，不是本轮已实现事实）

> 以下均为未来协议建议，不代表当前仓库已实现。

### 8.1 `config/coding-protocol.jsonc` 建议新增

```jsonc
{
  "methodologyOverlay": {
    "name": "superpowers-inspired-coding-discipline",
    "mode": "selective-deep-adaptation"
  },
  "workspaceIsolationPolicy": {
    "enabled": true,
    "allowSkip": true,
    "preferredStrategy": ["git-worktree", "feature-branch", "in-place"],
    "requireBaselineCheck": true
  },
  "taskMicrocycle": {
    "enabled": true,
    "steps": [
      "spec-lock",
      "red",
      "verify-red",
      "green",
      "verify-green",
      "self-review",
      "spec-review",
      "quality-review",
      "handoff"
    ]
  },
  "claimVerificationPolicy": {
    "requireFreshEvidence": true,
    "evidenceTTL": "same-session-or-explicit-rerun"
  },
  "debugPolicy": {
    "requireRootCauseRecordBeforeFix": true,
    "maxBlindFixAttempts": 0
  },
  "skillEngineeringPolicy": {
    "frontmatterStyle": "trigger-first",
    "requireSkillTests": true,
    "enforceTokenBudget": true
  }
}
```

### 8.2 `scheduler.json` 未来建议新增

- `workspaceIsolation`
- `phaseGuards`
- `claimVerification`

建议语义：

- `workspaceIsolation`：记录当前 run 是否需要工作区隔离、是否已满足
- `phaseGuards`：记录本 run 当前激活的 methodology gate
- `claimVerification`：记录当前完成声明所依赖的验证证据状态

### 8.3 `workstreams/*/status.json` 未来建议新增

- `specRef`
- `microcycleState`
- `reviewSequence`
- `freshEvidence`
- `rootCauseRecord`

建议语义：

- `specRef`：对应 define/plan 中的哪一段 contract
- `microcycleState`：记录当前 task microcycle 走到哪一步
- `reviewSequence`：记录 spec-review / quality-review 收敛状态
- `freshEvidence`：记录最近验证命令与结果摘要
- `rootCauseRecord`：失败 workstream 的根因调查记录

---

## 9. 不建议采用的内容

以下内容看起来“先进”，但不适合作为 iLongRun coding 的默认策略：

### 9.1 不建议整包搬运 Superpowers skills

原因：

- 会造成双重技能体系并存
- 容易让 iLongRun 用户入口与 Copilot 插件入口混淆
- 会把 iLongRun 从“有内核的系统”拉回“技能包组合”

### 9.2 不建议让所有 coding run 强制使用 worktree

原因：

- 并非所有用户都在标准 git 仓库中运行
- 一些快速本地迭代任务不值得增加工作区切换成本
- 更合理的方式是 protocolized optional gate

### 9.3 不建议把每个 review 都外包成新的独立最终 phase

Superpowers 的 per-task review loop 很好，但 iLongRun 已有 `phase-review` / `phase-audit` / `phase-finalize`。若继续新增大量 phase，会削弱当前协议可读性。

正确做法是：

- phase 数量保持稳定
- 在 build workstream 内部增加 microcycle 与 reviewSequence

### 9.4 不建议让 iLongRun 变成强依赖 session hooks 的系统

Superpowers 很多“自然触发”的体验来自其 hook + skill 文化。iLongRun 若过度依赖 hooks，会削弱其：

- 可移植性
- 工具链透明性
- 账本真值的一致性

---

## 10. 分阶段升级路线图（建议 v0.7.0）

### Phase A：技能工程标准化

目标：先把 iLongRun 自己的 skills 写法变科学。

建议动作：

1. 重写 `ilongrun` / `ilongrun-coding` / `ilongrun-resume` / `ilongrun-status` frontmatter description
2. 新增 skill lint，检查：
   - description 是否为 `Use when...`
   - 必要章节是否存在
   - 高频 skill 词数是否超预算
   - cross-reference 是否合法
3. 为 `ilongrun-coding` 建立 baseline failure scenarios

### Phase B：workspace isolation 与 microcycle 接入

目标：把 build 阶段做得更像工程系统，而不是“任务已发出”。

建议动作：

1. `phase-build` 前增加 workspace isolation gate
2. workstream contract 增加 microcycle 配置
3. build status 支持 `reviewSequence`
4. status board 可展示 microcycle 进度

### Phase C：claim verification 与 root cause gate 接入

目标：把完成宣称与恢复修复收紧为协议硬门禁。

建议动作：

1. finalize 读取 `freshEvidence`
2. 无 fresh evidence 时 finalize 必须失败
3. recovery 读取 `rootCauseRecord`
4. 无根因记录时不得直接 fix/complete

### Phase D：skill testing 体系化

目标：把 iLongRun skill 自己纳入工程验证。

建议动作：

1. 建立 `skills-test` 或 `skill-lint` 工具
2. 为关键 skills 建立 pressure scenario 回归集
3. 为高频 skills 建立 token budget 与 CSO 检查

---

## 11. 推荐升级动作总表

按优先顺序，推荐执行以下 6 项：

1. **Skill frontmatter 重写**  
   将 `ilongrun` / `ilongrun-coding` / `ilongrun-resume` / `ilongrun-status` 的 description 改成 `Use when...` 风格，只写触发条件。

2. **引入 workspace isolation gate**  
   在 coding build 前增加可选 worktree/branch 隔离检查。

3. **把 build workstream 改成 microcycle**  
   固定为 `spec-lock → RED → verify-red → GREEN → verify-green → self-review → spec-review → quality-review → handoff`。

4. **把 verification-before-completion 硬接到 finalize**  
   没有 fresh verification evidence，不得 claim done。

5. **把 systematic-debugging 硬接到 recovery**  
   failed workstream 必须先写根因记录，再允许修复。

6. **建立 iLongRun skills 的测试规范**  
   借鉴 `writing-skills`，把“技能本身也要测试”引入 iLongRun。

---

## 12. 下一轮实现验收建议

以下不是本轮文档验收，而是未来执行升级时的最低验收基线：

1. 新增 methodology 字段后，`selftest` 能校验其存在与合法值
2. finalize 缺 `freshEvidence` 时必须失败
3. recovery 在无 `rootCauseRecord` 时不得直接推进 fix
4. build workstream 若未完成 `reviewSequence`，不得标记完整完成
5. skill lint 至少能检查：
   - frontmatter description 风格
   - 必要章节
   - 词数预算
   - cross-reference 合法性

---

## 13. 最终判断

### 应 adopt 的部分

- Superpowers 的流程优先思想
- task-level microcycle
- evidence-before-claims
- root-cause-before-fix
- skill engineering / skill TDD

### 应 reject 的部分

- 整包引入 Superpowers
- 用 session skill runner 替代 iLongRun scheduler 真值
- 把所有 coding 流程都改成 hooks-first

### 一句话结论

**iLongRun 的下一步不是“变成 Superpowers”，而是让 `ilongrun-coding` 吸收 Superpowers 最强的方法论，把现有长运行账本系统升级为“更科学的 coding discipline kernel”。**

---

## 附录 A：核心来源链接

- [Superpowers README](https://github.com/obra/superpowers)
- [using-superpowers](https://raw.githubusercontent.com/obra/superpowers/main/skills/using-superpowers/SKILL.md)
- [brainstorming](https://raw.githubusercontent.com/obra/superpowers/main/skills/brainstorming/SKILL.md)
- [writing-plans](https://raw.githubusercontent.com/obra/superpowers/main/skills/writing-plans/SKILL.md)
- [using-git-worktrees](https://raw.githubusercontent.com/obra/superpowers/main/skills/using-git-worktrees/SKILL.md)
- [subagent-driven-development](https://raw.githubusercontent.com/obra/superpowers/main/skills/subagent-driven-development/SKILL.md)
- [requesting-code-review](https://raw.githubusercontent.com/obra/superpowers/main/skills/requesting-code-review/SKILL.md)
- [test-driven-development](https://raw.githubusercontent.com/obra/superpowers/main/skills/test-driven-development/SKILL.md)
- [systematic-debugging](https://raw.githubusercontent.com/obra/superpowers/main/skills/systematic-debugging/SKILL.md)
- [verification-before-completion](https://raw.githubusercontent.com/obra/superpowers/main/skills/verification-before-completion/SKILL.md)
- [writing-skills](https://raw.githubusercontent.com/obra/superpowers/main/skills/writing-skills/SKILL.md)

## 附录 B：本地基线路径

- `/Users/zscc.in/Desktop/AI/ilongrun-V2/ilongrun-repo/config/coding-protocol.jsonc`
- `/Users/zscc.in/Desktop/AI/ilongrun-V2/ilongrun-repo/skills/ilongrun-coding/SKILL.md`
- `/Users/zscc.in/Desktop/AI/ilongrun-V2/ilongrun-repo/docs/架构与运行机制.md`
