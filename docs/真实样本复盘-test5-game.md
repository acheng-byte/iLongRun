# 真实样本复盘：`test5-game`

## 1. 目的

这份文档记录一次真实 coding 样本 run 的复盘结论。它的用途是：

- 作为 iLongRun 通用内核修复的证据样本
- 作为后续 selftest / doctor / verifier 设计的现实参照
- 明确区分“执行者没有按框架做”与“框架本身允许伪完成发生”

> 重要：`test5-game` 只是**真实样本**，不是 iLongRun 的产品适配对象。后续修复不能围绕该任务的业务逻辑做底层特判。

## 2. 样本概况

- 样本类型：`profile=coding`
- 样本 run id：`20260408-113842-three-js-typescript-sock`
- 复盘目标：验证 iLongRun 在真实 coding 生命周期中的账本一致性、gate enforcement、finalize 闭环与交付语义

## 3. 关键发现

### 3.1 生命周期没有真实闭环

样本 run 在文件层面出现过“completed”痕迹，但实际并没有完成 finalize 闭环：

- `scheduler.json` 同时出现 `state=running` 与 `status=completed`
- `COMPLETION.md` 缺失
- `active-run-id` 仍指向该 run
- raw `phase`、claim verification、phase guards 没有收敛到真正完成态

这说明当时的 run 更接近：

> **“形成了一个 smoke 级原型，但 finalize / ledger / gate 没有真实闭环。”**

### 3.2 review gate 存在伪完成

样本中出现了典型的 review 伪完成：

- workstream 状态已标 done / complete
- 但 `result.md` / `evidence.md` 仍是 placeholder

这类问题在通用框架里非常危险，因为它意味着：

- 文件名和状态都存在
- 但真实证据并不存在
- audit/finalize 若只看账面状态，就会被“伪完成”误导

### 3.3 verifier 语义和 completion score 脱节

样本 run 的 verify 结论明确是：

- `ok=false`
- `failureClass=state_drift`

但旧评分体系仍可能给出较高 completion score，甚至落到乐观的原型交付 verdict。这会直接误导使用者把“有代码、有服务、有 smoke”误判成“可以稳定交付”。

### 3.4 session 结束不等于 run 完成

样本还暴露了一个关键事实：

- 会话结束
- 服务仍在跑
- 某些产物已经存在

并不等于：

- 生命周期已闭环
- gate 已通过
- finalize 已完成

因此，`sessionEnd` 只能作为 **precheck / 落账时机**，不能作为“自动宣布任务完成”的依据。

## 4. 从样本反推出的通用框架缺陷

这次样本复盘最终反推出以下通用问题：

1. **完成态双真值**：top-level `state` 与 `status` 可同时存在且互相冲突。
2. **完成态可伪造**：只靠手改 `scheduler.json`，就能制造“看起来完成”的账面状态。
3. **review 证据校验不够硬**：placeholder `result.md` / `evidence.md` 没被系统性阻断。
4. **finalize 原子性不够**：`COMPLETION.md`、active pointer、state 之间存在中间不一致窗口。
5. **verify / score / verdict 语义不统一**：失败 run 仍可能拿到乐观评分。
6. **doctor 只看安装，不看当前工作区 run 健康**：导致用户无法快速识别“当前 run 是不是账面完成”。
7. **工作区污染缺少硬提示**：`.copilot-ilongrun/`、`node_modules/` 等生成态被 git 跟踪时，没有被明确提升为 run 风险。

## 5. 本轮整改如何吸收这个样本

基于这个样本，当前版本把修复落到了 iLongRun 通用层，而不是样本业务层：

- 完成态只认 `scheduler.json.state`
- ledger sync 会自动清理 legacy top-level `status`
- placeholder review 产物会被判定为伪完成
- `sessionEnd` 会触发本地 precheck 落账，但不会直接替代 finalize
- `COMPLETION.md` 缺失时，completed run 不再自动清 active pointer
- completion score 与 verdict 会服从 hard failure / drift 结论
- doctor 新增“当前工作区 Run 健康”区块
- verify / doctor 会检查 git 跟踪的生成态目录污染

## 6. 如何使用这份样本文档

后续如果再出现以下现象，可以优先回看这份文档对应的故障模型：

- `ok=false` 但 score 很高
- `active-run-id` 卡在已完成 run 上
- `COMPLETION.md` 缺失但 run 被写成 complete/completed
- review gate 看起来完成，但实际只有 placeholder
- 当前服务可访问，但状态看板仍然不可信

它不是业务实现说明，而是 iLongRun **内核审计样本**。
