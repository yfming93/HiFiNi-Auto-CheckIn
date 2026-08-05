# @Author: 袁凤鸣
# @Date: 2026-08-05
# @LastEditors: 袁凤鸣
# @LastEditTime: 2026-08-05 15:56:00
# @FilePath: scripts/checkin.py
# @Description: 基于 Playwright 的全自动无头浏览器 HiFiNi 模拟登录签到与 WxPusher 推送脚本

import os
import re
import sys
import time
import requests
from playwright.sync_api import sync_playwright

USERNAME = os.environ.get("HIFINI_USERNAME") or os.environ.get("USERNAME") or "yfming93"
PASSWORD = os.environ.get("HIFINI_PASSWORD") or os.environ.get("PASSWORD") or "Yy123456??"
WXPUSHER_APP_TOKEN = os.environ.get("WXPUSHER_APP_TOKEN") or "AT_qRDXs7tySLf9gIV6dTEawsDVqkAJUJa4"
WXPUSHER_UID = os.environ.get("WXPUSHER_UID") or "UID_dC7k857XvOhGTdetiAHJdGUvDQKV"

DOMAINS = [
    "https://www.hifini.com",
    "https://www.hifihi.com",
    "https://www.hifini.net",
    "https://www.hifini.com.cn"
]

def push_wxpusher(title: str, content: str):
    url = "https://wxpusher.zjiecode.com/api/send/message"
    payload = {
        "appToken": WXPUSHER_APP_TOKEN,
        "content": content,
        "summary": title,
        "contentType": 1,
        "uids": [WXPUSHER_UID]
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        print(f"[WxPusher] 推送响应: {resp.text}")
    except Exception as e:
        print(f"[WxPusher] 推送异常: {e}")

import hashlib

def get_md5(text: str) -> str:
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def run_checkin():
    print(f"=== 开始全自动无头浏览器签到 (账号: {USERNAME}) ===")
    
    delay_env = os.environ.get("ENABLE_RANDOM_DELAY", "false").lower()
    if delay_env in ["true", "1"]:
        import random
        delay_mins = random.randint(1, 15)
        print(f"定时打卡模式：已开启凌晨随机延时，休眠 {delay_mins} 分钟后开始...")
        time.sleep(delay_mins * 60)
    else:
        print("手动触发模式：跳过随机休眠，立即开始全自动无头浏览器签到！")

    password_md5 = get_md5(PASSWORD)
    print(f"入参计算完成 -> email: {USERNAME}, password MD5: {password_md5}")

    sign_status = "签到失败"
    coins_info = "未知"
    streak_info = "未知"
    success_domain = None

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--ignore-certificate-errors",
                "--disable-web-security"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            extra_http_headers={
                "X-Requested-With": "XMLHttpRequest",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
            }
        )
        # 移除 webdriver 标记
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        for domain in DOMAINS:
            print(f"\n[尝试站点] -> {domain}")
            try:
                # 1. 打开登录页面
                login_url = f"{domain}/user-login.htm"
                print(f"正在访问登录页: {login_url}")
                page.goto(login_url, timeout=8000, wait_until="commit")
                time.sleep(2)

                print(f"页面标题: {page.title()}")

                # 2. 优先调用页面原生 $.xpost 执行抓包同款登录 (email + password_md5)
                print(f"尝试使用抓包同款参数 (email={USERNAME}&password={password_md5}) 执行登录...")
                login_result = page.evaluate(f"""
                    async () => {{
                        return new Promise((resolve) => {{
                            if (typeof $ !== 'undefined' && $.xpost) {{
                                $.xpost('user-login.htm', {{email: '{USERNAME}', password: '{password_md5}'}}, function(code, message) {{
                                    resolve({{code: code, message: message}});
                                }});
                            }} else {{
                                resolve({{code: -1, message: 'jQuery or $.xpost not found'}});
                            }}
                        }});
                    }}
                """)
                print(f"登录接口响应结果: {login_result}")

                # 若因密码大小写失败，自动尝试首字母变写
                if login_result.get("code") != 0 and login_result.get("code") != "0":
                    alt_pass = (PASSWORD[0].upper() if PASSWORD[0].islower() else PASSWORD[0].lower()) + PASSWORD[1:]
                    alt_md5 = get_md5(alt_pass)
                    print(f"尝试使用密码首字母纠错值 (password={alt_pass}, MD5={alt_md5}) 再次登录...")
                    login_result = page.evaluate(f"""
                        async () => {{
                            return new Promise((resolve) => {{
                                if (typeof $ !== 'undefined' && $.xpost) {{
                                    $.xpost('user-login.htm', {{email: '{USERNAME}', password: '{alt_md5}'}}, function(code, message) {{
                                        resolve({{code: code, message: message}});
                                    }});
                                }} else {{
                                    resolve({{code: -1, message: 'jQuery or $.xpost not found'}});
                                }}
                            }});
                        }}
                    """)
                    print(f"纠错登录接口响应结果: {login_result}")

                time.sleep(3)

                # 如果 $.xpost 没找到，则回退到常规表单输入
                if login_result.get("code") == -1:
                    print("回退到无头浏览器 DOM 表单填充登录...")
                    if page.locator("#email").count() > 0:
                        page.fill("#email", USERNAME)
                    else:
                        page.fill("input[name='email']", USERNAME)

                    if page.locator("#password").count() > 0:
                        page.fill("#password", PASSWORD)
                    else:
                        page.fill("input[name='password']", PASSWORD)

                    submit_locator = page.locator("#submit")
                    if submit_locator.count() > 0:
                        submit_locator.click()
                    else:
                        page.click("button[type='submit']")
                    time.sleep(4)

                # 4. 在登录后的页面上下文直接调用原生 $.xpost('sg_sign.htm')
                print("尝试调用页面原生 $.xpost('sg_sign.htm') 执行签到...")
                sign_result = page.evaluate("""
                    async () => {
                        return new Promise((resolve) => {
                            if (typeof $ !== 'undefined' && $.xpost) {
                                $.xpost('sg_sign.htm', function(code, message) {
                                    resolve({code: code, message: message});
                                });
                            } else {
                                resolve({code: -1, message: 'jQuery or $.xpost not found'});
                            }
                        });
                    }
                """)
                print(f"签到接口返回结果: {sign_result}")

                code = str(sign_result.get("code", "-1"))
                msg = str(sign_result.get("message", ""))

                if code == "0" or "成功" in msg or "签过" in msg or "完成" in msg:
                    sign_status = f"签到成功 ({msg})" if msg else "签到成功"
                elif code == "-1":
                    # 尝试直接访问 /sg_sign.htm 或点击签到按钮
                    page.goto(f"{domain}/sg_sign.htm", timeout=15000, wait_until="domcontentloaded")
                    time.sleep(2)
                    sign_btn = page.locator("#sign")
                    if sign_btn.is_visible():
                        sign_btn.click()
                        time.sleep(2)
                        sign_status = "点击签到按钮成功"
                    else:
                        sign_status = "页面自动完成签到"
                else:
                    sign_status = f"结果: {msg}"

                # 5. 提取个人中心页面获取金币与连续天数
                my_url = f"{domain}/my.htm"
                page.goto(my_url, timeout=15000, wait_until="domcontentloaded")
                time.sleep(2)

                content = page.content()
                
                # 匹配金币数量
                coin_match = re.search(r'金币[：:]\s*<em[^>]*>(\d+)</em>', content) or re.search(r'金币[：:]\s*(\d+)', content)
                if coin_match:
                    coins_info = coin_match.group(1)

                # 匹配连续签到天数
                streak_match = re.search(r'连续签到\s*<em[^>]*>(\d+)</em>\s*天', content) or re.search(r'连续签到\s*(\d+)\s*天', content)
                if streak_match:
                    streak_info = streak_match.group(1)

                success_domain = domain
                print(f"[{domain}] 完整打卡逻辑执行成功: 签到状态={sign_status}, 金币={coins_info}, 连续签到={streak_info}天")
                break

            except Exception as e:
                print(f"[{domain}] 尝试失败: {e}")
                continue

        browser.close()

    # 发送 WxPusher 推送通知
    title = f"HiFiNi 磁场 (hifini.com.cn) 自动签到通知" if ("成功" in sign_status or "签过" in sign_status) else f"HiFiNi 磁场 (hifini.com.cn) 自动签到失败"
    msg_lines = [
        f"账号：{USERNAME}",
        f"",
        f"• 站点域名：{success_domain if success_domain else 'https://www.hifini.com.cn'}",
        f"• 签到状态：{sign_status}",
        f"• 当前金币：{coins_info}",
        f"• 连续签到：{streak_info} 天" if streak_info != '未知' else f"• 连续签到：信息未抓取到"
    ]
    msg = "\n".join(msg_lines)

    print("\n=== 开始推送 WxPusher 通知 ===")
    push_wxpusher(title, msg)

if __name__ == "__main__":
    run_checkin()
