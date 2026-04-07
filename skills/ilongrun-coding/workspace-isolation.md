# Workspace Isolation

## 作用

在进入 `phase-build` 前，先判断当前 coding run 是否需要隔离工作区，避免多个 build workstream 互相覆盖写集。

## 最小规则

- 先判断当前工作区是否是 git 仓库
- 再判断 build wave 是否存在并行切片
- 再决定优先策略：`worktree` / `branch` / `in-place`
- 没有 git 时允许 `skipped`，但必须留下 `skippedReason`

## 记录要求

`scheduler.json.workspaceIsolation` 至少要记录：

- `assessed`
- `required`
- `status`
- `strategy`
- `gitAvailable`
- `isGitWorkspace`
- `baselineStatus`
- `skippedReason`
- `notes`

## 何时 stop-the-line

- build wave 已并行，但还没做 isolation assessment
- 发现 baseline 已 dirty，且 writeSet 很可能相互影响
