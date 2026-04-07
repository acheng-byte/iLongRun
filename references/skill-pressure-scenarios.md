# Skill Pressure Scenarios

## 场景 1：description 写成功能摘要
- 目标：确保 lint 拒绝非 `Use when...` 描述

## 场景 2：顶层 skill 过长
- 目标：确保高频 skill 被提示拆分到 playbook

## 场景 3：cross-reference 失效
- 目标：确保 lint 能发现引用文件不存在

## 场景 4：coding skill 缺失关键 playbook
- 目标：确保 `ilongrun-coding` 不会在 bundle 不完整时通过

## 场景 5：resume skill 没有说明 legacy / gate 处理
- 目标：确保恢复策略不会绕过 methodology guard
