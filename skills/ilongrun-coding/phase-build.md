# phase-build

## 目标

以 TDD + 增量实现交付 build 产物。

## RED → GREEN → REFACTOR

1. 先写失败测试或证明失败的验证
2. 用最小实现让它通过
3. 在通过状态下重构

## 波次建议

- foundation
- implementation
- integration

## fleet 规则

只有 build wave 才允许 `fleet`，且必须 writeSet 不重叠。
