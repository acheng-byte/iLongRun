# phase-review

## 目标

把 review 固化为独立 gate。

## 默认 review gate

- `review-code`
- `review-test-evidence`
- `review-security`

## 约束

- review gate 不能被 final audit 替代
- 任一 review 缺失都不得 declare complete
- 空结果也必须显式写 `- None.`
