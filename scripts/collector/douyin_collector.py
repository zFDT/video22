"""抖音采集器 - 通过公开接口获取抖音热门视频"""

import logging
import httpx
from pathlib import Path

from .base_collector import BaseCollector, MaterialItem

logger = logging.getLogger(__name__)

DOUYIN_SEARCH_API = "https://www.douyin.com/aweme/v1/web/search/item/"
DOUYIN_HOT_API = "https://www.douyin.com/aweme/v1/web/hot/search/list/"


class DouyinCollector(BaseCollector):
    def get_platform_name(self) -> str:
        return "douyin"

    def _get_headers(self) -> dict:
        cookie = self.platform_config.get("cookie", "")
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Cookie": cookie,
            "Referer": "https://www.douyin.com/",
        }

    async def search(self, keywords: list[str], limit: int = 20) -> list[dict]:
        keyword = " ".join(keywords)
        headers = self._get_headers()

        if not self.platform_config.get("cookie"):
            logger.warning("Douyin cookie not configured, using hot search fallback")
            return await self._hot_search_fallback(keyword, limit)

        params = {
            "keyword": keyword,
            "search_channel": "aweme_general",
            "sort_type": 0,
            "publish_time": 0,
            "count": min(limit, 20),
            "offset": 0,
        }

        results = []
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(DOUYIN_SEARCH_API, headers=headers, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    aweme_list = data.get("data", [])
                    for aweme in aweme_list:
                        info = aweme.get("aweme_info", {})
                        if info:
                            results.append({
                                "aweme_id": info.get("aweme_id", ""),
                                "desc": info.get("desc", ""),
                                "statistics": info.get("statistics", {}),
                                "video_cover": info.get("video", {}).get("cover", {}).get("url_list", [None])[0],
                                "video_play_url": info.get("video", {}).get("play_addr", {}).get("url_list", [None])[0],
                                "author": info.get("author", {}).get("nickname", ""),
                                "duration": info.get("video", {}).get("duration", 0),
                            })
                else:
                    logger.error(f"Douyin search failed: {resp.status_code}")
        except Exception as e:
            logger.error(f"Douyin search error: {e}")

        return results

    async def _hot_search_fallback(self, keyword: str, limit: int) -> list[dict]:
        """Fallback: use Douyin hot search API (public)"""
        logger.info(f"Using hot search fallback for: {keyword}")
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(DOUYIN_HOT_API, headers=self._get_headers())
                if resp.status_code == 200:
                    data = resp.json()
                    word_list = data.get("data", {}).get("word_list", [])
                    matched = [w for w in word_list if keyword.lower() in w.get("word", "").lower()]
                    return [{"desc": w.get("word", ""), "hot_value": w.get("hot_value", 0)} for w in matched[:limit]]
        except Exception as e:
            logger.error(f"Douyin hot search fallback error: {e}")
        return []

    def parse_result(self, raw: dict, topic_name: str) -> MaterialItem | None:
        desc = raw.get("desc", "")
        if not desc:
            return None

        aweme_id = raw.get("aweme_id", "")
        stats = raw.get("statistics", {})
        media_urls = []

        if raw.get("video_play_url"):
            media_urls.append(raw["video_play_url"])
        if raw.get("video_cover"):
            media_urls.append(raw["video_cover"])

        return MaterialItem(
            id="",
            platform="douyin",
            topic=topic_name,
            title=desc[:50] if len(desc) > 50 else desc,
            content=desc,
            media_urls=media_urls,
            media_type="video",
            metrics={
                "likes": stats.get("digg_count", 0),
                "comments": stats.get("comment_count", 0),
                "shares": stats.get("share_count", 0),
                "plays": stats.get("play_count", 0),
                "author": raw.get("author", ""),
            },
            source_url=f"https://www.douyin.com/video/{aweme_id}" if aweme_id else "",
        )
