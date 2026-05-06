"""小红书采集器 - 单浏览器实例复用，支持验证码等待和内容下载"""

import logging
import time
import httpx
from pathlib import Path

from .base_collector import BaseCollector, MaterialItem, BROWSER_DATA_DIR

logger = logging.getLogger(__name__)

try:
    from DrissionPage import ChromiumPage, ChromiumOptions
    DRISSION_AVAILABLE = True
except ImportError:
    DRISSION_AVAILABLE = False
    logger.warning("DrissionPage not installed. Run: pip install DrissionPage")

XHS_BROWSER_DATA = BROWSER_DATA_DIR / "xhs"
XHS_PORT = 9511


class XhsCollector(BaseCollector):
    def __init__(self, config_dir, page: "ChromiumPage | None" = None):
        super().__init__(config_dir)
        self._page = page

    def get_platform_name(self) -> str:
        return "xhs"

    def set_page(self, page: "ChromiumPage"):
        self._page = page

    @staticmethod
    def create_browser() -> "ChromiumPage":
        """创建独立的浏览器实例（固定端口 9511，与抖音隔离）"""
        co = ChromiumOptions()
        co.set_user_data_path(str(XHS_BROWSER_DATA))
        co.set_local_port(XHS_PORT)
        co.set_argument("--disable-blink-features=AutomationControlled")
        co.set_argument("--no-first-run")
        co.set_argument("--no-default-browser-check")
        return ChromiumPage(co)

    @staticmethod
    def wait_for_login(page: "ChromiumPage") -> bool:
        """打开小红书首页，检测登录状态"""
        page.get("https://www.xiaohongshu.com")
        time.sleep(3)
        avatar = page.ele("css:.user-avatar", timeout=3) or page.ele("css:[class*='avatar']", timeout=2)
        if avatar:
            logger.info("XHS: 已登录（复用上次 session）")
            return True
        logger.info("XHS: 需要登录，请在浏览器中完成登录")
        input(">>> 小红书登录完成后，按回车继续...")
        return True

    def _wait_for_page_ready(self):
        """等待页面加载完成，如果遇到验证码则暂停等待用户处理"""
        time.sleep(2)
        # 检测常见的验证码/风控页面
        captcha_signs = [
            "css:.captcha-container",
            "css:#captcha",
            "css:[class*='verify']",
            "css:[class*='captcha']",
        ]
        for selector in captcha_signs:
            el = self._page.ele(selector, timeout=1)
            if el:
                logger.warning("检测到验证码，请在浏览器中完成验证")
                input(">>> 验证完成后按回车继续...")
                time.sleep(2)
                return
        # 检测是否被重定向到登录页
        if "login" in self._page.url:
            logger.warning("被重定向到登录页，请重新登录")
            input(">>> 登录完成后按回车继续...")
            time.sleep(2)

    async def search(self, keywords: list[str], limit: int = 20) -> list[dict]:
        if not DRISSION_AVAILABLE or not self._page:
            logger.error("Browser not available")
            return []

        keyword = " ".join(keywords)
        results = []

        try:
            search_url = f"https://www.xiaohongshu.com/search_result?keyword={keyword}&source=web_search_result_note"
            self._page.get(search_url)
            self._wait_for_page_ready()

            # 等待搜索结果加载
            for _ in range(15):
                sections = self._page.eles("css:.note-item", timeout=2)
                if sections:
                    break
                time.sleep(1)

            note_items = self._page.eles("css:.note-item")
            logger.info(f"Found {len(note_items)} note items for '{keyword}'")

            for item in note_items[:limit]:
                try:
                    title_el = item.ele("css:.title", timeout=1)
                    title = title_el.text if title_el else ""

                    author_el = item.ele("css:.author-wrapper .name", timeout=1)
                    author = author_el.text if author_el else ""

                    likes_el = item.ele("css:.like-wrapper .count", timeout=1)
                    likes_text = likes_el.text if likes_el else "0"

                    link_el = item.ele("css:a", timeout=1)
                    href = link_el.attr("href") if link_el else ""

                    cover_el = item.ele("css:img", timeout=1)
                    cover_url = cover_el.attr("src") if cover_el else ""

                    note_url = ""
                    if href:
                        if href.startswith("http"):
                            note_url = href
                        elif href.startswith("/"):
                            note_url = f"https://www.xiaohongshu.com{href}"
                        else:
                            note_url = f"https://www.xiaohongshu.com/{href}"

                    results.append({
                        "id": href.split("/")[-1] if href else "",
                        "title": title,
                        "desc": title,
                        "liked_count": self._parse_count(likes_text),
                        "image_list": [cover_url] if cover_url else [],
                        "user": author,
                        "source_url": note_url,
                    })
                except Exception as e:
                    logger.debug(f"Error parsing note item: {e}")
                    continue
        except Exception as e:
            logger.error(f"XHS search error: {e}")

        return results

    def _parse_count(self, text: str) -> int:
        text = text.strip()
        if not text:
            return 0
        try:
            if "万" in text:
                return int(float(text.replace("万", "")) * 10000)
            return int(text.replace("+", ""))
        except (ValueError, TypeError):
            return 0

    def parse_result(self, raw: dict, topic_name: str) -> MaterialItem | None:
        if not raw.get("title") and not raw.get("desc"):
            return None

        liked = raw.get("liked_count", 0)
        if isinstance(liked, str):
            liked = self._parse_count(liked)

        return MaterialItem(
            id="",
            platform="xhs",
            topic=topic_name,
            title=raw.get("title", ""),
            content=raw.get("desc", ""),
            media_urls=raw.get("image_list", []),
            media_type="image",
            metrics={"likes": liked, "author": raw.get("user", "")},
            source_url=raw.get("source_url", ""),
        )
