"""小红书采集器 - 单浏览器实例复用，点击笔记获取详情"""

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
        """创建独立的浏览器实例（固定端口 9511）"""
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

    def _check_captcha(self) -> bool:
        """检测是否有真正的验证码弹窗（精确匹配，避免误报）"""
        # 只检测真正的滑块验证码容器
        captcha = self._page.ele("css:#captcha-div", timeout=1)
        if not captcha:
            captcha = self._page.ele("css:.captcha-container", timeout=1)
        if not captcha:
            # 检测是否整个页面被验证码覆盖
            captcha = self._page.ele("text:请通过验证", timeout=1)
        if captcha:
            logger.warning("检测到验证码，请在浏览器中完成验证")
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
            search_url = f"https://www.xiaohongshu.com/search_result?keyword={keyword}&source=web_search_result_note"
            self._page.get(search_url)
            time.sleep(3)
            self._check_captcha()

            # 等待搜索结果加载
            for _ in range(15):
                sections = self._page.eles("css:.note-item", timeout=2)
                if sections:
                    break
                time.sleep(1)

            note_items = self._page.eles("css:.note-item")
            logger.info(f"Found {len(note_items)} note items for '{keyword}'")

            for idx, item in enumerate(note_items[:limit]):
                try:
                    # 从列表获取基本信息
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

                    note_url = self._build_note_url(href)

                    # 点击笔记获取详情（弹窗模式）
                    detail_content, detail_images = self._get_detail_by_click(item)

                    results.append({
                        "id": href.split("/")[-1] if href else "",
                        "title": title,
                        "desc": detail_content or title,
                        "liked_count": self._parse_count(likes_text),
                        "image_list": detail_images or ([cover_url] if cover_url else []),
                        "user": author,
                        "source_url": note_url,
                    })
                except Exception as e:
                    logger.debug(f"Error parsing note item {idx}: {e}")
                    continue
        except Exception as e:
            logger.error(f"XHS search error: {e}")

        return results

    def _build_note_url(self, href: str) -> str:
        if not href:
            return ""
        if href.startswith("http"):
            return href
        if href.startswith("/"):
            return f"https://www.xiaohongshu.com{href}"
        return f"https://www.xiaohongshu.com/{href}"

    def _get_detail_by_click(self, item) -> tuple[str, list[str]]:
        """点击笔记卡片，从弹出的详情面板获取正文和图片"""
        content = ""
        images = []
        try:
            # 点击笔记卡片
            item.click()
            time.sleep(2)

            # 小红书搜索页点击后会弹出右侧详情面板
            # 获取正文
            desc_el = (
                self._page.ele("css:.note-content .desc", timeout=3)
                or self._page.ele("css:#detail-desc", timeout=2)
                or self._page.ele("css:[class*='note-text']", timeout=2)
                or self._page.ele("css:.content [class*='desc']", timeout=2)
            )
            if desc_el:
                content = desc_el.text

            # 获取所有图片
            img_els = (
                self._page.eles("css:.note-content img[src*='xhscdn']", timeout=2)
                or self._page.eles("css:.carousel-container img", timeout=2)
                or self._page.eles("css:[class*='slide'] img[src*='xhscdn']", timeout=2)
            )
            for img in img_els:
                src = img.attr("src")
                if src and ("xhscdn" in src or "sns-webpic" in src):
                    images.append(src)

            # 关闭详情面板（按 ESC 或点击关闭按钮）
            close_btn = self._page.ele("css:[class*='close']", timeout=1)
            if close_btn:
                close_btn.click()
            else:
                self._page.actions.key_down("ESCAPE").key_up("ESCAPE")
            time.sleep(0.5)

        except Exception as e:
            logger.debug(f"Error getting detail: {e}")
            # 确保关闭弹窗
            try:
                self._page.actions.key_down("ESCAPE").key_up("ESCAPE")
            except Exception:
                pass
            time.sleep(0.5)

        return content, images

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
