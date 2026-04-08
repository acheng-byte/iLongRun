# iLongRun 仓库协作指南

本文件是 iLongRun 的仓库级协作规范。对本仓库进行实现、文档、安装、诊断、发版或审查时，默认遵守本文。

## 1. 项目结构

- 顶层元数据与安装入口：`plugin.json`、`hooks.json`、`install.sh`、`uninstall.sh`
- 核心命令与脚本：`scripts/`
  - Bash 薄包装命令，如 `scripts/ilongrun`、`scripts/ilongrun-coding`
  - Python 调度/诊断脚本，如 `prepare_ilongrun_run.py`、`selftest_ilongrun.py`
- 内部协议资产：
  - `skills/`：工作流规则、纪律真值源
  - `agents/`：角色型 agent 定义
- 运行策略：`config/*.jsonc`
- 用户文档：`README.md`、`CHANGELOG.md`、`docs/`
- 参考资料与上游快照：`references/`、`vendor/`

原则：命令入口、技能真值、代理角色、配置策略、用户文档分层清晰，不要混用职责。

## 2. 项目硬性约束

### 2.1 发版默认是交付的一部分

每次版本迭代默认包含 GitHub 发版计划，不把“是否发版”当成额外决策。

如果改动影响以下任一内容，必须同步更新发版说明与 GitHub Release：

- 对外行为
- 安装方式
- 命令入口
- 诊断命令
- 通知链路
- 版本号
- 用户可见文案

发版说明默认：中文为主、标题清晰、结构稳定，重点覆盖“概述 / 新增 / 增强 / 文档 / 说明 / 安装升级”。

### 2.2 文档同步是默认动作

只要改动会影响用户认知或操作路径，默认同步：

- `README.md`
- `docs/快速开始.md`
- `CHANGELOG.md`
- 对应版本的 `docs/发版说明-vX.Y.Z.md`

必要时同步：

- `plugin.json`
- 安装 / 卸载脚本
- `ilongrun-doctor` 的提示文案

要求：新命令、新入口、新默认行为、新诊断项，不能只改代码不改文档；上述文档说法必须一致。

### 2.3 命令入口与技能入口分层

- 用户直接执行的是 **shell 命令入口**。
- `skills/` 中的是 **内部技能 / 协议 / 纪律真值源**。
- 不要把两者混为一谈。

新增用户命令时，必须同时检查：

- 安装脚本是否安装
- 卸载脚本是否移除
- `ilongrun-doctor` 是否检查
- README / 快速开始是否给出示例

当前已确认语义：

- `ilongrun`：通用长跑入口，自动推断 `profile`
- `ilongrun-coding`：显式 coding 长跑入口，默认 detached，并强制 `profile=coding`
- `skills/ilongrun-coding`：内部 discipline skill，不是用户直接调用的顶层入口

### 2.4 `ilongrun-doctor` 负责安装完整性检查

`ilongrun-doctor` 不只是环境检查，还必须核验安装是否完整。

至少覆盖：

- `ilongrun`
- `ilongrun-coding`
- `ilongrun-prompt`
- `ilongrun-resume`
- `ilongrun-status`
- `ilongrun-doctor`
- `copilot-ilongrun`

如果某个 skill 已存在，但对应 shell launcher 没装上，doctor 必须明确报错或给出重装建议，不能静默通过。

### 2.5 发版前后固定检查

默认执行：

- `git diff --check`
- 脚本 / Python 语法检查
- 项目自测
- `ilongrun-doctor`
- 关键命令可用性验证
- Release 正文与 README / 快速开始 / CHANGELOG 一致性检查

### 2.6 维护原则

- 改动尽量可回滚、可复现
- 用户可见变化优先中文表达；命令名、参数名、机器字段保持原样
- 优先补齐现有链路，不做表层修补
- 若局部实现与历史约束冲突，优先按当前运行行为，再按本文理解，再按静态源码理解

## 3. 常用开发与验证命令

- `bash install.sh`：本地安装插件与 launcher
- `bash scripts/copilot-ilongrun`：查看 CLI 帮助
- `python3 scripts/selftest_ilongrun.py`：运行主回归 / 自测
- `python3 scripts/lint_ilongrun_skills.py`：校验 `skills/` 与 `agents/`
- `bash scripts/ilongrun-doctor --refresh-model-cache`：检查安装与模型配置
- `git diff --check`：patch / 空白字符检查

补充：

- 改了 `skills/` 或 `agents/`，默认跑 `python3 scripts/lint_ilongrun_skills.py`
- 改了调度真值、命令路由、安装链路、review / audit 输出或 doctor 行为，默认跑 `python3 scripts/selftest_ilongrun.py`

## 4. 代码风格与命名

### Python

- Python 3
- 4 空格缩进
- 优先类型注解与 `Path`
- 文件统一 UTF-8
- 风格与现有 helper 保持一致

### Bash

- 以 `#!/usr/bin/env bash` 开头
- 默认 `set -euo pipefail`
- 保持脚本为薄包装或清晰编排层

### 命名与文案

- CLI 包装器：连字符，如 `ilongrun-status`
- Python helper：下划线，如 `sync_ilongrun_ledger.py`
- 中文文档放在 `docs/`，文件名清晰
- 用户文案尽量中文；命令名、flag、模型 slug、JSON 机器字段保持英文原样

## 5. 测试与回归

当前没有独立 `tests/` 目录，`scripts/selftest_ilongrun.py` 是主要回归入口。

以下场景优先补或改自测：

- scheduler 真值结构变化
- installer / uninstall 行为变化
- 命令入口路由变化
- review / audit / finalize 产物变化
- doctor 检查项或报告逻辑变化

要求：

- 行为变化型补丁应增加或更新自测断言
- 不能只改行为不补验证
- 修 bug 时优先补回归证明

## 6. 提交与 PR 规范

### Commit 风格

沿用以下前缀：

- `feat:`
- `fix:`
- `docs:`
- `release:`
- `chore:`
- `install:`
- `ui:`
- `doctor:`

提交信息要短、准、祈使式，例如：

- `fix: harden doctor selftest reporting`
- `docs: align release notes with install flow changes`

### PR 要求

PR 需要说明：

- 用户可见影响
- 受影响命令 / 文档
- 做了哪些验证

如果行为、安装流程或文案发生变化，必须一并更新：

- `README.md`
- `docs/快速开始.md`
- `CHANGELOG.md`
- 对应版本的 `docs/发版说明-vX.Y.Z.md`

## 7. 安全与配置

- 不要提交生成态的 `.copilot-ilongrun/` 运行状态
- 不要提交本地 `.codex/` 产物
- `config/model-policy.jsonc` 是模型路由真值源
- `config/coding-protocol.jsonc` 是 coding gate 真值源
- 修改模型路由、coding gate、安装行为、命令入口时，要同步考虑 doctor、自测、文档、发版说明是否需要更新

## 8. 面向 agent 的默认工作方式

- 先理解当前链路，再动手改实现
- 优先补齐现有链路，不凭空新增并行体系
- 对用户可见变化，优先同步文档与发版材料
- 对安装 / 诊断 / 命令入口改动，优先检查是否形成完整闭环
- 对 coding 纪律、review gate、audit gate、finalize gate 相关改动，优先保持真值单一、投影一致、状态可验证
