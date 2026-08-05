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
PASSWORD = os.environ.get("HIFINI_PASSWORD") or os.environ.get("PASSWORD") or "yy123456??"
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

    sign_status = "签到失败"
    coins_info = "未知"
    streak_info = "未知"
    success_domain = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        for domain in DOMAINS:
            print(f"\n[尝试站点] -> {domain}")
            try:
                # 1. 打开登录页面
                login_url = f"{domain}/user-login.htm"
                print(f"正在访问登录页: {login_url}")
                page.goto(login_url, timeout=25000, wait_until="domcontentloaded")
                time.sleep(2)

                print(f"页面标题: {page.title()}")

                # 2. 填充用户名和密码
                if page.locator("#email").count() > 0:
                    page.fill("#email", USERNAME)
                elif page.locator("input[name='email']").count() > 0:
                    page.fill("input[name='email']", USERNAME)
                else:
                    page.fill("input[type='text']", USERNAME)

                if page.locator("#password").count() > 0:
                    page.fill("#password", PASSWORD)
                else:
                    page.fill("input[name='password']", PASSWORD)

                # 3. 点击登录提交按钮
                submit_locator = page.locator("#submit")
                if submit_locator.count() > 0:
                    submit_locator.click()
                else:
                    page.click("button[type='submit']")

                print("提交登录表单中...")
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
    title = f"HiFiNi 自动签到提醒 - {sign_status}"
    msg_lines = [
        f"尊敬的用户，您的 HiFiNi 自动签到结果如下：",
        f"",
        f"• 登录账号：{USERNAME}",
        f"• 成功站点：{success_domain if success_domain else '无可用站点'}",
        f"• 签到状态：{sign_status}",
        f"• 当前金币：{coins_info}",
        f"• 连续签到：{streak_info} 天" if streak_info != '未知' else f"• 连续签到：信息未抓取到"
    ]
    msg = "\n".join(msg_lines)

    print("\n=== 开始推送 WxPusher 通知 ===")
    push_wxpusher(title, msg)

if __name__ == "__main__":
    run_checkin()
