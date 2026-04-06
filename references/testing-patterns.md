# 测试模式速查

> 来源：iLongRun 编码纪律 · 灵感来自 [agent-skills](https://github.com/addyosmani/agent-skills)

## 测试结构：AAA 模式

```
Arrange  → 准备测试数据和环境
Act      → 执行被测行为
Assert   → 验证结果符合预期
```

## 测试命名

```
test("当 <条件> 时，应该 <预期行为>")
test("given <前置条件> when <动作> then <结果>")
```

## 常用断言模式

| 场景 | 模式 |
|------|------|
| 值相等 | `expect(result).toBe(expected)` |
| 对象相等 | `expect(result).toEqual(expected)` |
| 包含 | `expect(array).toContain(item)` |
| 异常 | `expect(() => fn()).toThrow(ErrorType)` |
| 异步 | `await expect(promise).resolves.toBe(...)` |
| Mock 调用 | `expect(mock).toHaveBeenCalledWith(...)` |

## Mock 原则

- 只 mock 外部依赖（网络、数据库、文件系统）
- 不要 mock 被测模块本身
- Mock 应该反映真实行为（返回合理数据）
- 优先使用 spy 而非完全替换

## 测试金字塔

```
        /  E2E  \        ← 少量，验证关键路径
       / 集成测试 \       ← 适量，验证模块协作
      /  单元测试   \     ← 大量，验证逻辑正确性
```

## React/组件测试

```javascript
// 测试用户行为，不测试实现细节
render(<Button onClick={handler}>Click</Button>);
await userEvent.click(screen.getByRole('button'));
expect(handler).toHaveBeenCalledOnce();
```

## API 集成测试

```javascript
// 测试真实 HTTP 契约
const response = await request(app).get('/api/users').expect(200);
expect(response.body).toMatchObject({ users: expect.any(Array) });
```

## 测试反模式

| 反模式 | 问题 | 修复 |
|--------|------|------|
| 脆弱测试 | 依赖实现细节 | 测试公共接口 |
| 万能测试 | 一个测试验证太多 | 拆成独立测试 |
| 慢测试 | 阻塞开发流程 | 隔离 I/O，用 mock |
| 互相依赖 | 执行顺序影响结果 | 每个测试独立设置 |
| 无断言 | 测试永远通过 | 必须有明确断言 |
| 快照滥用 | 变更噪音大 | 只对稳定输出用快照 |
