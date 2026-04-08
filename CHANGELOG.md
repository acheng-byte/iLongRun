# 更新日志

## Unreleased

## v0.9.0

### 破坏性账本重构
- **新 run 直接切到全新 canonical 状态机**：`scheduler.json.state` 只允许 `running / blocked / completed / failed`，不再兼容历史 `complete / finalized` 或 top-level `status`
- **旧 run 不再作为执行面兼容对象**：新的 verify / finalize / doctor 只面向新账本规则；历史 run 仅保留人工复盘价值
- **终态文档彻底分离**：`COMPLETION.md` 只属于 `completed`，`BLOCKED.md` 只属于 `blocked`，`FAILED.md` 只属于 `failed`

### 收尾链路与 Gate Enforcement
- **收尾链路改为严格单向**：review → audit → adjudication → finalize，`adjudication.md` 只能在有效 `final-review.md` 之后生成
- **`proceed-to-finalize` / `return-for-fix` 成为唯一裁决决策**：前者才允许 `completed`，后者直接把 run 置为 `blocked`
- **`verification` 改成辅助诊断层**：不能再与 run 终态打架；`blocked / failed` run 保留 `verification.state=passed` 会被直接判错
- **`claimVerification` 成为 completed 的强前置**：fresh evidence 未收敛时，finalize 无法落成 `completed`

### workstream 与投影一致性
- **define / plan 的 result/evidence 改为系统自动写实**：完成后会自动生成结构化结果与证据，不再允许 `Pending result/evidence` 模板混入 done 状态
- **伪完成升级为硬失败**：workstream 标记 done 但缺结构化 result/evidence 时，verify 直接 hard-fail
- **运行中 delivery audit 降噪**：严格的 fake-completion 判定推迟到 final audit / terminal 校验阶段，减少 BUILD 中途噪音

### 诊断与可视化
- **status board 识别三类终态摘要**：看板会明确展示 `COMPLETION.md / BLOCKED.md / FAILED.md` 是否与 `scheduler.state` 一致
- **doctor 的当前工作区 run 健康区块升级**：新增对 terminal doc 错配、legacy `scheduler.status`、blocked/failed 误写 completion 的检查
- **通知链路对 blocked/failed 分流**：`blocked` 默认打开 `BLOCKED.md`，失败路径打开 `FAILED.md`

### 文档与回归
- **README / 快速开始改口**：明确新账本不兼容旧 run、三类终态摘要的语义、以及真正 completed 的判定条件
- **新增终态状态机重构蓝图**：补充 `docs/终态状态机与收尾链路重构蓝图.md`
- **新增发版说明**：补充 `docs/发版说明-v0.9.0.md`
- **selftest 重写终态断言**：覆盖 completed/block/failed 分离、placeholder-done 硬失败、legacy `scheduler.status` 拒绝、blocked 不清 active 指针

## v0.8.4

### 账本真值与完成态加固
- **完成态只认 `scheduler.json.state`**：top-level `status` 现在只作为 legacy 兼容读取；一旦与 `state` 冲突，verify 会直接判定 drift
- **ledger 写盘会自动清理非 canonical 顶层状态字段**：新的 ledger sync / finalize helper 会移除 top-level `status`，避免再次形成双真值
- **finalize 改成先准备 `COMPLETION.md` 再清理 active 指针**：减少“状态已完成但 completion 丢失”的中间不一致窗口

### Gate Enforcement 与 verifier 语义修复
- **review placeholder 继续视为伪完成**：`result.md` / `evidence.md` 的空壳、pending、placeholder、TODO/TBD 模板残留会被识别为未完成产物
- **review/adjudication 缺失改成上下文敏感阻断**：只有进入 audit/finalize 语境或 run 已完成态时，缺失终审/裁决才会成为硬失败；中途运行不再被过早误伤
- **completion score 与 verdict 收敛**：存在 hard failure 时分数封顶，存在 drift 时分数降级且 verdict 固定为 `state-drift`，不再出现 `ok=false` 同时 `A / prototype-ready`

### sessionEnd / doctor / workspace 安全
- **`sessionEnd` 现在会自动做一次本地 precheck 落账**：不依赖 Copilot CLI 额度，也能把 verification、recommendedAction、hook precheck 结果写回账本
- **已完成但缺 `COMPLETION.md` 的 run 不再自动清理 active-run-id**：会保留指针并记录 precheck，避免“账面完成、真实未闭环”
- **新增工作区污染检查**：若 git 跟踪了 `.copilot-ilongrun/`、`node_modules/`、`dist/`、`build/`、`.next/`、`coverage/` 等生成态目录，verify / doctor 会明确告警或失败
- **doctor 新增当前工作区 run 健康区块**：直接展示当前 active/latest run 的状态真值冲突、active 指针残留、finalize 缺件、review 伪完成、工作区污染与建议动作

### 文档与回归
- **新增真实样本复盘文档**：补充 `docs/真实样本复盘-test5-game.md`
- **新增项目级整改说明**：补充 `docs/项目全局审计与整改说明.md`
- **README / 快速开始同步更新**：明确 `state` 才是完成态唯一真值，并解释 doctor 的当前工作区 run 健康检查
- **新增发版说明**：补充 `docs/发版说明-v0.8.4.md`
- **selftest 补齐回归**：新增状态冲突、review placeholder、sessionEnd precheck、工作区污染等场景，默认仍不依赖 Copilot CLI 真跑额度

## v0.8.3

### 模型看板体验统一
- **`ilongrun-model show` 改为品牌化看板输出**：文本模式现在统一使用 iLongRun 的终端品牌视觉、中文区块标题与新手导向文案
- **脚本消费建议切换到 `--json`**：`show` 面向人类阅读，`--json` 继续保留稳定机器语义
- **TUI 渲染容错增强**：修复小终端尺寸下 `curses.addnstr()` 可能抛出的 `addnwstr() returned ERR`，避免交互式选模器直接退回 show
- **新增发版说明**：补充 `docs/发版说明-v0.8.3.md`

## v0.8.2

### 交互式选模器增强
- **`ilongrun-model` 新增 Tab 页签模式**：TTY 交互式 TUI 现在支持 `全局默认 / run模型 / coding模型` 三个页签
- **Tab 切页与作用域写入**：`Tab` / `Shift+Tab` / 左右方向键可切页，`Enter` 会按当前页签写入对应模型模板
- **新增全局 reset 热键**：在交互式 TUI 里按 `r` 会弹确认，并执行全局 reset
- **命令行直设仍保持全局语义**：`ilongrun-model <model>` / `show` / `reset` 继续只走全局模式，不新增公开 CLI scope 参数

### 模型模板写入语义
- **全局默认页签保持现有行为**：同时更新 `commandDefaults.run / coding`、`skillDefaults.ilongrun / ilongrun-coding` 与全局主执行角色模板
- **run模型页签采用浅作用域**：只更新 `commandDefaults.run` 与 `skillDefaults.ilongrun`
- **coding模型页签采用浅作用域**：只更新 `commandDefaults.coding` 与 `skillDefaults.ilongrun-coding`
- **不扩协议**：不新增配置字段，也不拆分共享 `roleModels`
- **审查与终审不变**：`codingAuditModel`、`roleModels.final-audit-reviewer` 与 review 固定角色保持原策略

### 测试与文档
- **模型管理 helper 增加隐藏测试入口**：新增 `--test-tab` 与 `--test-reset`，用于自测 run/coding 页签写入与 TUI reset 语义
- **selftest 覆盖页签作用域**：新增断言，验证 run/coding 页签只改浅作用域字段，全局 reset 仍恢复默认模板
- **README / 快速开始同步更新**：明确 Tab 分页作用域只存在于交互式 TUI，命令行直设 `<model>` 仍是全局模式
- **新增发版说明**：补充 `docs/发版说明-v0.8.2.md`

## v0.8.1

### 交互体验修正
- **`ilongrun-model` 改为终端交互式选模器**：无参在 TTY 终端中进入自建 picker，体验更接近原生 `/model`
- **非 TTY 无参默认 show**：脚本或管道里直接运行 `ilongrun-model` 时，默认退化为查看当前模板
- **新增显式子命令与刷新选项**：支持 `ilongrun-model show` 与 `ilongrun-model --refresh`
- **不再桥接当前 Copilot 会话模型**：`ilongrun-model` 只改 iLongRun 默认模板，不改当前会话的原生 `/model`

### 会话入口与菜单说明
- **移除 `/ilongrun-model` 会话入口**：不再把它作为 Copilot CLI 会话内 skill 暴露
- **升级安装会清理旧残留**：安装链路会主动移除历史 `~/.copilot/skills/ilongrun-model`
- **`/ilongrun*` 菜单说明中文化**：`/ilongrun`、`/ilongrun-prompt`、`/ilongrun-resume`、`/ilongrun-status` 的 frontmatter description 统一改成中文触发句
- **doctor 改为提示 legacy skill 残留**：若检测到旧 `/ilongrun-model` skill，只给 warn，不再作为缺失项报错

### 规则与文档
- **skill lint 允许中英文 trigger-first description**：接受 `Use when...` / `当用户...时使用` / `当需要...时使用`
- **默认 lint 目标调整**：移除 `ilongrun-model`，补上 `ilongrun-prompt`
- **README / 快速开始同步改口**：明确 `ilongrun-model` 是裸命令，不再宣传 `/ilongrun-model`
- **新增发版说明**：补充 `docs/发版说明-v0.8.1.md`

## v0.8.0

### 新增
- **新增 `ilongrun-model`**：提供 `ilongrun-model` / `copilot-ilongrun model` / `/ilongrun-model` 三个统一入口，用于热切换后续新 run 的默认主模型
- **新增模型管理 helper**：`scripts/manage_ilongrun_model.py` 负责 `show / set / reset`，支持 alias 归一化、双写安装态/仓库态配置、未知模型报错
- **新增模型管理 skill**：`skills/ilongrun-model/SKILL.md` 支持在 Copilot CLI 对话框中直接查看或切换模板模型

### 模型策略
- **主执行模板可热切换**：`ilongrun-model <slug>` 会同步更新 `run / coding / ilongrun / ilongrun-coding` 与主执行角色模板
- **审查模板固定为 GPT-5.4**：`code-reviewer / test-engineer / security-auditor` 默认收敛到 `gpt-5.4`
- **final audit 继续独立**：`codingAuditModel` 与 `roleModels.final-audit-reviewer` 保持独立，不被 `ilongrun-model` 改写
- **resume 优先继承历史 run 模型**：无显式 `--model` 时，`resume` 先读取目标 run 的 `selectedModel`
- **launcher / supervisor 选模收敛**：`run` 首跳按 run 模板、`coding` 首跳按 coding 模板，不再被 supervisor 误算成 fallback 首项

### 安装与诊断
- **安装/卸载链路补齐 `ilongrun-model`**：global launcher、bare commands、卸载脚本与清理脚本同步纳入
- **doctor 新增模型命令检查**：补充 `launcher.ilongrun-model`、`/ilongrun-model` skill 与模型管理 helper 完整性检查
- **技能 lint 纳入新 skill**：默认 lint 目标增加 `ilongrun-model`

### 文档
- **README / 快速开始同步补齐**：增加 `ilongrun-model` 用法、热切换范围与“只影响后续新 run”的说明
- **新增发版说明**：补充 `docs/发版说明-v0.8.0.md`

## v0.7.1

### 清理与一致性
- **历史命名硬清理**：移除 `phase-ship.md`，拆分为 `phase-audit.md` 与 `phase-finalize.md`
- **终审命名去模型化**：`ilongrun-gpt54-audit-reviewer.agent.md` 改为 `ilongrun-final-audit-reviewer.agent.md`
- **最终审查报告路径去模型化**：`reviews/gpt54-final-review.md` 改为 `reviews/final-review.md`
- **新增命名清理说明**：补充 `docs/内部命名清理说明.md`
- **新增全局审计说明**：补充 `docs/项目全局审计与整改说明.md`

### 模型语义
- **`--model` 升级为全链路强制**：显式指定模型时，run / coding / review / audit / finalize 全链路统一使用该模型
- **禁止跨模型 fallback**：显式 `--model` 场景下不再静默切到其他模型，只允许同模型重试
- **scheduler 模型元数据收敛**：`selectedModel`、`codingAuditModel`、`mission.modelAllocation`、review owner model 保持一致
- **仓库命令优先读取仓库配置**：直接运行仓库内 `scripts/copilot-ilongrun` 时，优先使用当前仓库 `config/`，避免被 `~/.copilot-ilongrun/config/` 的旧配置污染

### 文档
- **README 重构为新手入口页**：首页聚焦“这是什么、怎么安装、怎么开始、怎么看结果”
- **快速开始重写**：补齐 `--model` 全链路强制语义与常见排障
- **架构文档重写**：增加系统总览图与 coding 生命周期图，明确 `/fleet` 边界与模型锁定规则

## v0.7.0

`ilongrun-coding` 正式升级为带 Superpowers 方法学强化层的 **Coding Discipline Kernel**：保留原有蜂群编排骨架，但把 workspace isolation、task microcycle、claim verification、root-cause recovery、skill engineering 全部写进协议与账本。

### 新增
- **方法学真值**：`config/coding-protocol.jsonc` 新增 `methodologyOverlay / workspaceIsolationPolicy / taskMicrocycle / claimVerificationPolicy / debugPolicy / skillEngineeringPolicy`
- **scheduler 新字段**：`workspaceIsolation / phaseGuards / claimVerification`
- **workstream 新字段**：`specRef / microcycleState / reviewSequence / freshEvidence / rootCauseRecord`
- **新 playbooks**：`workspace-isolation.md / task-microcycle.md / claim-verification.md / recovery-debug.md / skill-engineering.md`
- **skill lint**：新增 `scripts/lint_ilongrun_skills.py`
- **pressure-scenario 参考资料**：新增 `references/skill-engineering-checklist.md` 与 `references/skill-pressure-scenarios.md`
- **Superpowers 研究文档**：新增 `docs/ilongrun+superpowers.md`

### 重构
- **coding 协议升级为 Discipline Kernel**：从“有 review gate 的 coding swarm”升级为“蜂群编排 + 方法学硬门禁”
- **status / doctor / install 链路同步升级**：看板与体检现在识别 methodology overlay、workspace isolation、claim verification、skill lint bundle
- **skill frontmatter 重写**：`ilongrun / ilongrun-coding / ilongrun-resume / ilongrun-status` 的 description 统一改为 `Use when...` 风格
- **launch / finalize / verify 更严格**：build 之外不考虑 fleet；finalize 缺 fresh evidence 时阻断；failed/blocked 缺 root cause record 时阻断

### 增强
- **workspace isolation assessment**：build 前自动评估 git/worktree/branch/in-place 策略；非 git 工作区允许 `skipped` 但必须记录原因
- **task microcycle 硬化**：`spec-lock → red → verify-red → green → verify-green → self-review → spec-review → quality-review → handoff`
- **claim verification 硬化**：fresh evidence 进入 finalize 前硬门禁
- **recovery 更科学**：先写根因记录，再允许 minimal fix
- **status 看板新增方法学门禁区**：明确显示 reviewSequence 未收敛、fresh evidence 缺失、rootCauseRecord 缺失等状态
- **selftest 扩展**：增加 skill lint 的 fail→fix 场景，并覆盖 0.7.0 protocol 字段与 methodology bundle

### 兼容策略
- **新协议优先**：新的 coding run 以 `0.7.0` 为唯一标准
- **旧 run best-effort**：旧 `v0.6.0` run 允许只读 reconcile 与最小字段推断，但若缺新 gate 所需证据，仍会被明确阻断

## v0.6.0

`ilongrun-coding` 正式升级为可长跑、可恢复、可审计的 **Coding Swarm Protocol**：把 coding mission 从“统一纪律文案”重构为“协议真值 + phase playbooks + review gates + vendorized agent-skills 方法库”的完整执行内核。

### 新增
- **`config/coding-protocol.jsonc`**：新增 coding 生命周期、swarm 策略、review matrix、语言画像、release policy 的机器真值
- **`vendor/agent-skills/`**：固化上游精选技能快照与许可证，运行时只消费 iLongRun 适配协议，不再依赖外部仓库
- **`skills/ilongrun-coding/*` playbooks**：新增 `phase-define / phase-plan / phase-build / phase-verify / phase-review / phase-ship / swarm-policy / js-ts-profile`
- **专项 review agents**：新增 `ilongrun-test-engineer.agent.md` 与 `ilongrun-security-auditor.agent.md`
- **doctor 协议 bundle 检查**：新增 coding protocol、vendor snapshot、playbooks、专项 agents 完整性检查

### 重构
- **coding phase 真正独立**：`profile=coding` 现在固定走 `phase-define → phase-plan → phase-build → phase-verify → phase-review → phase-audit → phase-finalize`
- **scheduler / workstream 协议升级**：新增 `codingProtocol / swarmPolicy / dependencyGraph / reviewMatrix` 与 `skillPack / swarmMode / writeSet / handoffArtifacts / entryCriteria / exitCriteria / verificationClass / reviewRequired`
- **`ilongrun-coding` 元技能化**：顶层 `SKILL.md` 改为协议路由器，细节下沉到 phase playbooks
- **投影文档增强**：`strategy.md / plan.md / task-list-N.md / workstream brief` 现在会显式展示 swarm 模式、依赖图、write set、handoff、review gate 等协议字段

### 增强
- **build-only `/fleet` 语义**：coding run 仅 `phase-build` 波次允许评估 `/fleet`；`review / audit / finalize / git / release` 一律 internal
- **独立 `phase-review` gate**：code / test-evidence / security 三个 review gate 成为 finalize 前的硬门禁，不能再被 final audit 代替
- **终审/裁决状态收敛**：`phase-audit` 负责最终终审与 release blocker，`phase-finalize` 负责完成态闭环，二者状态会反映在 status/plan/strategy 中
- **doctor / launch / status 看板升级**：新增 coding protocol 版本、swarm active mode、review matrix / gate 状态展示
- **安装器升级**：安装/卸载现在会同步处理 `coding-protocol.jsonc` 与 `vendor/agent-skills/`
- **安装器热修并入 v0.6.0**：补齐缺失 helper / helper launchers，修复已安装 selftest 的 `ModuleNotFoundError`，安装看板新增版本号展示，并正确解析新版 doctor 中文看板
- **模型策略清理**：移除默认配置里的 `Gemini 3.1 Pro`，安装时会自动清理历史 `model-policy.jsonc` 中残留的 `gemini-3.1-pro`

### 测试
- `selftest_ilongrun.py` 已覆盖：
  - 新 coding phase 拓扑
  - coding protocol / review matrix 落盘
  - build wave 的 `/fleet` dispatch/degrade 证据
  - review gate 阻断 finalize
  - 历史 run ledger sync / drift merge / delivery audit 兼容

## v0.5.0

账本一致性与动态投影同步补强：修复 finalize/verifier/task-list 契约错位，引入确定性 ledger sync，并补上对已完成 run 的状态清理。

### 修复
- **finalize/verifier 契约统一**：不再强依赖 `workstreams[*].index`；历史 run 缺失 `index` 时也能安全 verify / sync
- **run 完成态清理**：`finalize_ilongrun_run.py` 完成后会清理 `active-run-id`，`hook_event.py` 也会拒绝继续向已完成 run 追加 hook 事件
- **完成态兼容**：统一识别 `complete / completed / finalized`，避免已完成 run 因状态枚举差异漏清理、漏告警
- **终审解析修复**：`parse_review_sections()` 现在会正确把 `- None.` 识别为“无 must-fix”，不再误判 review 失败

### 新增
- **`sync_ilongrun_ledger.py`**：确定性对账脚本，可从 `scheduler.json + workstreams/*/status.json` 重建 `plan.md / task-list-N.md` 投影并清理 stale `active-run-id`
- **`scan_ilongrun_delivery_gaps.py`**：新增 JS/TS 交付缺口扫描器，自动识别未接主链模块、重名核心模块、noop provider，并把结果写入 `reviews/delivery-audit.md`
- **真实完成度评分**：verify/finalize 新增 `completionScore`，输出 `codeExists / wiredIntoEntry / tested / runtimeValidated` 四层 evidence-based 分数
- **`render_ilongrun_status_board.py`**：新增本地确定性状态看板，统一展示 completion score、delivery verdict、ledger/projection 状态与风险摘要
- **动态 task-list 勾选**：`task-list-N.md` 的 `[x] / [ ]` 改为由结构化 checklist 状态回写，不再永远停留在空勾选模板
- **`scheduler.taskLists[]` 契约**：为 task-list 投影提供显式索引，减少 verifier 与 projection 之间的隐式猜测
- **`Ledger Syncer` 角色**：新增专责角色说明与默认模型映射，明确“确定性脚本优先，子代理兜底”的同步策略

### 增强
- **漂移探测**：verify 现在会识别 `mission.md / plan.md` 状态漂移、`active-run-id` 残留、`completedAt < startedAt`、task-list 映射缺失等问题
- **假完成拦截**：coding verify 现在会把高置信度 delivery audit 结果升级为 drift finding，直接阻断“模块存在但未接主链”的账面完工
- **计划/完成摘要可见性**：`plan.md` 与 `COMPLETION.md` 会直接展示 completion score，方便快速识别“代码多但接线差”的 run
- **状态查看体验统一**：`ilongrun-status` 优先走本地 helper，不再依赖模型生成中文看板；风格与 install / doctor / launch 看板保持一致
- **reconcile 先补投影再 verify**：`reconcile_ilongrun_run.py` / `sync_ilongrun_ledger.py` 先重建投影再校验，减少“明明能修却先报错”的假失败
- **报告模板统一**：review / adjudication / completion 收敛到统一章节骨架，并修复 `## Verdict` 被误算进 residual risks 的解析漂移
- **`/fleet` 运行证据链**：新增 `fleetCapability` 的 probe 证据字段与 `fleetDispatch.dispatchEvents[]`，并在 verify / status board 中展示 completed/degraded/probe 证据

### 测试
- selftest 新增覆盖：
  - finalize 后自动清理 `active-run-id`
  - hook 不再写入已完成 run
  - 缺失 `taskLists[]` / `index` 的 run 仍可成功 sync
  - task-list 复选框自动从 `[ ]` 更新为 `[x]`
  - 非法时间戳顺序会被标记为 drift

## v0.4.0

run 协议统一化与模型配置化：修复 split-run 漂移、清除旧 `copilot-mission-control` 污染路径，并把默认模型收敛到单一 JSONC 配置。

### 修复
- **run 漂移根因修复**：统一 canonical run 目录为 `.copilot-ilongrun/runs/<run-id>/`，辅助脚本在 reconcile/verify/finalize 时会自动收敛旧的 `.copilot-ilongrun/<run-id>/`
- **历史 run 自愈**：新增 legacy merge 逻辑，会把旧根目录下的 review/result/evidence/journal 迁回 canonical run，并把迁移记录写入 `.copilot-ilongrun/legacy-imports/run-merges/`
- **旧插件冲突治理**：`install.sh`、`ilongrun-doctor`、`copilot-ilongrun` 启动前都会自动尝试卸载 `copilot-mission-control`，避免工作区再生成 `.copilot-mission-control/`
- **工作区治理**：已有 `.copilot-mission-control/` 会自动归档到 `.copilot-ilongrun/legacy-imports/` 后移除，只保留一个状态根目录

### 安装器更新
- **一键安装先彻底清理再重装**：`install.sh` / `scripts/install-all.sh` 现在会先执行完整清理，卸载旧 `ilongrun / longrun / copilot-mission-control` 插件定义，删除旧缓存、旧 launchers、旧 personal skills/agents，以及 `~/.copilot-ilongrun` / `~/.copilot-mission-control`，然后再安装新版插件与命令
- **新增 `cleanup-copilot-longrun-state.sh`**：把彻底清理逻辑沉淀为可复用 helper，避免重复手工排查和手工删除
- **一键安装中文看板**：安装流程现在会输出品牌化中文安装向导 / 安装看板，补齐新手引导、安装成功提示与社区欢迎语
- **看板风格回归简洁**：安装看板、detached 启动看板与状态看板规范保持原始无额外配色的简洁风格，同时保留右侧开口框与统一版式
- **安装兼容 `curl | bash`**：修复通过标准输入执行时 `BASH_SOURCE[0]` 为空导致的 `unbound variable` 提示
- **模型配置提醒补齐**：安装看板会显式告诉用户默认模型配置文件位置，以及 `commandDefaults / skillDefaults / codingAuditModel` 的修改入口
- **doctor 体检看板升级**：`ilongrun-doctor --refresh-model-cache` 改为输出面向新手的中文环境体检看板，整合命令入口、登录状态、模型缓存、自检结果与 `/fleet` 能力摘要，不再把长串原始日志直接倾倒到终端

### 新增
- **`model-policy.jsonc`**：默认模型改为注释化 JSONC 配置，支持 `commandDefaults` / `skillDefaults` / `roleModels` / `codingAuditModel` / `fallback`
- **共享 detached 启动看板**：`ilongrun` / `ilongrun-coding` / `ilongrun-resume` 启动后会输出统一品牌风格的中文看板
- **共享终端主题 helper**：新增 `_ilongrun_terminal_theme.py`，统一开口框、广告语等号框与终端渲染逻辑；默认不主动启用额外配色
- **`cleanup_legacy_workspace.py` helper**：负责归档并清理旧 `.copilot-mission-control/`
- **`render_ilongrun_launch_board.py` helper**：负责渲染 detached 启动摘要看板

### 增强
- **默认模型映射**：
  - `ilongrun` / `status` / `prompt` / `resume` / `doctor` → `Claude Sonnet 4.6`
  - `ilongrun-coding` → `Claude Opus 4.6`
  - coding 最终终审 → `GPT-5.4`
- **文案统一**：对外展示从“固定 GPT-5.4 终审”改为“最终终审（实际模型由配置控制）”，但继续保留 `reviews/gpt54-final-review.md` 兼容路径
- **doctor / probe**：模型探测改为围绕“默认模型 + 回退链”展开，不再依赖旧 preferred 列表

### 文档
- README 新增“默认模型与配置文件”和“目录治理”章节
- 新增 `docs/发版说明-v0.4.0.md`
- 快速开始补充 JSONC 配置与单根目录规则

## v0.3.0

macOS 通知链路回归：把 LongRun 中成熟的系统提醒能力按 iLongRun 当前架构完整补回。

### 新增
- **`notify_macos.py` helper**：支持 `launched` / `resumed` / `recovery` / `attention` / `complete` / `blocked` / `checkpoint` 七类通知事件
- **后端回退链路**：优先 `terminal-notifier`，不可用时自动回退到 `osascript`
- **通知去重状态**：写入 `.copilot-ilongrun/state/notify-<run-id>.json`，避免短时间重复轰炸
- **`ilongrun-doctor --notify-test`**：可主动发送一条 macOS 测试通知，检查权限与提醒链路

### 增强
- **launcher**：`ilongrun` / `ilongrun-resume` detached 启动成功后会发送 `launched` / `resumed` 通知
- **supervisor**：首次模型 fallback / 自动恢复时发送 `recovery` 通知
- **finalize**：complete precheck 失败时发送 `attention`；真正 `complete` / `blocked` 时发送结果通知
- **安装脚本**：Darwin 环境优先准备 `terminal-notifier`，失败后保底回退基础 macOS 通知
- **selftest**：新增通知 helper dry-run 测试，覆盖 launched / complete 与打开目标解析
- **热修：`ilongrun-coding` 命令入口补齐**：一键安装现在会安装 `ilongrun-coding` launcher，且该入口会显式强制 `profile=coding`
- **doctor**：新增 launcher 完整性检查，缺失 `ilongrun-coding` 时会明确提示重新执行安装脚本

### 文档
- 新增 `docs/发版说明-v0.3.0.md`
- README、快速开始与 doctor 说明补充通知自检命令参考
- README / 快速开始 / 发版说明同步补写 `ilongrun-coding` 的用户入口语义与重装说明

## v0.2.1

状态看板中文化升级：聚焦 `ilongrun-status` 的终端呈现体验，让默认输出从“英文结构化看板”升级为“中文结构化看板”。

### 优化
- **`ilongrun-status` 技能**：新增“默认中文输出”总规则，要求 section 标题、字段标签、状态值、模式值、backend 标记统一中文化
- **展示映射**：补齐 status / mode / profile / control mode / backend / verdict / 内置 phase 的中文展示映射
- **示例输出**：将 office profile 示例完整改写为中文状态看板，减少英文提示对用户体感的割裂
- **终端文案**：明确禁止默认输出整块英文看板，必要时仅在中文后补充原始值

### 文档
- 新增 `docs/发版说明-v0.2.1.md`
- README 文档索引补充 v0.2.1 发版说明

## v0.2.0

深度编码纪律升级：整合 agent-skills 最佳实践，使 iLongRun 在 coding 任务场景下具备完整的编码执行纪律。

### 新增
- **`ilongrun-coding` 技能**：编码纪律单一真值源，涵盖 TDD、增量实现、系统化调试、五轴代码审查、安全加固、性能优化、Git 工作流
- **`ilongrun-code-reviewer` 代理**：五轴代码审查专家（正确性/可读性/架构/安全性/性能）
- **参考清单**：`references/testing-patterns.md`、`references/security-checklist.md`、`references/performance-checklist.md`
- **编码生命周期映射**：DEFINE → PLAN → BUILD → VERIFY → REVIEW → SHIP 六阶段指导
- **合理化借口防御**：识别并拒绝跳过纪律的常见借口
- **Red Flags 危险信号**：出现时要求立即停下检查
- **Verification Checklist**：任务完成前的必查清单

### 增强
- **主 skill (`ilongrun`)**：新增 Coding 生命周期感知、合理化借口防御、Red Flags、Verification Checklist
- **Executor 代理**：新增 TDD 循环、Stop-the-Line 规则、增量实现原则、五步排查法
- **GPT-5.4 Audit Reviewer 代理**：新增五轴审查框架、严重性分级、参考清单集成
- **Mission Governor 代理**：新增 Coding 生命周期感知、合理化借口防御、Adjudication 裁决规则
- **Strategy Synthesizer 代理**：新增 Coding 任务画像增强、垂直切片策略、大小估算指南
- **Phase Planner 代理**：新增 Coding 任务 Phase 映射、Wave 资格评估
- **Workstream Planner 代理**：新增大小估算、垂直切片要求、Acceptance/Verify 模板
- **Recovery Agent 代理**：新增系统化调试流程、Stop-the-Line 规则、恢复场景表
- 卸载脚本兼容新增文件

### 致谢
- 编码纪律灵感来自 [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills)

## v0.1.0

首个公开版本，完成独立项目拆仓与首发发布。

### 新增
- 独立插件身份 `ilongrun`
- 独立状态目录 `.copilot-ilongrun/`
- `scheduler.json` 五层任务真值模型
- `plan.md / strategy.md / task-list-N.md / workstreams/*` 投影链路
- GPT-5.4 coding 终审与 `reviews/adjudication.md`
- `/fleet` 能力探测与 wave 级外部 dispatch / 自动降级
- 一键安装脚本 `install.sh`
- 中文 README、快速开始和架构说明

### 默认策略
- 主编排 / 常规执行：Claude Opus 4.6
- 复杂逻辑 / 代码审计 / 最终终审：GPT-5.4

### 已知限制
- `/fleet` 是否可用以本机 Copilot CLI 实际能力探测为准
- 某些环境下若 `copilot plugin install` 失败，仍可通过本地 skills + launchers 方式正常使用
