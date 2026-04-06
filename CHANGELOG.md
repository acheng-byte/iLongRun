# 更新日志

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
