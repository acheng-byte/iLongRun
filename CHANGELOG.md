# 更新日志

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
