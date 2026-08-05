// HiFiNi 签到代理中继 Cloudflare Worker
// 部署到 Cloudflare Workers 后，GitHub Actions 通过此 Worker 中继签到请求
// 免费额度: 每天 100,000 次请求，完全够用
//
// 部署步骤:
// 1. 注册 Cloudflare 账号: https://dash.cloudflare.com/sign-up
// 2. 安装 wrangler CLI: npm install -g wrangler
// 3. 登录: wrangler login
// 4. 在本仓库 workers/ 目录下执行: wrangler deploy
// 5. 将部署后的 URL (如 https://hifini-relay.xxx.workers.dev) 
//    添加到 GitHub Secrets 中，名称为 PROXY_WORKER_URL

export default {
  async fetch(request, env) {
    // 从 URL 中解析目标域名和路径
    const url = new URL(request.url);
    const targetDomain = url.searchParams.get('domain') || 'https://www.hifini.com.cn';
    // 去掉 query params 中的 domain，保留其他路径
    const targetPath = url.pathname;
    const targetUrl = targetDomain + targetPath;

    // 转发请求头（移除 Cloudflare 和 Host 相关头）
    const forwardHeaders = new Headers();
    const skipHeaders = new Set(['host', 'cf-connecting-ip', 'cf-ray', 'cf-ipcountry', 
                                  'cf-visitor', 'x-forwarded-for', 'x-forwarded-proto',
                                  'x-real-ip', 'cdn-loop']);
    
    for (const [key, value] of request.headers.entries()) {
      if (!skipHeaders.has(key.toLowerCase()) && !key.toLowerCase().startsWith('cf-')) {
        forwardHeaders.set(key, value);
      }
    }

    // 确保关键请求头存在
    if (!forwardHeaders.has('User-Agent')) {
      forwardHeaders.set('User-Agent', 
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36');
    }

    try {
      const resp = await fetch(targetUrl, {
        method: request.method,
        headers: forwardHeaders,
        body: request.method === 'POST' ? request.body : undefined,
        redirect: 'follow',
      });

      // 将原始响应头中的 Set-Cookie 等信息也转发回来
      const responseHeaders = new Headers();
      for (const [key, value] of resp.headers.entries()) {
        responseHeaders.append(key, value);
      }
      responseHeaders.set('X-Relay-Status', 'OK');
      responseHeaders.set('X-Relay-Target', targetUrl);
      responseHeaders.set('Access-Control-Allow-Origin', '*');

      return new Response(resp.body, {
        status: resp.status,
        headers: responseHeaders,
      });
    } catch (e) {
      return new Response(JSON.stringify({ 
        relay_error: true, 
        message: e.message,
        target: targetUrl 
      }), {
        status: 502,
        headers: { 'Content-Type': 'application/json' },
      });
    }
  },
};
