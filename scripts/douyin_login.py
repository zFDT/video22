"""
抖音 Cookie 获取工具
用法: python douyin_login.py

会打开 Chrome 浏览器到抖音登录页，你扫码/手机号登录后，
脚本自动提取 Cookie 保存为 cookies.json（与 xiaohongshu-mcp 格式一致）
"""

import json
import time
import sys
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

OUTPUT_DIR = Path(__file__).parent.parent / "config"
COOKIES_PATH = OUTPUT_DIR / "douyin_cookies.json"


def main():
    print("=" * 50)
    print("  抖音 Cookie 获取工具")
    print("=" * 50)
    print("\n即将打开 Chrome 浏览器...")
    print("请在浏览器中完成抖音登录（扫码或手机号）\n")

    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=options)

    # 反检测
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })

    driver.get("https://www.douyin.com")
    print("浏览器已打开，请登录抖音...")
    print("（登录成功后页面会显示你的头像/昵称）\n")

    # 等待用户登录 - 检测登录状态
    print("等待登录中... (最长等待 5 分钟)")
    logged_in = False
    for i in range(300):
        cookies = driver.get_cookies()
        cookie_names = [c["name"] for c in cookies]
        # 抖音登录后会有 passport_csrf_token 和 sid_guard
        if "passport_csrf_token" in cookie_names or "sid_guard" in cookie_names or "sessionid" in cookie_names:
            logged_in = True
            break
        time.sleep(1)
        if i % 10 == 0 and i > 0:
            print(f"  已等待 {i} 秒...")

    if not logged_in:
        print("\n未检测到登录状态，尝试手动确认...")
        input("如果你已经登录成功，请按回车键继续: ")

    # 刷新一下确保 Cookie 完整
    time.sleep(2)
    driver.get("https://www.douyin.com")
    time.sleep(3)

    # 提取 Cookie
    cookies = driver.get_cookies()
    driver.quit()

    if not cookies:
        print("未获取到任何 Cookie，请重试。")
        sys.exit(1)

    # 保存为与 xiaohongshu-mcp 相同的格式
    cookie_data = []
    for c in cookies:
        cookie_data.append({
            "name": c["name"],
            "value": c["value"],
            "domain": c.get("domain", ""),
            "path": c.get("path", "/"),
            "expires": c.get("expiry", -1),
            "size": len(c["name"]) + len(c["value"]),
            "httpOnly": c.get("httpOnly", False),
            "secure": c.get("secure", False),
            "session": c.get("expiry") is None,
            "priority": "Medium",
            "sameParty": False,
            "sourceScheme": "Secure",
            "sourcePort": 443,
        })

    with open(COOKIES_PATH, "w", encoding="utf-8") as f:
        json.dump(cookie_data, f, ensure_ascii=False, indent=2)

    print(f"\n成功获取 {len(cookies)} 个 Cookie!")
    print(f"已保存到: {COOKIES_PATH}")

    # 更新 platforms.json
    platforms_path = OUTPUT_DIR / "platforms.json"
    config = json.loads(platforms_path.read_text(encoding="utf-8"))
    config["douyin"]["cookies_json"] = str(COOKIES_PATH).replace("\\", "/")
    platforms_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已更新 platforms.json 中的 douyin.cookies_json 路径")
    print("\n完成! 现在可以运行采集脚本了。")


if __name__ == "__main__":
    main()
