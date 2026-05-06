"""抖音采集器 - 基于 DrissionPage 浏览器自动化"""

import logging
import time
import re
from pathlib import Path

from .base_collector import BaseCollector, MaterialItem

logger = logging.getLogger(__name__)

try:
    from DrissionPage import ChromiumPage, ChromiumOptions
    DRISSION_AVAILABLE = True
except ImportError:
    DRISSION_AVAILABLE = False
    logger.warning("DrissionPage not installed. Run: pip install DrissionPage")


class DouyinCollector(BaseCollector):
    def get_platform_name(self) -> str:
        return "douyin"

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
                    page.set.cookies({"name": name.strip(), "value": value.strip(), "domain": ".douyin.com"})
        return page

    async def search(self, keywords: list[str], limit: int = 20) -> list[dict]:
        if not DRISSION_AVAILABLE:
            logger.error("DrissionPage not available")
            return []

        keyword = " ".join(keywords)
        results = []

        try:
            page = self._create_browser()
            search_url = f"https://www.douyin.com/search/{keyword}?type=video"
            page.get(search_url)
            time.sleep(4)

            # 滚动加载更多
            scroll_count = min(limit // 5 + 1, 5)
            for i in range(scroll_count):
                page.scroll.to_bottom()
                time.sleep(2)

            # 解析视频卡片
            video_cards = page.eles("css:[data-e2e='scroll-list'] > div", timeout=5)
            if not video_cards:
                video_cards = page.eles("css:.search-result-card", timeout=3)

            logger.info(f"Found {len(video_cards)} video cards for '{keyword}'")

            for card in video_cards[:limit]:
                try:
                    title_el = card.ele("css:a[title]", timeout=1) or card.ele("css:.title", timeout=1)
                    title = title_el.attr("title") or title_el.text if title_el else ""

                    author_el = card.ele("css:.author-card-user-name", timeout=1) or card.ele("css:[data-e2e='search-card-user-name']", timeout=1)
                    author = author_el.text if author_el else ""

                    likes_el = card.ele("css:[data-e2e='search-like-count']", timeout=1) or card.ele("css:.like-count", timeout=1)
                    likes_text = likes_el.text if likes_el else "0"

                    link_el = card.ele("css:a[href*='/video/']", timeout=1)
                    href = link_el.attr("href") if link_el else ""

                    cover_el = card.ele("css:img[src*='image']", timeout=1)
                    cover_url = cover_el.attr("src") if cover_el else ""

                    results.append({
                        "aweme_id": self._extract_video_id(href),
                        "desc": title,
                        "statistics": {"digg_count": self._parse_count(likes_text)},
                        "video_cover": cover_url,
                        "author": author,
                        "source_url": href if href.startswith("http") else f"https://www.douyin.com{href}" if href else "",
                    })
                except Exception as e:
                    logger.debug(f"Error parsing video card: {e}")
                    continue

            page.quit()
        except Exception as e:
            logger.error(f"Douyin DrissionPage search error: {e}")

        return results

    def _extract_video_id(self, url: str) -> str:
        match = re.search(r"/video/(\d+)", url)
        return match.group(1) if match else ""

    def _parse_count(self, text: str) -> int:
        text = text.strip()
        if not text:
            return 0
        try:
            if "万" in text:
                return int(float(text.replace("万", "")) * 10000)
            if "w" in text.lower():
                return int(float(text.lower().replace("w", "")) * 10000)
            return int(text.replace("+", "").replace(",", ""))
        except (ValueError, TypeError):
            return 0

    def parse_result(self, raw: dict, topic_name: str) -> MaterialItem | None:
        desc = raw.get("desc", "")
        if not desc:
            return None

        aweme_id = raw.get("aweme_id", "")
        stats = raw.get("statistics", {})

        return MaterialItem(
            id="",
            platform="douyin",
            topic=topic_name,
            title=desc[:50] if len(desc) > 50 else desc,
            content=desc,
            media_urls=[raw.get("video_cover", "")] if raw.get("video_cover") else [],
            media_type="video",
            metrics={
                "likes": stats.get("digg_count", 0),
                "author": raw.get("author", ""),
            },
            source_url=raw.get("source_url", ""),
        )
