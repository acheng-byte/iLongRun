---
name: ilongrun-status
description: 用中文查看 ILongRun 的 scheduler 状态、phase/wave/workstream 进度、质量门禁与下一步动作。
allowed-tools: ["view", "glob", "grep", "bash"]
user-invocable: true
disable-model-invocation: false
---

这是只读技能，不要修改任何文件。

## Resolve run

- 若 prompt 指定 run-id，就用它。
- 否则读取 `.copilot-ilongrun/state/latest-run-id`。
- 若不存在 run 目录，直接说明当前工作区还没有 ILongRun 状态。

## 读取顺序

按下面顺序读取，够用即停：

1. `scheduler.json`（必读，核心真值源）
2. `plan.md`
3. `strategy.md`
4. `task-list-N.md`
5. `workstreams/ws-*/status.json`（按需）
6. `reviews/gpt54-final-review.md`（若存在，文件名保持兼容）
7. `reviews/adjudication.md`（若存在）
8. `COMPLETION.md`（若存在）
9. `journal.jsonl` 尾部（仅在需要解释错误 / 限流时）

## 中文化输出总规则

- **默认所有对外展示文案都使用简体中文。**
- 若某个值属于机器字段（如 `running`、`direct-lane`、`internal`），优先输出中文展示值；必要时可在中文后补充原始值，例如：`进行中（running）`。
- 用户自定义 workstream 名称、文件路径、run-id、模型名保持原样，不要擅自翻译。
- 对内置 phase / wave / mode / profile / control / backend / verdict 名称做中文化渲染。
- 除非用户明确要求英文，否则**不要输出整块英文看板**，也不要把 section 标题写成英文。
- 不要依赖固定宽度对齐——长 run-id、中文文本和路径可能打断列宽。
- 默认遵循 **iLongRun 原始简洁风格**：除非用户明确要求，否则不要主动引入额外 ANSI 配色、渐变或动画效果；优先保持黑白终端下也自然好看的版式。
- 所有框形看板默认采用**右侧开口**的品牌样式：顶部和底部只保留左侧起笔与横线，不要在右侧闭口；若当前环境不适合 ANSI，也要保持同样的开口框布局。

### 常见状态展示映射

| 原始值 | 中文展示 |
|--------|----------|
| complete / done | 已完成 |
| passed | 已通过 |
| verified | 已验证 |
| running / in-progress | 进行中 |
| active | 活跃 |
| pending | 待处理 |
| blocked | 已阻塞 |
| failed | 失败 |
| skipped | 已跳过 |
| warning | 警告 |
| dirty / drift | 脏状态 |
| not-required | 不适用 |
| resumable | 可继续 |

### 执行后端展示映射

| 原始值 | 中文展示 |
|---------|-------|
| internal | 🏠 内部执行 |
| fleet | 🚀 舰队执行 |

### 常见模式展示映射

| 原始值 | 中文展示 |
|--------|----------|
| direct-lane | 直连模式 |
| wave-swarm | 波次蜂群 |
| super-swarm | 超级蜂群 |
| fleet-governor | 舰队治理 |
| sentinel-watch | 哨兵观察 |
| complete-and-exit | 完成后退出 |

### 常见画像与控制模式映射

| 原始值 | 中文展示 |
|--------|----------|
| coding | 编码 |
| office | 办公 |
| research | 研究 |
| launcher-enforced | 启动器强制 |
| session-inherited | 会话继承 |

### 内置阶段名称映射

| 原始值 | 中文展示 |
|--------|----------|
| Strategy / Strategy Synthesis | 策略制定 |
| Execution | 执行 |
| Finalize | 收尾 |
| Final audit / Audit | 最终审查 |

### 进度条

使用 Unicode 方块字符绘制，固定 20 字符宽：
- 已完成部分：`█`
- 未完成部分：`░`
- 末尾显示百分比和计数，例如：`████████████░░░░░░░░ 60% (3/5)`

## 输出格式

使用以下视觉模板，确保终端呈现**清晰美观、层次分明、默认中文化**。
每个展示分区都不可省略；无数据时明确写“无”。

### 输出模板

```
╭─── 🚀 iLongRun 状态看板 ────────────────────────────
│
│  🆔 运行 ID    {run-id}
│  📊 当前状态   {state-emoji} {display-state}
│  🎯 当前阶段   {display-phase-name}
│  🔧 运行模式   {display-mode}
│  🤖 执行模型   {display-model-name}
│  🌐 任务画像   {display-profile}
│  🔑 控制模式   {display-control-mode}
│  🕐 最近更新   {updatedAt}
│
╰──────────────────────────────────────────────────────

📋 阶段进度
──────────────────────────────────
  {phase-emoji} {display-phase-name}  {display-status}  [{wave-count} 个波次]
  {phase-emoji} {display-phase-name}  {display-status}  [{wave-count} 个波次]
  ...
  {progress-bar} {percent}% ({done}/{total} 个阶段)

🌊 波次详情
──────────────────────────────────
  📌 阶段：{display-phase-name}
    ├── {wave-id}  {backend-badge}  {status-emoji} {display-status}
    │   └── 工作流：{ws-id-list 或 "无"}
    └── {wave-id}  {backend-badge}  {status-emoji} {display-status}
        └── 工作流：{ws-id-list 或 "无"}
  （对每个 phase 重复上述结构）

⚡ 工作流进度
──────────────────────────────────
  {status-emoji} {ws-id}  {name}  {backend-badge}  {ownerRole}
  ...
  {progress-bar} {percent}% ({done}/{total} 个已完成)

🔒 质量门禁
──────────────────────────────────
  代码审查      {gate-emoji} {display-review-status}
  最终终审      {gate-emoji} {display-audit-status}
  裁决          {gate-emoji} {display-adjudication-status}
  必须修复      {pendingMustFixCount} 项

🛡️ 验证状态
──────────────────────────────────
  状态          {verification.state-emoji} {display-verification-state}
  失败分类      {verification.failureClass || "无"}
  建议动作      {display-recommended-action}
  最近验证      {verification.lastVerifiedAt || "尚未验证"}
  最近错误      {lastError || "无"}

🚢 舰队运行态
──────────────────────────────────
  能力状态      {display-fleet-capability}
  降级波次      {degradedWaves || "无"}
  最近分发      {lastDispatchedWave || "无"}

⚠️ 阻塞 / 风险
──────────────────────────────────
  {blocker-list 或 "（无阻塞）"}

💡 下一步建议
──────────────────────────────────
  - {recommended-action-1}
  - {recommended-action-2}

📌 最终判定：{display-verdict}
```

## 任务画像感知渲染

根据 `profile` 字段调整显示重点：

- **`coding`**：完整显示“质量门禁”分区（代码审查 / 最终终审 / 裁决 / 必须修复计数）。
- **`office` / `research`**：将质量门禁分区简化为一行 `➖ 非编码任务，审查门禁不适用`，改为显示证据覆盖情况：
  ```
  📚 证据覆盖
  ──────────────────────────────────
    {ws-id}: result.md {存在?✅:❌}  evidence.md {存在?✅:❌}
    ...
  ```

## 舰队运行态省略规则

- 若 `runtime.fleetCapability.status` 为 `unknown` 且无 fleet-tagged wave，省略整个“舰队运行态”分区。

## 脏状态检测

如果出现以下**任一**情况，在“阻塞 / 风险”分区前额外插入：

```
⚠️ 检测到脏状态 / 状态漂移
──────────────────────────────────
  - {具体描述}
建议：使用 /ilongrun-resume latest 进行收敛式 finalize，而不是从头重跑。
```

### 脏状态规则

| 条件 | 描述 |
|------|------|
| `state=complete` 但 `requestedDeliverables` 非空且 `deliverables` 为空 | 声明完成但未交付任何请求产物 |
| `state=complete` 但 `activeWorkstreams` 非空 | 声明完成但仍有活跃工作流 |
| `state=running` 但 `COMPLETION.md` 已存在 | 运行中但已有完成标记 |
| `state=complete\|blocked` 但 `.copilot-ilongrun/state/active-run-id` 仍指向当前 run | active-run-id 未清理 |
| `state=complete` 但 `COMPLETION.md` 不存在 | 声明完成但缺少完成报告 |
| `verification.state=failed` 或 `hardFailures` / `driftFindings` 非空 | 验证失败或存在漂移 |
| `profile=coding` 但 phase 已到 finalize 阶段，`reviews/gpt54-final-review.md` 不存在 | 编码任务缺少终审报告 |
| `profile=coding` 且 `pendingMustFixCount > 0` | 存在未解决的必须修复项 |
| `profile=coding` 且 `reviews.status` 不是 `passed` 或 `not-required`，但 state 已是 complete | 审查未通过就声明完成 |
| required workstream 的 `task-list-N.md` 文件不存在 | 缺少任务清单投影 |
| required workstream 的 `status.json` / `result.md` / `evidence.md` 在已完成状态下仍缺失 | 关键产物缺失 |
| `selectedModel=claude-opus-*` 但 `modelControlMode=session-inherited` | 模型控制模式异常 |
| `plan.md` 中缺少 `<!-- ILONGRUN:PLAN:START -->` 标记或 plan 内容与 scheduler.json 明显不同步 | 投影文件脱节 |

### 非脏状态排除

- `deliverables` 为空但 `requestedDeliverables` 也为空 → **不是**脏状态（非编码任务可合法无 deliverables）
- `reviews.status=not-required` 且 `profile != coding` → **不是**脏状态

## 输出要点

简洁返回以下全部信息：

- run id
- state / active phase / mode（以中文展示，必要时可附原值）
- profile
- selected model / fallback reason（若有 `fallbackReason`）
- model control mode
- phase 完成情况（含进度条）
- 波次后端与状态（internal / fleet 需中文化展示）
- 工作流完成度（含进度条）
- coding review gate 状态（仅 coding profile）
- 最终终审状态（仅 coding profile）
- adjudication 状态（仅 coding profile）
- verification state / failure class / recommended action
- 舰队能力 / 降级信息（仅有 fleet wave 时）
- 当前 blocker / risk
- 下一步建议
- 最终判定：`可继续` / `已完成` / `已阻塞`
- 是否存在脏状态（若有，明确列出）

## 示例输出

以下是一个 **office profile** 任务的典型输出（默认中文化）：

```
╭─── 🚀 iLongRun 状态看板 ────────────────────────────
│
│  🆔 运行 ID    20260406-225813-ilongrun-https-github
│  📊 当前状态   🔄 进行中（running）
│  🎯 当前阶段   策略制定
│  🔧 运行模式   直连模式（direct-lane）
│  🤖 执行模型   Claude Opus 4.6
│  🌐 任务画像   办公（office）
│  🔑 控制模式   启动器强制（launcher-enforced）
│  🕐 最近更新   2026-04-06T14:58:14Z
│
╰──────────────────────────────────────────────────────

📋 阶段进度
──────────────────────────────────
  🔄 策略制定  进行中（running）  [1 个波次]
  ⏳ 执行      待处理（pending）  [1 个波次]
  ⏳ 收尾      待处理（pending）  [1 个波次]
  ░░░░░░░░░░░░░░░░░░░░ 0% (0/3 个阶段)

🌊 波次详情
──────────────────────────────────
  📌 阶段：策略制定
    └── wave-strategy  🏠 内部执行  🔄 进行中（running）
        └── 工作流：无

  📌 阶段：执行
    └── wave-execution-1  🏠 内部执行  ⏳ 待处理（pending）
        └── 工作流：ws-001

  📌 阶段：收尾
    └── wave-finalize-1  🏠 内部执行  ⏳ 待处理（pending）
        └── 工作流：无

⚡ 工作流进度
──────────────────────────────────
  ⏳ ws-001  主执行链路  🏠 内部执行  executor
  ░░░░░░░░░░░░░░░░░░░░ 0% (0/1 个已完成)

➖ 非编码任务，审查门禁不适用

📚 证据覆盖
──────────────────────────────────
  ws-001: result.md ❌  evidence.md ❌

🛡️ 验证状态
──────────────────────────────────
  状态          ⏳ 待处理（pending）
  失败分类      无
  建议动作      继续执行（continue）
  最近验证      尚未验证
  最近错误      无

⚠️ 阻塞 / 风险
──────────────────────────────────
  （无阻塞）

💡 下一步建议
──────────────────────────────────
  - 完成策略制定阶段
  - 执行 ws-001 工作流

📌 最终判定：可继续（resumable）
```
