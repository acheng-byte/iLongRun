# iLongRun — Claude Code Integration

这些命令文件安装到 `~/.claude/commands/` 后，可在 Claude Code 中直接用 `/ilongrun`、`/ilongrun-prompt` 等斜杠命令调用 iLongRun。

## 安装

```bash
bash scripts/install-agent-adapters.sh --agent claude
```

## 命令列表

| 命令 | 说明 |
|------|------|
| `/ilongrun` | 将任务交给 iLongRun 后端执行 |
| `/ilongrun-prompt` | 生成 iLongRun 任务 Prompt |
| `/ilongrun-resume` | 恢复上次的 iLongRun 任务 |
| `/ilongrun-status` | 查看当前 iLongRun 运行状态 |
