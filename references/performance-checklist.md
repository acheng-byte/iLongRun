# 性能优化清单速查

> 来源：iLongRun 编码纪律 · 灵感来自 [agent-skills](https://github.com/addyosmani/agent-skills)

## Core Web Vitals 目标

| 指标 | 良好 | 需改进 | 差 |
|------|------|--------|-----|
| LCP (最大内容绘制) | ≤ 2.5s | ≤ 4.0s | > 4.0s |
| INP (交互到下一帧) | ≤ 200ms | ≤ 500ms | > 500ms |
| CLS (累积布局偏移) | ≤ 0.1 | ≤ 0.25 | > 0.25 |
| TTFB (首字节时间) | ≤ 800ms | ≤ 1.8s | > 1.8s |

## 前端性能清单

### 图片

- [ ] 使用现代格式（WebP/AVIF）
- [ ] 响应式图片（srcset + sizes）
- [ ] 懒加载非首屏图片
- [ ] 关键图片预加载
- [ ] 明确宽高避免 CLS

### JavaScript

- [ ] 代码分割（路由级别）
- [ ] Tree shaking 清除死代码
- [ ] 延迟加载非关键 JS
- [ ] 避免主线程长任务（> 50ms）
- [ ] Web Worker 处理 CPU 密集计算

### CSS

- [ ] 关键 CSS 内联
- [ ] 移除未使用的 CSS
- [ ] 避免 `@import`（用打包工具）
- [ ] 避免强制同步布局

### 网络

- [ ] 启用压缩（Brotli > gzip）
- [ ] HTTP/2 或 HTTP/3
- [ ] 合理缓存策略（immutable 静态资源）
- [ ] 预连接关键第三方域名
- [ ] 减少请求数量

### 渲染

- [ ] 避免布局抖动
- [ ] `will-change` 合理使用
- [ ] `requestAnimationFrame` 处理动画
- [ ] 虚拟列表处理长列表

## 后端性能清单

### 数据库

- [ ] 慢查询日志已开启
- [ ] 常用查询有索引
- [ ] N+1 查询已消除
- [ ] 连接池大小合理
- [ ] 读写分离（如适用）

### API

- [ ] 响应分页
- [ ] 避免过度获取（GraphQL / 字段筛选）
- [ ] 合理超时设置
- [ ] 并行请求（非依赖请求）

### 基础设施

- [ ] CDN 分发静态资源
- [ ] 自动伸缩配置
- [ ] 健康检查端点
- [ ] 缓存策略（Redis / Memcached）

## 性能测量命令

```bash
# Lighthouse CLI
npx lighthouse https://example.com --output=json --output-path=./report.json

# Web Vitals
npx web-vitals-cli https://example.com

# 构建分析
npx webpack-bundle-analyzer stats.json
npx source-map-explorer build/static/js/*.js

# Node.js profiling
node --prof app.js
node --prof-process isolate-*.log > profile.txt
```

## 常见反模式

| 反模式 | 影响 | 修复 |
|--------|------|------|
| 未优化图片 | LCP 恶化 | 压缩 + 现代格式 + 响应式 |
| 同步第三方脚本 | 阻塞渲染 | async/defer + 延迟加载 |
| 无限滚动无虚拟化 | 内存泄漏 + 卡顿 | 虚拟列表 |
| 全表扫描 | TTFB 飙升 | 添加索引 + EXPLAIN |
| 缓存缺失 | 重复计算 | 合理缓存 + TTL |
| 未压缩传输 | 带宽浪费 | Brotli 压缩 |
