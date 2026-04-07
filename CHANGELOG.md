# 更新日志

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
