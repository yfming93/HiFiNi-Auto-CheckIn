# -*- coding: utf-8 -*-
# 腾讯云 SCF 云函数 - HiFiNi 磁场自动签到
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

# ========== 配置（从环境变量读取） ==========
DOMAINS = [
    "https://www.hifini.com.cn",
    "https://www.hifihi.com",
    "https://www.hifini.net",
]
SIGN_PATH = "/sg_sign.htm"
LOGIN_PATH = "/user-login.htm"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
SITE_NAME = "HiFiNi 磁场 (hifini.com.cn)"


def get_env(key, default=""):
    """获取环境变量"""
    return os.environ.get(key, default).strip()


def md5(text):
    """计算 MD5"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def http_request(url, method="GET", headers=None, data=None, timeout=15):
    """通用 HTTP 请求，返回 (响应体, 响应头字典)"""
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

    print(f"[签到请求] -> {sign_url}")
    body, _, status = http_request(sign_url, method="POST", headers=headers, data=b"")

    if not body or status == 0:
        print(f"[{domain}] 签到请求失败: {body}")
        return None

    print(f"[{domain}] 签到响应: {body.strip()}")

    try:
        result = json.loads(body)
        msg = result.get("message", "")
        code = str(result.get("code", ""))

        if "签到" in msg or "签过" in msg or "金币" in msg:
            print(f"[✅ 签到成功] {msg}")
            # 签到成功后获取用户详细信息（总金币、连续签到天数）
            user_extra = fetch_user_info(domain, cookie)
            result = {"success": True, "message": msg, "domain": domain}
            result.update(user_extra)
            return result
        elif "请登录" in msg:
            print(f"[{domain}] Cookie 失效，需要重新登录")
            return {"success": False, "message": msg, "need_login": True}
        else:
            print(f"[{domain}] 未知响应: {msg}")
            return {"success": False, "message": msg}
    except json.JSONDecodeError:
        if "请登录" in body or "<html" in body.lower():
            return {"success": False, "message": "返回了网页而非 JSON", "need_login": True}
        return {"success": False, "message": body[:200]}


def fetch_user_info(domain, cookie):
    """签到成功后获取用户主页，解析总金币余额和连续签到天数"""
    extra = {}
    try:
        # 请求签到页面获取连续签到天数
        sign_page_url = domain + "/sg_sign.htm"
        headers = {
            "Cookie": cookie,
            "User-Agent": USER_AGENT,
            "Referer": domain + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        body, _, status = http_request(sign_page_url, method="GET", headers=headers)
        if body and status == 200:
            # 解析连续签到天数: var s3 = '连续签到N天';
            streak_match = re.search(r"连续签到(\d+)天", body)
            if streak_match:
                extra["streak"] = int(streak_match.group(1))
                print(f"[用户信息] 连续签到: {extra['streak']} 天")

            # 解析总金币: <span class="text-muted">金币：</span><em ...>数字</em>
            coin_match = re.search(r'金币[：:]\s*</span>\s*<em[^>]*>(\d+)</em>', body)
            if coin_match:
                extra["coins"] = int(coin_match.group(1))
                print(f"[用户信息] 当前总金币: {extra['coins']}")

            # 解析用户名
            name_match = re.search(r'class="avatar-1"[^>]*>\s*([^<]+)</a>', body)
            if name_match:
                extra["display_name"] = name_match.group(1).strip()
                print(f"[用户信息] 用户昵称: {extra['display_name']}")

    except Exception as e:
        print(f"[用户信息] 获取失败（不影响签到）: {e}")

    return extra


def try_login(domain, username, password):
    """账号密码登录获取 Cookie"""
    login_url = domain + LOGIN_PATH
    md5_pwd = md5(password)

    print(f"[登录请求] -> {login_url} (MD5: {md5_pwd})")

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

    # 使用底层 http.client 来获取 Set-Cookie 头
    import http.client
    from urllib.parse import urlparse

    parsed = urlparse(login_url)
    conn = http.client.HTTPSConnection(parsed.hostname, timeout=15,
                                        context=ssl._create_unverified_context())
    try:
        conn.request("POST", parsed.path, body=form_data, headers=headers)
        resp = conn.getresponse()
        resp.read()

        # 提取 Set-Cookie 中的 bbs_token
        bbs_token = None
        for header_name, header_value in resp.getheaders():
            if header_name.lower() == "set-cookie" and "bbs_token=" in header_value:
                token_part = header_value.split("bbs_token=")[1].split(";")[0].strip()
                if token_part and token_part != "deleted":
                    bbs_token = token_part

        if bbs_token:
            print(f"[{domain}] 登录成功, bbs_token: {bbs_token[:20]}...")
            return f"bbs_token={bbs_token}"

        # 密码首字母大小写自动纠错
        first_char = password[0]
        if first_char.islower():
            alt_password = first_char.upper() + password[1:]
        elif first_char.isupper():
            alt_password = first_char.lower() + password[1:]
        else:
            print(f"[{domain}] 登录失败")
            return None

        alt_md5 = md5(alt_password)
        print(f"[登录重试] 首字母纠错 -> MD5: {alt_md5}")

        form_data2 = urllib.parse.urlencode({"email": username, "password": alt_md5})
        conn2 = http.client.HTTPSConnection(parsed.hostname, timeout=15,
                                             context=ssl._create_unverified_context())
        conn2.request("POST", parsed.path, body=form_data2, headers=headers)
        resp2 = conn2.getresponse()
        resp2.read()

        for header_name, header_value in resp2.getheaders():
            if header_name.lower() == "set-cookie" and "bbs_token=" in header_value:
                token_part = header_value.split("bbs_token=")[1].split(";")[0].strip()
                if token_part and token_part != "deleted":
                    bbs_token = token_part

        conn2.close()

        if bbs_token:
            print(f"[{domain}] 纠错登录成功, bbs_token: {bbs_token[:20]}...")
            return f"bbs_token={bbs_token}"

        print(f"[{domain}] 登录失败")
        return None
    except Exception as e:
        print(f"[{domain}] 登录异常: {e}")
        return None
    finally:
        conn.close()


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

    print(f"[WxPusher] 推送标题: {title}")

    body, _, status = http_request(
        "https://wxpusher.zjiecode.com/api/send/message",
        method="POST",
        headers={"Content-Type": "application/json"},
        data=payload,
    )
    print(f"[WxPusher] 推送结果: {body}")


def main_handler(event, context):
    """腾讯云 SCF 入口函数"""
    print("=" * 50)
    print("HiFiNi 磁场自动签到 - 腾讯云 SCF 云函数")
    print("=" * 50)

    cookie = get_env("HIFIHI_COOKIE", get_env("COOKIE"))
    username = get_env("HIFINI_USERNAME", "yfming93")
    password = get_env("HIFINI_PASSWORD", "Yy123456??")

    sign_result = None

    # 策略1: 使用配置的 Cookie 直接签到
    if cookie:
        print("\n检测到 HIFIHI_COOKIE，优先使用直通签到模式")
        for domain in DOMAINS:
            print(f"\n--- [尝试域名] {domain} ---")
            result = try_sign_with_cookie(domain, cookie)
            if result and result.get("success"):
                sign_result = result
                break
            elif result and result.get("need_login"):
                print("Cookie 已失效，切换到账号密码登录模式")
                cookie = ""
                break

    # 策略2: 账号密码登录后签到
    if not sign_result and username and password:
        print("\n===== 切换到账号密码登录模式 =====")
        for domain in DOMAINS:
            print(f"\n--- [尝试域名] {domain} ---")
            new_cookie = try_login(domain, username, password)
            if new_cookie:
                result = try_sign_with_cookie(domain, new_cookie)
                if result and result.get("success"):
                    sign_result = result
                    break

    # 推送结果
    print("\n" + "=" * 50)
    if sign_result and sign_result.get("success"):
        title = f"{SITE_NAME} 自动签到成功通知"
        # 构建推送内容，包含金币余额和连续签到天数
        display_name = sign_result.get('display_name', username)
        content_lines = [
            f"账号：{display_name}",
            f"签到结果：{sign_result['message']}",
        ]
        if "coins" in sign_result:
            content_lines.append(f"当前总金币：{sign_result['coins']}")
        if "streak" in sign_result:
            content_lines.append(f"连续签到：{sign_result['streak']} 天")
        content_lines.append(f"签到域名：{sign_result.get('domain', '')}")
        content_lines.append(f"签到方式：腾讯云 SCF 云函数")
        content = "\n".join(content_lines)
        print(f"✅ 签到成功 - {sign_result['message']}")
        if "coins" in sign_result:
            print(f"   当前总金币: {sign_result['coins']}")
        if "streak" in sign_result:
            print(f"   连续签到: {sign_result['streak']} 天")
    else:
        title = f"{SITE_NAME} 自动签到失败通知"
        msg = sign_result.get("message", "所有域名均无法访问") if sign_result else "所有域名均无法访问"
        content = (
            f"账号：{username}\n"
            f"签到结果：{msg}\n"
            f"签到方式：腾讯云 SCF 云函数"
        )
        print(f"❌ 签到失败 - {msg}")

    push_wxpusher(title, content)

    print("\n===== 签到任务结束 =====")
    return {"code": 0 if (sign_result and sign_result.get("success")) else 1}


# 本地调试入口
if __name__ == "__main__":
    main_handler({}, {})
