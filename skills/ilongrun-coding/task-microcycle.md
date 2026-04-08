# Task Microcycle

## 作用

把每个 build workstream 从“接任务就写代码”，升级成固定的小闭环。

## 固定顺序

```text
spec-lock → red → verify-red → green → verify-green → self-review → spec-review → quality-review → handoff
```

## 含义

- `spec-lock`：先锁定本切片做什么、不做什么
- `red`：先写失败测试或先定义失败条件
- `verify-red`：确认红灯是真的
- `green`：最小实现通过
- `verify-green`：重新跑验证，确认绿灯
- `self-review`：自己先看有没有明显偏题或脏改动
- `spec-review`：对照 contract 检查有没有跑偏
- `quality-review`：检查可读性、安全、性能、接线质量
- `handoff`：写 result / evidence / status 并把产物交出来

## 硬规则

- 顺序不能乱
- 后面的步骤不能伪造完成
- build workstream 想标 `complete`，必须 microcycle 收敛
