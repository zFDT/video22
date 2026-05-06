"""微博采集器 - 通过公开接口获取微博热搜和话题内容"""

import logging
import httpx
from pathlib import Path

from .base_collector import BaseCollector, MaterialItem

logger = logging.getLogger(__name__)

WEIBO_HOT_SEARCH_API = "https://weibo.com/ajax/side/hotSearch"
WEIBO_TOPIC_API = "https://weibo.com/ajax/statuses/topic"
WEIBO_SEARCH_API = "https://m.weibo.cn/api/container/getIndex"


class WeiboCollector(BaseCollector):
    def get_platform_name(self) -> str:
        return "weibo"

    def _get_headers(self) -> dict:
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://m.weibo.cn/",
            "Accept": "application/json, text/plain, */*",
        }

    async def search(self, keywords: list[str], limit: int = 20) -> list[dict]:
        keyword = " ".join(keywords)
        results = []

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # 使用移动端搜索接口（公开，无需登录）
                params = {
                    "containerid": f"100103type=1&q={keyword}",
                    "page_type": "searchall",
                    "page": 1,
                }
                resp = await client.get(WEIBO_SEARCH_API, headers=self._get_headers(), params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    cards = data.get("data", {}).get("cards", [])
                    for card in cards:
                        if card.get("card_type") == 9:
                            mblog = card.get("mblog", {})
                            if mblog:
                                pics = mblog.get("pics", [])
                                pic_urls = [p.get("large", {}).get("url", "") for p in pics] if pics else []
                                results.append({
                                    "id": mblog.get("id", ""),
                                    "text": mblog.get("text", ""),
                                    "source": mblog.get("source", ""),
                                    "reposts_count": mblog.get("reposts_count", 0),
                                    "comments_count": mblog.get("comments_count", 0),
                                    "attitudes_count": mblog.get("attitudes_count", 0),
                                    "pic_urls": pic_urls,
                                    "page_info": mblog.get("page_info", {}),
                                    "user": mblog.get("user", {}).get("screen_name", ""),
                                })
                        elif card.get("card_type") == 11:
                            card_group = card.get("card_group", [])
                            for sub_card in card_group:
                                if sub_card.get("card_type") == 9:
                                    mblog = sub_card.get("mblog", {})
                                    if mblog:
                                        pics = mblog.get("pics", [])
                                        pic_urls = [p.get("large", {}).get("url", "") for p in pics] if pics else []
                                        results.append({
                                            "id": mblog.get("id", ""),
                                            "text": mblog.get("text", ""),
                                            "reposts_count": mblog.get("reposts_count", 0),
                                            "comments_count": mblog.get("comments_count", 0),
                                            "attitudes_count": mblog.get("attitudes_count", 0),
                                            "pic_urls": pic_urls,
                                            "page_info": mblog.get("page_info", {}),
                                            "user": mblog.get("user", {}).get("screen_name", ""),
                                        })
                else:
                    logger.error(f"Weibo search failed: {resp.status_code}")
        except Exception as e:
            logger.error(f"Weibo search error: {e}")

        return results[:limit]

    async def get_hot_search(self) -> list[dict]:
        """获取微博热搜榜"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(WEIBO_HOT_SEARCH_API, headers=self._get_headers())
                if resp.status_code == 200:
                    data = resp.json()
                    realtime = data.get("data", {}).get("realtime", [])
                    return [{"word": item.get("word", ""), "num": item.get("num", 0)} for item in realtime]
        except Exception as e:
            logger.error(f"Weibo hot search error: {e}")
        return []

    def parse_result(self, raw: dict, topic_name: str) -> MaterialItem | None:
        import re
        text = raw.get("text", "")
        if not text:
            return None

        clean_text = re.sub(r"<[^>]+>", "", text)
        mid = raw.get("id", "")
        media_urls = raw.get("pic_urls", [])
        media_type = "image"

        page_info = raw.get("page_info", {})
        if page_info and page_info.get("type") == "video":
            video_url = page_info.get("urls", {}).get("mp4_720p_mp4", "")
            if video_url:
                media_urls = [video_url] + media_urls
                media_type = "video"

        return MaterialItem(
            id="",
            platform="weibo",
            topic=topic_name,
            title=clean_text[:50] if len(clean_text) > 50 else clean_text,
            content=clean_text,
            media_urls=media_urls,
            media_type=media_type,
            metrics={
                "likes": raw.get("attitudes_count", 0),
                "comments": raw.get("comments_count", 0),
                "shares": raw.get("reposts_count", 0),
                "author": raw.get("user", ""),
            },
            source_url=f"https://m.weibo.cn/detail/{mid}" if mid else "",
        )
