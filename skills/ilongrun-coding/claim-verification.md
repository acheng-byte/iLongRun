# Claim Verification

## 核心原则

**没有 fresh evidence，就不能说“完成”。**

## fresh evidence 最少包含

- 命令
- 时间
- exit code
- 摘要

## finalize 硬门禁

- required build / verify workstream 缺 fresh evidence 时，禁止 finalize complete
- 只接受新鲜证据，不接受“上次应该跑过”
- claimVerification 要把缺失 workstream 明确列出来

## 常见反模式

- 只写“已验证”但没有命令
- 复制旧 evidence 当新 evidence
- 代码改完了，却没重新跑验证
