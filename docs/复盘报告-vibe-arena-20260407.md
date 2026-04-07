# Vibe Arena 长跑复盘报告（2026-04-07）

## 1. 复盘范围

- 任务项目：`/Users/zscc.in/Desktop/AI/Test/test4-game`
- 真值 run：`/Users/zscc.in/Desktop/AI/Test/test4-game/.copilot-ilongrun/runs/20260407-061049-three-js-typescript-sock`
- iLongRun 实现：`/Users/zscc.in/Desktop/AI/ilongrun-V2/ilongrun-repo`
- 复盘目标：
  1. 判断这次长跑是否达到**真实项目交付标准**
  2. 排查 iLongRun 内核、状态机、投影同步、内部协议导致的**不稳定 / 漂移 / 假完成**问题

## 2. 交付等级结论

| 等级 | 结论 | 说明 |
|---|---|---|
| L0 账面完成 | **通过** | `scheduler.json` 显示 `state=completed`，`reviews.status=passed`，原账面 `verification.state=passed` |
| L1 原型交付 | **不通过** | 存在一票否决项：核心链路未真正接入、finalize/verifier 崩溃、plan/task-list/active-run 指针漂移 |
| L2 工程交付 | **不通过** | 真值/投影契约不统一，重复核心实现与验证闭环不足 |
| L3 生产交付 | **不通过** | 鉴权、持久化、限流、监控、回滚等生产要件未形成 |

### L1 一票否决证据

- `finalize` 真实日志以 `KeyError: 'index'` 崩溃收尾：`/Users/zscc.in/Desktop/AI/Test/test4-game/.copilot-ilongrun/launcher/coding-20260407-061049.log`
- run 已完成但 `active-run-id` 仍指向旧 run：`/Users/zscc.in/Desktop/AI/Test/test4-game/.copilot-ilongrun/state/active-run-id`
- `plan.md` / `mission.md` 仍显示 `running`，与 `scheduler.json` 的 `completed` 冲突
- 核心多人对战主链未真正接线：
  - 客户端入口：`/Users/zscc.in/Desktop/AI/Test/test4-game/packages/client/src/main.ts`
  - 客户端主控：`/Users/zscc.in/Desktop/AI/Test/test4-game/packages/client/src/core/GameClient.ts`
  - 服务端入口：`/Users/zscc.in/Desktop/AI/Test/test4-game/packages/server/src/app.ts`

## 3. 项目真实完成度审计

### 3.1 关键需求矩阵

| 需求 | 状态 | 证据 |
|---|---|---|
| TypeScript | **Wired + Verified** | `pnpm typecheck` 通过；项目全量 TS 结构已落地 |
| Three.js 渲染 | **Wired + Verified** | 客户端使用 Three.js；`/Users/zscc.in/Desktop/AI/Test/test4-game/packages/client/src/core/GameClient.ts` |
| 服务器权威 + 客户端预测 / 插值 / 校正 | **Implemented, not wired** | `NetworkManager` / `ClientPredictor` / `EntityInterpolator` 存在，但 `GameClient` 未接入 |
| seed + vibeParams 可复现地图 | **Implemented + Partially verified** | 类型、RNG、BSP 生成与单测存在；但缺少多人运行态闭环证据 |
| 受限 DSL / JSON 技能系统 | **Implemented + Partially verified** | 共享技能 preset/runtime 存在；但未证明已接入完整多人战斗链 |
| WebGPU 优先、WebGL2 回退 | **Implemented, not fully met** | `RenderBackend` 只实际启用 WebGL2；WebGPU 仅检测不切换 |
| 1 主题 + 3 技能 + 幽灵投票 + 1 Bot | **Partially implemented** | 主题与 3 个技能 preset 存在；`VoteUI` / `GhostSystem` / `BotAgent` 未见主链接线 |
| ReplayEvent 事件日志 | **Implemented** | 类型与 replay logger 存在 |
| Claude + Groq 兼容的 LLMProvider，且只输出结构化 JSON | **Missing / scaffold only** | `NoopLLMProvider` 占位，无 Claude/Groq 实现：`/Users/zscc.in/Desktop/AI/Test/test4-game/packages/shared/src/ai/LLMProvider.ts` |

### 3.2 真实运行闭环结论

**当前更接近“高完成度原型代码库”，不是“真正可交付的多人 FPS 原型”。**

原因：

- 客户端目前主要是本地渲染 + 基础输入 + 原生 `socket.io-client` 连接，未把预测/插值/状态校正主链真正接起来
- 服务端当前真实接线只覆盖：`handshake`、`create_room`、`chat_message`
- 现有 E2E 只覆盖 health/status、双客户端握手、建房、聊天广播：
  - `/Users/zscc.in/Desktop/AI/Test/test4-game/packages/server/src/network/__tests__/ServerE2E.test.ts`
- 这离 Prompt 验收要求中的“实时对战、受击、死亡、重生、观战、投票影响下一局、Bot 参战”仍有明显差距

## 4. 代码与运行时关键证据

### 4.1 客户端主链断层

- `GameClient` 直接管理 `Socket`，未接入：
  - `/Users/zscc.in/Desktop/AI/Test/test4-game/packages/client/src/network/NetworkManager.ts`
  - `/Users/zscc.in/Desktop/AI/Test/test4-game/packages/client/src/prediction/ClientPredictor.ts`
  - `/Users/zscc.in/Desktop/AI/Test/test4-game/packages/client/src/interpolation/EntityInterpolator.ts`
  - `/Users/zscc.in/Desktop/AI/Test/test4-game/packages/client/src/ui/VoteUI.ts`
- 入口文件 `/Users/zscc.in/Desktop/AI/Test/test4-game/packages/client/src/main.ts` 只做 `GameClient.init/start/connect`

### 4.2 服务端主链断层

- 服务端入口 `/Users/zscc.in/Desktop/AI/Test/test4-game/packages/server/src/app.ts` 当前只实际注册：
  - `ClientMessageType.CREATE_ROOM`
  - `ClientMessageType.CHAT_MESSAGE`
- 下列核心模块存在，但未看到在入口主链中形成对战闭环：
  - `/Users/zscc.in/Desktop/AI/Test/test4-game/packages/server/src/game/GameStateManager.ts`
  - `/Users/zscc.in/Desktop/AI/Test/test4-game/packages/server/src/systems/GhostSystem.ts`
  - `/Users/zscc.in/Desktop/AI/Test/test4-game/packages/server/src/ai/BotAgent.ts`
- 房间管理存在两套实现，存在架构漂移风险：
  - `/Users/zscc.in/Desktop/AI/Test/test4-game/packages/server/src/core/RoomManager.ts`
  - `/Users/zscc.in/Desktop/AI/Test/test4-game/packages/server/src/room/RoomManager.ts`

### 4.3 设计文档领先于运行时

- 文档中大量声明了 WebGPU/WebGL2 双后端、后处理分离、Bot、Replay、地图生成等扩展能力
- 但运行时代码里 `RenderBackend` 明确写着“当前版本使用 WebGL2 渲染器，WebGPU 支持在 Three.js 稳定后启用”：
  - `/Users/zscc.in/Desktop/AI/Test/test4-game/packages/client/src/rendering/RenderBackend.ts`
- 这说明**文档覆盖面 > 当前真正接入的 runtime 能力面**

## 5. 项目验证结果（本次复核）

### 5.1 通过项

- `pnpm typecheck`：通过
- `pnpm test`：通过，共 **209 tests**
  - shared 83
  - server 96
  - client 30
- `pnpm build`：通过
- `pnpm lint`：**0 error / 3 warning**

### 5.2 仍然不能据此判定交付通过

因为这些结果只能证明：

- 静态类型没炸
- 单元测试与当前 smoke 测试没炸
- 构建产物可出

但还**不能证明**：

- 两浏览器客户端可稳定进入同房间并实时战斗
- 死亡/观战/投票/Bot/技能广播形成完整多人闭环
- 渲染与网络异常不会把整局打崩

## 6. 长跑稳定性与状态账本审计

### 6.1 运行稳定性指标

| 指标 | 数值 | 说明 |
|---|---:|---|
| sessionStart | 25 | hook 记录 |
| sessionEnd | 25 | hook 记录 |
| preToolUse | 568 | hook 记录 |
| errorOccurred | 24 | hook 记录 |
| 显式 rate-limit 日志 | 4 | launcher log 可见 |
| 模型尝试轨迹 | 6 条 | `claude-opus-4.5 → claude-sonnet-4.6 → claude-sonnet-4.5 → gpt-5.4` 伴随 3 次 rate-limited 记录 |
| /fleet 账面模式 | `fleet-dispatch` | scheduler 声称 |
| /fleet 运行时观测 | `fleetCapability.status=unknown` | runtime 未形成可信观测闭环 |

### 6.2 账本漂移

实际 run 在原始状态下存在：

- `scheduler.json.state = completed`
- `plan.md` / `mission.md` 仍为 `running`
- `scheduler.taskLists[]` 缺失，只能靠推断重建
- `task-list-1.md` ~ `task-list-7.md` 复选框全部静态空选
- `active-run-id` 未清理，完成态 run 仍可能继续吸附 hook 事件
- 至少 1 个 workstream 时间戳异常：`ws-306` 存在 `completedAt < startedAt`

### 6.3 finalize / verify 协议问题

原始 run 的 launcher 末尾出现：

- `Traceback (most recent call last)`
- `KeyError: 'index'`

根因是 verifier 依赖 `workstreams[*].index`，但这次真实 run 的 `scheduler.json` 中 workstream 只有：

- `id`
- `name`
- `phaseId`
- `waveId`
- `status`
- `dependencies`
- `ownerModel`
- `backend`
- `lastUpdatedAt`

缺少 `index / ownerRole / taskListPath / resultPath / evidencePath / statusPath` 等 verifier 依赖字段。

## 7. iLongRun 内核/协议缺陷判定

### P0

1. **verifier 契约过脆**
   - 对 `ws.index` 的硬依赖会直接打崩 finalize
2. **完成态指针未清理**
   - `active-run-id` 可残留到已完成 run
3. **task-list 只是静态投影，不会随真值动态勾选**
   - 导致“做完了但看板仍全空”
4. **完成态枚举不统一**
   - `complete / completed` 混用，导致清理和 verify 条件漏判

### P1

1. **review 解析过脆**
   - `- None.` 这种常见写法会被误算成 must-fix
2. **先 verify 再 sync projection**
   - 历史 run 明明可修，仍先报缺少 task-list 的假失败
3. **/fleet 账面模式缺少可验证 runtime 指标**
   - `mode=fleet-dispatch` 但 `runtime.fleetCapability.status=unknown`

### P2

1. **没有统一 completion scoring / ledger dashboard**
2. **project 实现问题与内核问题混在一起，账面上难区分**
3. **缺少对“模块存在但未接主链”的自动预警**

## 8. 本次已落地的 iLongRun 修复

已在 `/Users/zscc.in/Desktop/AI/ilongrun-V2/ilongrun-repo` 实现：

- `scripts/_ilongrun_lib.py`
  - 兼容 `complete / completed / finalized`
  - 移除对 `ws.index` 的 verifier 硬依赖
  - 引入 `scheduler.taskLists[]` / structured checklist / 动态 task-list 投影
  - 增加 plan/mission 状态漂移、时间戳异常、active-run 残留探测
- `scripts/finalize_ilongrun_run.py`
  - complete 后自动清理 `active-run-id`
- `scripts/hook_event.py`
  - 已完成 run 不再继续写入本地 hook ledger
- `scripts/reconcile_ilongrun_run.py`
  - 先补投影再 verify
- `scripts/sync_ilongrun_ledger.py`
  - 新增确定性 ledger sync 工具
- `scripts/selftest_ilongrun.py`
  - 新增 finalize 清理、已完成 run hook 抑制、task-list 动态勾选、时间戳异常等回归覆盖

## 9. 修复有效性验证

- iLongRun 自测：`/Users/zscc.in/Desktop/AI/ilongrun-V2/ilongrun-repo/scripts/selftest_ilongrun.py` 通过
- 在 `test4-game` 的隔离副本上运行新版 `sync_ilongrun_ledger.py` 后：
  - `task-list` 投影恢复为 7 份
  - `active-run-id` 被清理
  - run state 归一为 `complete`
  - 原本大量账本漂移缩减为仅剩 **`ws-306` 时间戳异常** 这一项历史数据问题

## 10. 建议 backlog

### P0（必须先做）

1. 把 `scheduler.json + workstreams/*/status.json` 固化为唯一真值
2. 所有 finalize / reconcile / hook 流程统一完成态枚举与清理语义
3. 让 `taskLists[] / taskListPath / checklist status` 成为正式协议字段
4. 在 status verifier 中保留 drift，不再让 finalize 因字段缺失直接 traceback

### P1（稳定性增强）

1. 给 `/fleet` 增加真实 completedWaves / degradedWaves / probe 证据
2. 增加历史 run ledger migration 报告
3. 增加“模块存在但未接入口”的自动扫描器
4. 增加真实完成度评分：代码存在 / 已接线 / 已测试 / 已运行验证 四层分数

### P2（体验优化）

1. 增加账本状态看板
2. 增加“投影同步”显式日志
3. 为 review / adjudication / completion 提供统一报告模板

## 11. 你可能还没显式注意到的隐藏问题

1. **重复核心实现漂移**：两套 `RoomManager` 长期并存，后续极易出现功能实现与调用面分叉
2. **文档领先运行时**：架构文档很强，但 runtime 接线不足，容易制造“已交付”错觉
3. **AI 集成其实还没开始**：`LLMProvider` 仍是 noop，占位接口容易被误当成“已兼容 Claude/Groq”
4. **Smoke E2E 容易掩盖战斗闭环缺失**：当前 E2E 成功不能代表多人对战成功
5. **历史 run 被后续 hook 污染的风险很高**：如果不清 `active-run-id`，后续任何 hook 都可能污染旧 run 审计数据

## 12. 最终结论

这次 Vibe Arena 长跑的**账面完成度高，真实交付完成度中等偏低**。

- 对项目本身：更像“实现了大量模块与文档的高完成度原型仓库”，但还没有达到真正可交付的多人 FPS 原型标准
- 对 iLongRun 本身：已经具备长跑雏形，但在**账本协议、完成态清理、投影动态同步、历史 run 兼容**上存在明确内核缺口

因此，这次复盘的核心结论不是“项目没做出来”，而是：

> **项目代码产出很多，但 iLongRun 之前缺少一套足够严格的真值/投影/完成态契约，导致它很容易把“高产出原型”误判成“稳定已交付”。**
