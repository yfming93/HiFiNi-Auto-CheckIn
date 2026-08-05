/// @Author: 袁凤鸣
/// @Date: 2026-08-05
/// @LastEditors: 袁凤鸣
/// @LastEditTime: 2026-08-05 15:52:00
/// @FilePath: scripts/checkin.py
/// @Description: 基于 Playwright 的全自动无头浏览器 HiFiNi 模拟登录签到与 WxPusher 推送脚本

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
                page.goto(login_url, timeout=20000, wait_until="domcontentloaded")
                time.sleep(2)

                # 2. 填充用户名和密码
                if page.locator("input[name='email']").is_visible():
                    page.fill("input[name='email']", USERNAME)
                elif page.locator("input[name='username']").is_visible():
                    page.fill("input[name='username']", USERNAME)
                else:
                    page.fill("input[type='text']", USERNAME)

                page.fill("input[name='password']", PASSWORD)
                
                # 3. 点击登录按钮
                submit_btn = page.locator("button[type='submit']")
                if submit_btn.count() > 0:
                    submit_btn.click()
                else:
                    page.locator("input[type='submit']").click()

                time.sleep(3)

                # 4. 跳转至签到页面 /sg_sign.htm
                sign_url = f"{domain}/sg_sign.htm"
                page.goto(sign_url, timeout=20000, wait_until="domcontentloaded")
                time.sleep(2)

                # 检查签到按钮或签到状态
                sign_btn = page.locator("#sign")
                if sign_btn.is_visible():
                    sign_btn.click()
                    time.sleep(2)
                    sign_status = "签到成功"
                    print(f"[{domain}] 点击签到按钮成功！")
                else:
                    sign_status = "今日已签到或已成功登录"
                    print(f"[{domain}] 页面未找到独立签到按钮，可能今日已完成签到。")

                # 5. 提取个人中心页面获取金币与连续天数
                my_url = f"{domain}/my.htm"
                page.goto(my_url, timeout=15000, wait_until="domcontentloaded")
                time.sleep(2)

                content = page.content()
                
                # 匹配金币
                coin_match = re.search(r'金币：</span><em[^>]*>(\d+)</em>', content)
                if coin_match:
                    coins_info = coin_match.group(1)

                # 匹配连续签到天数
                streak_match = re.search(r'连续签到(\d+)天', content)
                if streak_match:
                    streak_info = streak_match.group(1)

                success_domain = domain
                print(f"[{domain}] 数据抓取成功: 金币={coins_info}, 连续签到={streak_info}天")
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
