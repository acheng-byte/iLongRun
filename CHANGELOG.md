# 更新日志

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
