"""抖音采集器 - 单浏览器实例复用，采集视频信息并下载"""

import logging
import time
import re
import sys
from pathlib import Path

from .base_collector import BaseCollector, MaterialItem, BROWSER_DATA_DIR
sys_path = str(Path(__file__).parent.parent)
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)
from utils.retry_utils import RetryConfig, retry_call_sync

logger = logging.getLogger(__name__)

try:
    from DrissionPage import ChromiumPage, ChromiumOptions
    DRISSION_AVAILABLE = True
except ImportError:
    DRISSION_AVAILABLE = False
    logger.warning("DrissionPage not installed. Run: pip install DrissionPage")

DOUYIN_BROWSER_DATA = BROWSER_DATA_DIR / "douyin"
DOUYIN_PORT = 9512


class DouyinCollector(BaseCollector):
    def __init__(self, config_dir, page: "ChromiumPage | None" = None):
        super().__init__(config_dir)
        self._page = page

    def get_platform_name(self) -> str:
        return "douyin"

    def set_page(self, page: "ChromiumPage"):
        self._page = page

    @staticmethod
    def create_browser() -> "ChromiumPage":
        """创建独立的浏览器实例（固定端口 9512）"""
        co = ChromiumOptions()
        co.set_user_data_path(str(DOUYIN_BROWSER_DATA))
        co.set_local_port(DOUYIN_PORT)
        co.set_argument("--disable-blink-features=AutomationControlled")
        co.set_argument("--no-first-run")
        co.set_argument("--no-default-browser-check")
        return ChromiumPage(co)

    @staticmethod
    def wait_for_login(page: "ChromiumPage") -> bool:
        """打开抖音首页，检测登录状态"""
        page.get("https://www.douyin.com")
        time.sleep(3)
        avatar = page.ele("css:[class*='avatar']", timeout=3)
        if avatar:
            logger.info("Douyin: 已登录（复用上次 session）")
            return True
        logger.info("Douyin: 需要登录，请在浏览器中完成登录")
        input(">>> 抖音登录完成后，按回车继续...")
        return True

    def _check_captcha(self) -> bool:
        """检测抖音的机器人验证（精确匹配）"""
        captcha_signs = [
            "css:#captcha-verify-image",
            "css:.captcha_verify_container",
            "css:.secsdk-captcha-drag-icon",
        ]
        for selector in captcha_signs:
            el = self._page.ele(selector, timeout=1)
            if el:
                logger.warning("⚠️  检测到机器人验证，请在浏览器中完成验证")
                input(">>> 验证完成后按回车继续...")
                time.sleep(2)
                return True

        verify_text = self._page.ele("text:请完成验证", timeout=1)
        if verify_text:
            logger.warning("⚠️  检测到验证提示，请在浏览器中完成")
            input(">>> 验证完成后按回车继续...")
            time.sleep(2)
            return True
        return False

    async def search(self, keywords: list[str], limit: int = 20) -> list[dict]:
        if not DRISSION_AVAILABLE or not self._page:
            logger.error("Browser not available")
            return []

        keyword = " ".join(keywords)
        results = []

        try:
            search_url = f"https://www.douyin.com/search/{keyword}?type=video"
            self._page.get(search_url)
            time.sleep(4)
            self._check_captcha()

            # 滚动加载更多
            scroll_count = min(limit // 5 + 1, 3)
            for i in range(scroll_count):
                self._page.scroll.to_bottom()
                time.sleep(2)
                self._check_captcha()

            # 解析视频卡片
            video_cards = self._page.eles("css:[data-e2e='scroll-list'] > div", timeout=5)
            if not video_cards:
                video_cards = self._page.eles("css:.search-result-card", timeout=3)
            if not video_cards:
                video_cards = self._page.eles("css:li[class*='video']", timeout=3)

            logger.info(f"Found {len(video_cards)} video cards for '{keyword}'")

            for card in video_cards[:limit]:
                try:
                    title_el = card.ele("css:a[title]", timeout=1) or card.ele("css:.title", timeout=1)
                    title = (title_el.attr("title") or title_el.text) if title_el else ""

                    author_el = card.ele("css:[data-e2e='search-card-user-name']", timeout=1)
                    author = author_el.text if author_el else ""

                    likes_el = card.ele("css:[data-e2e='search-like-count']", timeout=1)
                    likes_text = likes_el.text if likes_el else "0"

                    link_el = card.ele("css:a[href*='/video/']", timeout=1)
                    href = link_el.attr("href") if link_el else ""

                    cover_el = card.ele("css:img[src*='image']", timeout=1) or card.ele("css:img", timeout=1)
                    cover_url = cover_el.attr("src") if cover_el else ""

                    if not title:
                        continue

                    video_url = href if href and href.startswith("http") else f"https://www.douyin.com{href}" if href else ""

                    # 进入视频详情页获取文案和视频源
                    desc, video_src = self._get_video_detail(video_url)

                    results.append({
                        "aweme_id": self._extract_video_id(href),
                        "desc": desc or title,
                        "statistics": {"digg_count": self._parse_count(likes_text)},
                        "video_cover": cover_url,
                        "video_src": video_src,
                        "author": author,
                        "source_url": video_url,
                    })
                except Exception as e:
                    logger.debug(f"Error parsing video card: {e}")
                    continue
        except Exception as e:
            logger.error(f"Douyin search error: {e}")

        return results

    def _get_video_detail(self, video_url: str) -> tuple[str, str]:
        """进入视频详情页获取完整文案和视频源地址（带重试）"""
        def _fetch_video_detail():
            desc = ""
            video_src = ""
            if not video_url:
                return desc, video_src

            try:
                self._page.get(video_url)
                time.sleep(3)
                self._check_captcha()

                # 获取视频文案
                desc_el = (
                    self._page.ele("css:[data-e2e='video-desc']", timeout=3)
                    or self._page.ele("css:[class*='desc']", timeout=2)
                    or self._page.ele("css:.video-info-detail", timeout=2)
                )
                if desc_el:
                    desc = desc_el.text

                # 获取视频源地址（从 video 标签）
                video_el = self._page.ele("css:video source", timeout=3) or self._page.ele("css:video", timeout=2)
                if video_el:
                    video_src = video_el.attr("src") or ""

                # 返回搜索页
                self._page.back()
                time.sleep(2)

            except Exception as e:
                logger.debug(f"Error getting video detail from {video_url}: {e}")
                try:
                    self._page.back()
                    time.sleep(1)
                except Exception:
                    pass
                raise

            return desc, video_src

        # 为详情获取添加重试机制
        try:
            return retry_call_sync(
                _fetch_video_detail,
                config=RetryConfig(max_retries=2, initial_delay=0.5)
            )
        except Exception as e:
            logger.warning(f"Failed to get video detail after retries: {e}")
            return "", ""

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

        stats = raw.get("statistics", {})
        media_urls = []
        if raw.get("video_src"):
            media_urls.append(raw["video_src"])
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
            metrics={"likes": stats.get("digg_count", 0), "author": raw.get("author", "")},
            source_url=raw.get("source_url", ""),
        )
