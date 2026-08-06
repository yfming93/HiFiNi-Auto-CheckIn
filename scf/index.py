# -*- coding: utf-8 -*-
# 腾讯云 SCF 云函数 - 多网站自动签到
# 覆盖网站: HiFiNi 磁场 / HiFiKi 音乐 / HiFiTi 音乐
# 部署平台: 腾讯云云函数 (SCF)
# 运行环境: Python 3.9
# 作者: 袁凤鸣

import json
import hashlib
import os
import re
import urllib.request
import urllib.parse
import urllib.error
import ssl
import time
import http.cookiejar
import http.client

# ========== 站点分组定义 ==========
SITES = [
    {
        "name": "HiFiNi 磁场",
        "domains": [
            "https://www.hifini.com.cn",
            "https://www.hifihi.com",
            "https://www.hifini.net",
            "https://www.hifini.com",
        ],
    },
    {
        "name": "HiFiKi 音乐",
        "domains": [
            "https://www.hifiki.com",
            "https://hifiki.com",
        ],
    },
    {
        "name": "HiFiTi 音乐",
        "domains": [
            "https://www.hifiti.com",
            "https://hifiti.com",
        ],
    },
]

SIGN_PATH = "/sg_sign.htm"
LOGIN_PATH = "/user-login.htm"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"


def get_env(key, default=""):
    """获取环境变量"""
    return os.environ.get(key, default).strip()


def md5(text):
    """计算 MD5"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def http_request(url, method="GET", headers=None, data=None, timeout=15):
    """通用 HTTP 请求，返回 (响应体, 响应头字典, 状态码)"""
    if headers is None:
        headers = {}

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    if data and isinstance(data, str):
        data = data.encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            resp_headers = dict(resp.getheaders())
            return body, resp_headers, resp.status
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore") if e.fp else ""
        return body, {}, e.code
    except Exception as e:
        return str(e), {}, 0


def fetch_user_info(domain, cookie):
    """签到成功后获取用户主页 (my.htm)，解析总金币余额和连续签到天数"""
    extra = {}
    headers = {
        "Cookie": cookie,
        "User-Agent": USER_AGENT,
        "Referer": domain + "/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        # 1. 请求 my.htm 页面解析总金币和用户名
        my_page_url = domain + "/my.htm"
        body, _, status = http_request(my_page_url, method="GET", headers=headers)
        if body and status == 200:
            # 匹配: <span class="text-muted">金币：</span><em style="...">869</em>
            coin_match = re.search(r'金币[：:]\s*</span>\s*<em[^>]*>(\d+)</em>', body)
            if coin_match:
                extra["coins"] = int(coin_match.group(1))
                print(f"  [{domain}] 解析到总金币: {extra['coins']}")

            name_match = re.search(r'class="avatar-1"[^>]*>\s*([^<]+)</a>', body)
            if name_match:
                extra["display_name"] = name_match.group(1).strip()

        # 2. 请求 sg_sign.htm 页面解析连续签到天数
        sign_page_url = domain + "/sg_sign.htm"
        sign_body, _, sign_status = http_request(sign_page_url, method="GET", headers=headers)
        if sign_body and sign_status == 200:
            streak_match = re.search(r"连续签到(\d+)天", sign_body)
            if streak_match:
                extra["streak"] = int(streak_match.group(1))
                print(f"  [{domain}] 解析到连续签到: {extra['streak']} 天")
    except Exception as e:
        print(f"  [{domain}] 用户信息获取失败: {e}")

    return extra


def try_sign_with_cookie(domain, cookie):
    """使用 Cookie 尝试签到"""
    sign_url = domain + SIGN_PATH
    headers = {
        "Cookie": cookie,
        "User-Agent": USER_AGENT,
        "X-Requested-With": "XMLHttpRequest",
        "Referer": domain + "/",
        "Origin": domain,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }

    print(f"  [签到请求] -> {sign_url}")
    body, _, status = http_request(sign_url, method="POST", headers=headers, data=b"")

    if not body or status == 0:
        print(f"  [{domain}] 签到请求无响应/网络异常")
        return None

    print(f"  [{domain}] 签到响应: {body.strip()}")

    try:
        result = json.loads(body)
        msg = result.get("message", "")

        if "签到" in msg or "签过" in msg or "金币" in msg:
            print(f"  [✅ 签到成功] {msg}")
            user_extra = fetch_user_info(domain, cookie)
            res = {"success": True, "message": msg, "domain": domain}
            res.update(user_extra)
            return res
        elif "请登录" in msg:
            print(f"  [{domain}] Cookie 失效，需要登录")
            return {"success": False, "message": msg, "need_login": True}
        else:
            print(f"  [{domain}] 响应异常: {msg}")
            return {"success": False, "message": msg}
    except json.JSONDecodeError:
        return {"success": False, "message": body[:200]}


def try_login(domain, username, password):
    """账号密码登录获取 Cookie"""
    login_url = domain + LOGIN_PATH
    md5_pwd = md5(password)

    print(f"  [登录请求] -> {login_url} (MD5: {md5_pwd})")

    headers = {
        "User-Agent": USER_AGENT,
        "X-Requested-With": "XMLHttpRequest",
        "Referer": login_url,
        "Origin": domain,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    form_data = urllib.parse.urlencode({"email": username, "password": md5_pwd})

    parsed = urllib.parse.urlparse(login_url)
    conn = http.client.HTTPSConnection(parsed.hostname, timeout=15,
                                        context=ssl._create_unverified_context())
    try:
        conn.request("POST", parsed.path, body=form_data, headers=headers)
        resp = conn.getresponse()
        resp.read()

        bbs_token = None
        for header_name, header_value in resp.getheaders():
            if header_name.lower() == "set-cookie" and "bbs_token=" in header_value:
                token_part = header_value.split("bbs_token=")[1].split(";")[0].strip()
                if token_part and token_part != "deleted":
                    bbs_token = token_part

        if bbs_token:
            print(f"  [{domain}] 登录成功, bbs_token: {bbs_token[:20]}...")
            return f"bbs_token={bbs_token}"

        print(f"  [{domain}] 登录失败")
        return None
    except Exception as e:
        print(f"  [{domain}] 登录异常: {e}")
        return None
    finally:
        conn.close()


def process_site(site, username, password, default_cookie):
    """处理单站点的签到（优先使用账号密码登录，失败则尝试 Cookie）"""
    site_name = site["name"]
    domains = site["domains"]
    print(f"\n==================== 【{site_name}】 ====================")

    # 1. 优先策略: 使用账号密码登录后签到
    if username and password:
        print(f"优先使用账号密码登录签到 ({username})...")
        for domain in domains:
            print(f"--- [尝试域名] {domain} ---")
            cookie = try_login(domain, username, password)
            if cookie:
                res = try_sign_with_cookie(domain, cookie)
                if res and res.get("success"):
                    res["site_name"] = site_name
                    return res

    # 2. 降级策略: 使用配置的 Cookie 直接签到
    if default_cookie:
        print(f"账号密码未成功，尝试使用配置的 Cookie 进行签到...")
        for domain in domains:
            print(f"--- [尝试域名] {domain} ---")
            res = try_sign_with_cookie(domain, default_cookie)
            if res and res.get("success"):
                res["site_name"] = site_name
                return res

    return {"site_name": site_name, "success": False, "message": "所有可用域名均登录或签到失败"}


def push_pushplus(title, content):
    """推送到 PushPlus (推送加 - 微信公众号消息直接发送到微信聊天框)"""
    token = get_env("PUSHPLUS_TOKEN")
    if not token:
        return

    print(f"\n[PushPlus] 正在推送到微信...")
    # 将 \n 替换为 <br/> 适合 HTML/Markdown 渲染
    html_content = content.replace("\n", "<br/>")
    payload = json.dumps({
        "token": token,
        "title": title,
        "content": html_content,
        "template": "html"
    }, ensure_ascii=False)

    body, _, _ = http_request(
        "http://www.pushplus.plus/send",
        method="POST",
        headers={"Content-Type": "application/json"},
        data=payload
    )
    print(f"[PushPlus] 推送结果: {body}")


def push_serverchan(title, content):
    """推送到 Server酱 (微信公众号聊天框卡片通知)"""
    sendkey = get_env("SERVER_CHAN")
    if not sendkey:
        return

    print(f"\n[Server酱] 正在推送到微信...")
    payload = urllib.parse.urlencode({
        "title": title,
        "desp": content
    })

    body, _, _ = http_request(
        f"https://sctapi.ftqq.com/{sendkey}.send",
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=payload
    )
    print(f"[Server酱] 推送结果: {body}")


def push_wechat_app(title, content):
    """推送到 企业微信应用 (通过微信插件，直接在原生微信聊天列表弹出消息)"""
    corpid = get_env("WECHAT_CORPID")
    corpsecret = get_env("WECHAT_CORPSECRET")
    agentid = get_env("WECHAT_AGENTID")

    if not corpid or not corpsecret or not agentid:
        return

    print(f"\n[企业微信] 正在推送到原生微信...")
    try:
        # 1. 获取 access_token
        token_url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={corpid}&corpsecret={corpsecret}"
        resp_body, _, _ = http_request(token_url, method="GET")
        token_res = json.loads(resp_body)
        access_token = token_res.get("access_token")

        if not access_token:
            print(f"[企业微信] 获取 access_token 失败: {resp_body}")
            return

        # 2. 发送应用消息
        send_url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"
        msg_payload = json.dumps({
            "touser": "@all",
            "msgtype": "text",
            "agentid": agentid,
            "text": {
                "content": f"{title}\n\n{content}"
            },
            "safe": 0
        }, ensure_ascii=False)

        body, _, _ = http_request(
            send_url,
            method="POST",
            headers={"Content-Type": "application/json"},
            data=msg_payload
        )
        print(f"[企业微信] 推送结果: {body}")
    except Exception as e:
        print(f"[企业微信] 推送失败: {e}")


def push_wxpusher(title, content):
    """推送到 WxPusher"""
    token = get_env("WXPUSHER_APP_TOKEN", "AT_qRDXs7tySLf9gIV6dTEawsDVqkAJUJa4")
    uid = get_env("WXPUSHER_UID", "UID_dC7k857XvOhGTdetiAHJdGUvDQKV")

    if not token or not uid:
        print("[WxPusher] 未配置 Token 或 UID，跳过推送")
        return

    payload = json.dumps({
        "appToken": token,
        "content": content,
        "summary": title,
        "contentType": 1,
        "uids": [uid],
    }, ensure_ascii=False)

    print(f"\n[WxPusher] 推送标题: {title}")

    body, _, status = http_request(
        "https://wxpusher.zjiecode.com/api/send/message",
        method="POST",
        headers={"Content-Type": "application/json"},
        data=payload,
    )
    print(f"[WxPusher] 推送结果: {body}")


def main_handler(event, context):
    """腾讯云 SCF 入口函数"""
    print("=" * 60)
    print("HiFi 音乐三站 (HiFiNi / HiFiKi / HiFiTi) 联合自动签到脚本")
    print("=" * 60)

    username = get_env("HIFINI_USERNAME", "yfming93")
    password = get_env("HIFINI_PASSWORD", "Yy123456??")
    cookie = get_env("HIFIHI_COOKIE", get_env("COOKIE"))

    results = []
    success_count = 0

    # 遍历三大站点分别完成签到
    for site in SITES:
        res = process_site(site, username, password, cookie)
        results.append(res)
        if res.get("success"):
            success_count += 1

    # 汇总生成推送通知
    print("\n" + "=" * 60)
    total_sites = len(SITES)
    status_str = "全部成功" if success_count == total_sites else f"{success_count}/{total_sites} 成功"
    title = f"HiFi 社区联合签到通知 ({status_str})"

    content_lines = [f"账号: {username}", f"签到结果统计: {success_count}/{total_sites} 成功\n"]

    for r in results:
        s_name = r.get("site_name", "")
        if r.get("success"):
            line = f"✅ [{s_name}]: {r.get('message', '')}"
            if "streak" in r:
                line += f" (连续{r['streak']}天)"
            if "coins" in r:
                line += f" [总金币:{r['coins']}]"
        else:
            line = f"❌ [{s_name}]: {r.get('message', '')}"
        content_lines.append(line)

    content = "\n".join(content_lines)

    print("签到汇总输出:")
    print(content)

    push_wxpusher(title, content)
    push_pushplus(title, content)
    push_serverchan(title, content)
    push_wechat_app(title, content)

    print("\n===== 任务完成 =====")
    return {"code": 0 if success_count > 0 else 1}


# 本地调试入口
if __name__ == "__main__":
    main_handler({}, {})
