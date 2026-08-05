# Cloudflare Worker 代理中继部署指南

## 为什么需要代理？

HiFiNi 的 CDN 对来自 GitHub Actions 的美国数据中心 IP 进行了 IP 级别的封锁：
- `curl: (52) Empty reply from server` — 服务器直接返回空响应
- `<script src="/_guard/auto.js"></script>` — 触发 JS 人机验证挑战

**解决方案**：通过 Cloudflare Worker 中继请求。Cloudflare 边缘节点 IP 通常不会被国内 CDN 封锁。

## 部署步骤（约 5 分钟）

### 1. 注册 Cloudflare 账号

访问 https://dash.cloudflare.com/sign-up 注册免费账号。

### 2. 通过 Cloudflare Dashboard 部署 Worker

1. 登录 Cloudflare Dashboard → 左侧菜单点击 **Workers & Pages**
2. 点击 **Create** → **Create Worker**
3. 给 Worker 取个名字，比如 `hifini-relay`
4. 将 `workers/src/index.js` 中的代码粘贴到编辑器中
5. 点击 **Deploy**
6. 部署成功后，你会得到一个 URL，类似：
   ```
   https://hifini-relay.你的用户名.workers.dev
   ```

### 3. 配置 GitHub Secret

1. 打开你的 GitHub 仓库 → **Settings** → **Secrets and variables** → **Actions**
2. 点击 **New repository secret**
3. Name: `PROXY_WORKER_URL`
4. Value: `https://hifini-relay.你的用户名.workers.dev`（替换为你的实际 Worker URL）
5. 点击 **Add secret**

### 4. 验证

在 GitHub Actions 页面点击 **Run workflow**，curl 签到引擎会自动通过 Worker 代理发送签到请求。

## 免费额度

Cloudflare Workers 免费计划：
- **每天 100,000 次请求**（签到每天只需 1-4 次，完全够用）
- **无需绑定信用卡**
- **永久免费**

## 原理

```
GitHub Actions (美国 IP)
    ↓ curl 请求
Cloudflare Worker (边缘节点 IP) 
    ↓ fetch 转发
HiFiNi 服务器 (国内 CDN)
    ↓ 正常响应
Cloudflare Worker
    ↓ 返回签到结果
GitHub Actions
    ↓ WxPusher 推送
你的微信
```
