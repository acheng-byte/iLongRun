# iLongRun 项目硬性约束

这份文件记录已经在历史对话中反复确认、且后续迭代应默认遵守的项目规则。
如果与局部实现冲突，优先按当前运行行为、再按本文件、再按源代码理解。

## 1. 版本迭代默认执行 GitHub 发版计划

- 每一次版本迭代更新任务，默认都要包含 GitHub 发版计划，不要把“是否发版”当成额外决策。
- 发版要求要延续近期发版的描述风格：
  - 中文为主
  - 标题清晰
  - 结构稳定
  - 重点说明“概述 / 新增 / 增强 / 文档 / 说明 / 安装升级”
- 如果本次迭代对外行为、安装方式、命令入口、诊断命令、通知链路、版本号或用户可见文案有变化，必须同步更新对应发版说明与 GitHub Release 正文。

## 2. 文档同步是默认动作

只要改动会影响用户认知或操作路径，优先同步这些文档：

- `README.md`
- `docs/快速开始.md`
- `CHANGELOG.md`
- 对应版本的 `docs/发版说明-vX.Y.Z.md`

必要时还要同步：

- `plugin.json`
- 安装 / 卸载脚本
- `ilongrun-doctor` 的检查与提示文案

原则：

- 新命令、新入口、新默认行为、新诊断项，不能只改代码不改文档。
- README / 快速开始 / 发版说明 / CHANGELOG 的说法要保持一致，不能互相打架。

## 3. 命令入口与技能入口必须分层清楚

- 用户在终端直接敲的，必须是**shell 命令入口**。
- `skills/` 里的内容是**内部技能/纪律真值源**，不能和用户入口混为一谈。
- 如果新增一个用户命令，必须同时检查：
  - 安装脚本是否会装进去
  - 卸载脚本是否会移除
  - `ilongrun-doctor` 是否会检查
  - README / 快速开始是否有示例

### 当前已经确认的语义

- `ilongrun`：通用长跑入口，按任务内容自动推断 profile。
- `ilongrun-coding`：显式 coding 长跑入口，默认 detached，并强制 `profile=coding`。
- `skills/ilongrun-coding`：内部 discipline skill，负责 coding 任务的编码纪律单一真值源，不是用户直接调用的顶层入口。

## 4. `ilongrun-doctor` 是安装完整性检查入口

`ilongrun-doctor` 不只是环境检查，还要承担“安装是否完整”的核验职责。

至少要覆盖：

- `ilongrun`
- `ilongrun-coding`
- `ilongrun-prompt`
- `ilongrun-resume`
- `ilongrun-status`
- `ilongrun-doctor`
- `copilot-ilongrun`

如果某个 skill 已存在，但对应 shell launcher 没装上，doctor 必须明确报错或给出重装建议，不能静默通过。

## 5. 发版前后的固定检查

每次版本迭代在发版前后，默认执行以下检查：

- `git diff --check`
- 脚本语法检查 / Python 语法检查
- 项目自测
- `ilongrun-doctor`
- 关键命令可用性验证
- Release 正文与 README / 快速开始 / CHANGELOG 的一致性检查

## 6. 维护原则

- 尽量保持改动可回滚、可复现。
- 用户可见变化优先中文化表达，但命令名、参数名、日志中的机器值保持原样。
- 新增行为以“补齐现有链路”为优先，不要只做表面文案修补。

