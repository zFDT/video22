"""小红书采集器 - 通过 xiaohongshu-mcp 工具进行内容采集"""

import logging
import subprocess
import httpx
from pathlib import Path

from .base_collector import BaseCollector, MaterialItem

logger = logging.getLogger(__name__)

XHS_MCP_EXE = Path(r"D:\go\xiaohongshu-mcp-windows-amd64\xiaohongshu-mcp-windows-amd64.exe")
XHS_MCP_DIR = XHS_MCP_EXE.parent


class XhsCollector(BaseCollector):
    def get_platform_name(self) -> str:
        return "xhs"

    def _get_headers(self) -> dict:
        cookie = self.platform_config.get("cookie", "")
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Cookie": cookie,
            "Origin": "https://www.xiaohongshu.com",
            "Referer": "https://www.xiaohongshu.com/",
            "Content-Type": "application/json",
        }

    async def search(self, keywords: list[str], limit: int = 20) -> list[dict]:
        keyword = " ".join(keywords)

        # 优先使用 xiaohongshu-mcp 的 HTTP API（如果在运行）
        results = await self._search_via_mcp_api(keyword, limit)
        if results:
            return results

        # Fallback: 直接用 httpx（需要签名，可能返回空）
        return await self._search_direct(keyword, limit)

    async def _search_via_mcp_api(self, keyword: str, limit: int) -> list[dict]:
        """通过 xiaohongshu-mcp HTTP API 搜索（端口 18060）"""
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    "http://127.0.0.1:18060/api/v1/feeds/search",
                    json={"keyword": keyword, "limit": limit},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("success"):
                        notes = data.get("data", [])
                        if isinstance(notes, list):
                            logger.info(f"MCP API returned {len(notes)} notes for '{keyword}'")
                            return notes
                        elif isinstance(notes, dict):
                            items = notes.get("items", notes.get("notes", []))
                            logger.info(f"MCP API returned {len(items)} items for '{keyword}'")
                            return items
                    else:
                        logger.debug(f"MCP API error: {data.get('error', 'unknown')}")
                else:
                    logger.debug(f"MCP API returned {resp.status_code}")
        except httpx.ReadTimeout:
            logger.warning(f"MCP API timeout for '{keyword}' (120s)")
        except (httpx.ConnectError, httpx.ConnectTimeout):
            logger.debug("xiaohongshu-mcp API not available, using direct method")
        except Exception as e:
            logger.debug(f"MCP API error: {e}")
        return []

    async def _search_direct(self, keyword: str, limit: int) -> list[dict]:
        """直接调用小红书 API（可能因缺少签名返回空）"""
        headers = self._get_headers()
        if not self.platform_config.get("cookie"):
            logger.warning("XHS cookie not configured")
            return []

        payload = {
            "keyword": keyword,
            "page": 1,
            "page_size": min(limit, 20),
            "search_id": "",
            "sort": "general",
            "note_type": 0,
        }

        results = []
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://edith.xiaohongshu.com/api/sns/web/v1/search/notes",
                    headers=headers, json=payload,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("data", {}).get("items", [])
                    for item in items:
                        note_card = item.get("note_card", {})
                        if note_card:
                            results.append({
                                "id": item.get("id", ""),
                                "title": note_card.get("display_title", ""),
                                "desc": note_card.get("desc", ""),
                                "type": note_card.get("type", "normal"),
                                "liked_count": note_card.get("interact_info", {}).get("liked_count", "0"),
                                "image_list": [img.get("url_default", "") for img in note_card.get("image_list", [])],
                                "video_url": note_card.get("video", {}).get("consumer", {}).get("origin_video_key", ""),
                                "user": note_card.get("user", {}).get("nickname", ""),
                            })
                else:
                    logger.warning(f"XHS direct search returned {resp.status_code}")
        except Exception as e:
            logger.error(f"XHS search error: {e}")

        return results

    def parse_result(self, raw: dict, topic_name: str) -> MaterialItem | None:
        if not raw.get("title") and not raw.get("desc"):
            return None

        note_id = raw.get("id", "")
        media_urls = raw.get("image_list", [])
        media_type = "video" if raw.get("video_url") else "image"

        if media_type == "video" and raw.get("video_url"):
            media_urls = [raw["video_url"]] + media_urls

        liked = raw.get("liked_count", "0")
        if isinstance(liked, str):
            liked = int(liked.replace("万", "0000").replace("+", "")) if liked else 0

        return MaterialItem(
            id="",
            platform="xhs",
            topic=topic_name,
            title=raw.get("title", ""),
            content=raw.get("desc", ""),
            media_urls=media_urls,
            media_type=media_type,
            metrics={"likes": liked, "author": raw.get("user", "")},
            source_url=f"https://www.xiaohongshu.com/explore/{note_id}" if note_id else "",
        )
