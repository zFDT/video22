"""小红书采集器 - 基于 DrissionPage 浏览器自动化"""

import logging
import time
import json
from pathlib import Path

from .base_collector import BaseCollector, MaterialItem

logger = logging.getLogger(__name__)

try:
    from DrissionPage import ChromiumPage, ChromiumOptions
    DRISSION_AVAILABLE = True
except ImportError:
    DRISSION_AVAILABLE = False
    logger.warning("DrissionPage not installed. Run: pip install DrissionPage")


class XhsCollector(BaseCollector):
    def get_platform_name(self) -> str:
        return "xhs"

    def _create_browser(self) -> "ChromiumPage":
        co = ChromiumOptions()
        co.set_argument("--disable-blink-features=AutomationControlled")
        co.set_argument("--no-first-run")
        cookie = self.platform_config.get("cookie", "")
        page = ChromiumPage(co)
        if cookie:
            for item in cookie.split("; "):
                if "=" in item:
                    name, value = item.split("=", 1)
                    page.set.cookies({"name": name.strip(), "value": value.strip(), "domain": ".xiaohongshu.com"})
        return page

    async def search(self, keywords: list[str], limit: int = 20) -> list[dict]:
        if not DRISSION_AVAILABLE:
            logger.error("DrissionPage not available")
            return []

        keyword = " ".join(keywords)
        results = []

        try:
            page = self._create_browser()
            search_url = f"https://www.xiaohongshu.com/search_result?keyword={keyword}&source=web_search_result_note"
            page.get(search_url)
            time.sleep(3)

            # 等待搜索结果加载
            for _ in range(10):
                sections = page.eles("css:.note-item", timeout=2)
                if sections:
                    break
                time.sleep(1)

            note_items = page.eles("css:.note-item")
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

                    likes = self._parse_count(likes_text)

                    results.append({
                        "id": href.split("/")[-1] if href else "",
                        "title": title,
                        "desc": title,
                        "liked_count": likes,
                        "image_list": [cover_url] if cover_url else [],
                        "user": author,
                        "source_url": f"https://www.xiaohongshu.com{href}" if href and not href.startswith("http") else href,
                    })
                except Exception as e:
                    logger.debug(f"Error parsing note item: {e}")
                    continue

            page.quit()
        except Exception as e:
            logger.error(f"XHS DrissionPage search error: {e}")

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

        note_id = raw.get("id", "")
        media_urls = raw.get("image_list", [])
        liked = raw.get("liked_count", 0)
        if isinstance(liked, str):
            liked = self._parse_count(liked)

        return MaterialItem(
            id="",
            platform="xhs",
            topic=topic_name,
            title=raw.get("title", ""),
            content=raw.get("desc", ""),
            media_urls=media_urls,
            media_type="image",
            metrics={"likes": liked, "author": raw.get("user", "")},
            source_url=raw.get("source_url", ""),
        )
