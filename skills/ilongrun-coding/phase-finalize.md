# phase-finalize

## 目标

在所有 gate 收敛后完成收尾，生成完成态摘要。

## 核心职责

- 写 `COMPLETION.md`
- 校验 claim verification 已完整
- 清理 active-run-id
- 确认 release readiness

## 边界

- 不重新裁决 must-fix
- 不替代 phase-audit 的最终终审结论
- gate 未收敛时不得强行 complete
