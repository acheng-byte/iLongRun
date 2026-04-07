# Recovery Debug

## 核心原则

**没有 root cause record，就不要直接修。**

## recovery 顺序

```text
failure observed → root cause investigation → hypothesis → minimal fix → verify → rejoin
```

## root cause record 至少包含

- symptom
- hypothesis
- evidence
- fix
- guard

## 适用场景

- workstream 进入 `failed`
- workstream 进入 `blocked`
- resume 发现上次失败原因没有写清楚

## 目标

- 避免猜修
- 避免同一个坑反复踩
- 让下一个恢复者一眼看懂卡点在哪里
