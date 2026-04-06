# 安全清单速查

> 来源：iLongRun 编码纪律 · 灵感来自 [agent-skills](https://github.com/addyosmani/agent-skills)

## 提交前检查

- [ ] 无硬编码密钥、密码、token
- [ ] `.env` 文件在 `.gitignore` 中
- [ ] 敏感配置走环境变量
- [ ] 无 `console.log` 泄露敏感数据

## 认证

- [ ] 密码用 bcrypt/argon2 哈希（cost ≥ 10）
- [ ] Token 有过期时间
- [ ] 刷新 token 一次性使用
- [ ] 登录失败有速率限制
- [ ] 密码重置 token 一次性 + 有效期

## 授权

- [ ] 服务端验证权限（不只依赖前端）
- [ ] 最小权限原则
- [ ] 资源访问检查 ownership
- [ ] Admin 接口额外保护

## 输入验证

- [ ] 所有外部输入在边界处验证
- [ ] 用白名单而非黑名单
- [ ] SQL 用参数化查询/ORM
- [ ] 文件上传验证类型 + 大小 + 内容
- [ ] URL 重定向只允许白名单域名

## 安全头

```
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
Content-Security-Policy: default-src 'self'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
```

## CORS 配置

- [ ] 不使用 `Access-Control-Allow-Origin: *`（生产环境）
- [ ] 白名单指定允许的 origin
- [ ] 限制允许的 HTTP method
- [ ] 敏感接口需要 `credentials: true`

## 数据保护

- [ ] 传输加密（TLS 1.2+）
- [ ] 静态加密（敏感字段）
- [ ] PII 数据最小化收集
- [ ] 日志不记录敏感数据
- [ ] 备份加密

## 依赖安全

```bash
npm audit --production          # Node.js
pip audit                       # Python
cargo audit                     # Rust
gh api /repos/{owner}/{repo}/vulnerability-alerts  # GitHub
```

- [ ] 无已知高危漏洞
- [ ] 依赖锁文件（lock file）已提交
- [ ] 定期更新依赖

## 错误处理

- [ ] 错误响应不泄露内部细节
- [ ] 堆栈跟踪不暴露给用户
- [ ] 统一错误格式
- [ ] 错误日志包含上下文但不含敏感数据

## OWASP Top 10 速查

| # | 风险 | 关键防护 |
|---|------|----------|
| A01 | 权限控制失效 | 服务端权限校验 + 默认拒绝 |
| A02 | 加密失败 | TLS + 加密存储 + 密钥管理 |
| A03 | 注入 | 参数化查询 + 输入验证 |
| A04 | 不安全设计 | 威胁建模 + 安全设计评审 |
| A05 | 安全配置错误 | 最小化默认配置 + 自动化检查 |
| A06 | 脆弱/过期组件 | 依赖审计 + 自动更新 |
| A07 | 认证失败 | MFA + 强密码策略 + 速率限制 |
| A08 | 数据完整性失败 | 签名验证 + CI/CD 安全 |
| A09 | 日志/监控不足 | 结构化日志 + 告警 + 审计 |
| A10 | SSRF | URL 白名单 + 网络隔离 |
