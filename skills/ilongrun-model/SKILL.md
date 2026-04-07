---
name: ilongrun-model
description: Use when you want to inspect, set, or reset the default iLongRun primary model templates for future run/coding missions.
allowed-tools: ["bash", "view"]
user-invocable: true
disable-model-invocation: false
---

仅用于查看或切换 iLongRun 后续新任务的默认主模型模板。

## 总原则

- 这不是运行态账本编辑器，不要回写当前 active run 的 `scheduler.json`
- 只影响未来新启动的 `ilongrun` / `ilongrun-coding`
- `resume` 默认应继续继承目标 run 既有模型，不被这里的新默认值打断
- 审查模板保持独立：review roles 与 final audit 不跟随主模型切换

## 执行方式

- 查看当前模板：运行 `ilongrun-model`
- 设置主模型：运行 `ilongrun-model <slug-or-alias>`
- 恢复模板默认值：运行 `ilongrun-model reset`

## 输出要求

- 用简体中文简要说明：
  - 当前或更新后的主执行模板
  - 审查模板仍固定为 `gpt-5.4`
  - 哪些配置路径已更新
  - 哪些路径因当前目录不是 iLongRun 仓库而跳过
