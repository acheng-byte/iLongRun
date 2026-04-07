# Skill Engineering

## 目标

把 iLongRun 的技能从“说明文档”升级成“可验证的方法学组件”。

## 规则

- frontmatter `description` 只写 `Use when...`
- 高频 skill 要保持短、准、可交叉引用
- 复杂流程拆到 playbook，不要把顶层 skill 写成巨型文档
- 需要有 skill lint
- 需要有 pressure scenario

## 最少检查项

- trigger-first frontmatter
- 必要章节存在
- 词数预算不过载
- cross-reference 指向真实文件

## 目标结果

- 更稳定触发
- 更低 token 噪音
- 更容易维护与演进
