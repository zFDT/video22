"""采集器基类 - 定义统一的采集接口和数据格式"""

import json
import hashlib
import time
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, asdict, field

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
BROWSER_DATA_DIR = PROJECT_ROOT / "browser_data"


@dataclass
class MaterialItem:
    id: str
    platform: str
    topic: str
    title: str
    content: str
    media_urls: list[str] = field(default_factory=list)
    media_type: str = "image"
    metrics: dict = field(default_factory=dict)
    collected_at: str = ""
    source_url: str = ""
    raw_data: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.collected_at:
            self.collected_at = datetime.now(timezone.utc).isoformat()
        if not self.id:
            self.id = hashlib.md5(f"{self.platform}:{self.source_url}".encode()).hexdigest()

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("raw_data", None)
        return d


class BaseCollector(ABC):
    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.platforms_config = self._load_json("platforms.json")
        self.topics_config = self._load_json("topics.json")
        self.platform_name = self.get_platform_name()
        self.platform_config = self.platforms_config.get(self.platform_name, {})
        self._load_cookies_from_json()

    def _load_json(self, filename: str) -> dict:
        filepath = self.config_dir / filename
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_cookies_from_json(self):
        """从 cookies.json 文件加载 Cookie（兼容 xiaohongshu-mcp 格式）"""
        cookies_json_path = self.platform_config.get("cookies_json", "")
        if cookies_json_path and Path(cookies_json_path).exists():
            with open(cookies_json_path, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
            self.platform_config["cookie"] = cookie_str
            logger.info(f"Loaded {len(cookies)} cookies from {cookies_json_path}")

    def refresh_cookies(self) -> bool:
        """调用登录工具刷新 Cookie（如 xiaohongshu-login-windows-amd64.exe）"""
        import subprocess
        login_tool = self.platform_config.get("login_tool", "")
        if not login_tool or not Path(login_tool).exists():
            logger.warning(f"No login tool configured for {self.platform_name}")
            return False

        logger.info(f"Launching login tool: {login_tool}")
        logger.info("请在弹出的浏览器中完成登录...")
        try:
            result = subprocess.run([login_tool], cwd=str(Path(login_tool).parent), timeout=300)
            if result.returncode == 0:
                self._load_cookies_from_json()
                logger.info("Cookie 刷新成功!")
                return True
            else:
                logger.error(f"Login tool exited with code {result.returncode}")
        except subprocess.TimeoutExpired:
            logger.error("Login tool timed out (5 min)")
        except Exception as e:
            logger.error(f"Login tool error: {e}")
        return False

    @abstractmethod
    def get_platform_name(self) -> str:
        pass

    @abstractmethod
    async def search(self, keywords: list[str], limit: int = 20) -> list[dict]:
        pass

    async def collect(self, topic: dict, limit: int = 20) -> list[MaterialItem]:
        if self.platform_name not in topic.get("platforms", []):
            return []

        if not self.platform_config.get("enabled", False):
            logger.warning(f"Platform {self.platform_name} is disabled")
            return []

        keywords = topic.get("keywords", [])
        topic_name = topic.get("name", "")
        rate_limit = self.platform_config.get("rate_limit_seconds", 3)

        all_items = []
        for keyword in keywords:
            try:
                raw_results = await self.search([keyword], limit=limit // len(keywords))
                for raw in raw_results:
                    item = self.parse_result(raw, topic_name)
                    if item:
                        all_items.append(item)
                time.sleep(rate_limit)
            except Exception as e:
                logger.error(f"Error collecting '{keyword}' from {self.platform_name}: {e}")

        seen_urls = set()
        unique_items = []
        for item in all_items:
            if item.source_url not in seen_urls:
                seen_urls.add(item.source_url)
                unique_items.append(item)

        return unique_items[:limit]

    @abstractmethod
    def parse_result(self, raw: dict, topic_name: str) -> MaterialItem | None:
        pass

    def save_results(self, items: list[MaterialItem], output_dir: Path):
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = output_dir / f"{self.platform_name}_{timestamp}.json"
        data = [item.to_dict() for item in items]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(items)} items to {filepath}")

        # 下载媒体文件到本地
        media_dir = output_dir / f"{self.platform_name}_{timestamp}_media"
        self._download_media(items, media_dir)

        return filepath

    def _download_media(self, items: list[MaterialItem], media_dir: Path):
        """下载所有素材的图片/视频到本地"""
        import httpx

        if not any(item.media_urls for item in items):
            return

        media_dir.mkdir(parents=True, exist_ok=True)
        downloaded = 0

        with httpx.Client(timeout=30, follow_redirects=True) as client:
            for i, item in enumerate(items):
                for j, url in enumerate(item.media_urls):
                    if not url or not url.startswith("http"):
                        continue
                    try:
                        ext = ".jpg" if item.media_type == "image" else ".mp4"
                        if ".webp" in url:
                            ext = ".webp"
                        elif ".png" in url:
                            ext = ".png"

                        filename = f"{i:03d}_{j:02d}{ext}"
                        filepath = media_dir / filename
                        resp = client.get(url)
                        if resp.status_code == 200:
                            filepath.write_bytes(resp.content)
                            downloaded += 1
                    except Exception as e:
                        logger.debug(f"Failed to download {url[:60]}: {e}")

        if downloaded:
            logger.info(f"Downloaded {downloaded} media files to {media_dir}")
