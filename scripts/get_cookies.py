"""
Cookie 获取辅助工具
用法: python get_cookies.py --platform xhs
      python get_cookies.py --platform douyin

会打开浏览器让你登录，登录成功后自动提取 Cookie 并写入 config/platforms.json
"""

import argparse
import json
import time
import sys
from pathlib import Path

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    HAS_SELENIUM = True
except ImportError:
    HAS_SELENIUM = False


PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "platforms.json"

PLATFORM_URLS = {
    "xhs": "https://www.xiaohongshu.com",
    "douyin": "https://www.douyin.com",
}


def get_cookie_manual(platform: str):
    """手动方式：引导用户从浏览器 DevTools 复制 Cookie"""
    url = PLATFORM_URLS[platform]
    print(f"\n{'='*60}")
    print(f"  手动获取 {platform.upper()} Cookie")
    print(f"{'='*60}")
    print(f"""
步骤：
  1. 打开浏览器，访问 {url}
  2. 登录你的账号
  3. 按 F12 打开开发者工具
  4. 切换到 "Network"（网络）标签
  5. 刷新页面
  6. 点击任意一个请求
  7. 在 "Headers"（标头）中找到 "Cookie" 字段
  8. 复制整个 Cookie 值粘贴到下方
""")
    cookie = input("请粘贴 Cookie 值 (直接回车跳过): ").strip()
    return cookie


def get_cookie_selenium(platform: str):
    """自动方式：使用 Selenium 打开浏览器，等待用户登录后提取 Cookie"""
    url = PLATFORM_URLS[platform]
    print(f"\n正在打开 {platform.upper()} 登录页面...")
    print("请在浏览器中完成登录，登录成功后按回车键继续...\n")

    options = Options()
    options.add_argument("--start-maximized")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=options)
    driver.get(url)

    input(">>> 登录完成后，按回车键提取 Cookie...")

    cookies = driver.get_cookies()
    cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])

    driver.quit()
    print(f"成功提取 {len(cookies)} 个 Cookie 项")
    return cookie_str


def save_cookie(platform: str, cookie: str):
    """保存 Cookie 到配置文件"""
    if not cookie:
        print("未提供 Cookie，跳过保存")
        return

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    config[platform]["cookie"] = cookie
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nCookie 已保存到 {CONFIG_PATH}")
    print(f"Cookie 长度: {len(cookie)} 字符")


def validate_cookie(platform: str, cookie: str) -> bool:
    """简单验证 Cookie 格式"""
    if not cookie:
        return False
    if "=" not in cookie:
        print("警告: Cookie 格式可能不正确（缺少 = 号）")
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description="Cookie 获取辅助工具")
    parser.add_argument("--platform", choices=["xhs", "douyin"], required=True)
    parser.add_argument("--method", choices=["manual", "auto"], default="auto",
                        help="manual=手动复制, auto=Selenium自动提取")
    args = parser.parse_args()

    if args.method == "auto" and HAS_SELENIUM:
        cookie = get_cookie_selenium(args.platform)
    else:
        if args.method == "auto" and not HAS_SELENIUM:
            print("未安装 selenium，切换到手动模式")
            print("安装命令: pip install selenium")
        cookie = get_cookie_manual(args.platform)

    if validate_cookie(args.platform, cookie):
        save_cookie(args.platform, cookie)
        print("\n完成! 现在可以运行采集脚本了。")
    else:
        print("\n未获取到有效 Cookie。")


if __name__ == "__main__":
    main()
