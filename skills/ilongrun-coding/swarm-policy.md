# swarm-policy

## 核心公式

蜂群 = 协调器 + Worker + 依赖图 + 波次执行 + 上下文记忆

## 模式

- `serial`：严格串行，适合 release / adjudication / finalize
- `swarm-wave`：有依赖，按波次推进
- `super-swarm`：完全独立，同时启动

## Worker 合同

每个 worker 的 brief 都必须像迷你需求文档：

- 输入
- 输出
- 约束
- 写集合
- 依赖
- 验收
- 验证

## 协调器记忆

协调器通过 `scheduler.json`、`journal.jsonl`、`projection-sync.jsonl` 保留跨 wave 记忆。
