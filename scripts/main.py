"""
多平台内容采集 & 自动化创作工作流 - 主入口

流程：启动浏览器 → 登录一次 → 复用同一浏览器完成所有采集 → 关闭

用法:
    python main.py                    # 执行全流程
    python main.py --collect          # 仅采集
    python main.py --organize         # 仅整理
    python main.py --generate         # 仅生成
    python main.py --topic fdm_3d_printing  # 指定话题
"""

import asyncio
import argparse
import json
import logging
import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from collector import XhsCollector, DouyinCollector
from organizer import MaterialOrganizer
from generator import ContentGenerator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(PROJECT_ROOT / "logs" / f"run_{datetime.now():%Y%m%d_%H%M%S}.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def init_browsers(config_dir: Path) -> tuple:
    """启动浏览器并完成登录（每次流程只需登录一次）

    返回 (xhs_page, douyin_page) 两个已登录的浏览器实例。
    使用持久化用户数据目录，如果之前登录过可能自动跳过登录。
    """
    logger.info("=== 初始化浏览器 ===")

    # 小红书浏览器
    logger.info("启动小红书浏览器...")
    xhs_page = XhsCollector.create_browser()
    XhsCollector.wait_for_login(xhs_page)

    # 抖音浏览器
    logger.info("启动抖音浏览器...")
    douyin_page = DouyinCollector.create_browser()
    DouyinCollector.wait_for_login(douyin_page)

    logger.info("=== 浏览器初始化完成，开始采集 ===\n")
    return xhs_page, douyin_page


async def run_collection(config_dir: Path, output_base: Path, xhs_page, douyin_page, topic_filter: str | None = None):
    """Phase 1: 多平台素材采集（复用已登录的浏览器实例）"""
    logger.info("=== Phase 1: Content Collection ===")

    topics_config = json.loads((config_dir / "topics.json").read_text(encoding="utf-8"))
    topics = topics_config["topics"]
    collection_config = topics_config["collection"]

    if topic_filter:
        topics = [t for t in topics if t["slug"] == topic_filter]

    xhs_collector = XhsCollector(config_dir, page=xhs_page)
    douyin_collector = DouyinCollector(config_dir, page=douyin_page)
    collectors = [xhs_collector, douyin_collector]

    total_collected = 0
    for topic in topics:
        logger.info(f"Collecting for topic: {topic['name']}")
        for collector in collectors:
            try:
                items = await collector.collect(topic, limit=collection_config["max_items_per_topic"])
                if items:
                    output_dir = output_base / collector.get_platform_name()
                    collector.save_results(items, output_dir)
                    total_collected += len(items)
                    logger.info(f"  {collector.get_platform_name()}: {len(items)} items")
            except Exception as e:
                logger.error(f"  {collector.get_platform_name()} failed: {e}")

    logger.info(f"Collection complete. Total: {total_collected} items")
    return total_collected


def run_organization(project_root: Path) -> dict:
    """Phase 2: 素材整理"""
    logger.info("=== Phase 2: Material Organization ===")
    organizer = MaterialOrganizer(project_root)
    metadata = organizer.organize()
    logger.info(f"Organization complete. Total organized: {metadata.get('total_items', 0)} items")
    return metadata


def run_generation(project_root: Path, topic_filter: str | None = None) -> list[dict]:
    """Phase 3: 内容生成"""
    logger.info("=== Phase 3: Content Generation ===")
    generator = ContentGenerator(project_root)
    organizer = MaterialOrganizer(project_root)
    topics_config = json.loads((project_root / "config" / "topics.json").read_text(encoding="utf-8"))

    all_outputs = []
    for topic in topics_config["topics"]:
        slug = topic["slug"]
        if topic_filter and slug != topic_filter:
            continue

        materials = organizer.get_top_materials(slug, limit=10)
        if not materials:
            logger.warning(f"No organized materials for {slug}, skipping generation")
            continue

        output = generator.analyze_and_generate(slug, materials)
        all_outputs.append(output)

        posts = output.get("posts", [])
        image_prompts = generator.generate_image_prompts(posts)
        video_prompts = generator.generate_video_prompts(posts)

        prompts_dir = project_root / "output" / "posts"
        prompts_dir.mkdir(parents=True, exist_ok=True)

        if image_prompts:
            img_path = prompts_dir / f"{slug}_image_prompts.json"
            img_path.write_text(json.dumps(image_prompts, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info(f"  Image prompts: {len(image_prompts)} saved to {img_path}")

        if video_prompts:
            vid_path = prompts_dir / f"{slug}_video_prompts.json"
            vid_path.write_text(json.dumps(video_prompts, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info(f"  Video prompts: {len(video_prompts)} saved to {vid_path}")

    logger.info(f"Generation complete. {len(all_outputs)} topics processed")
    return all_outputs


async def main():
    parser = argparse.ArgumentParser(description="多平台内容采集 & 自动化创作工作流")
    parser.add_argument("--collect", action="store_true", help="仅执行采集")
    parser.add_argument("--organize", action="store_true", help="仅执行整理")
    parser.add_argument("--generate", action="store_true", help="仅执行生成")
    parser.add_argument("--topic", type=str, default=None, help="指定话题 slug (如 fdm_3d_printing)")
    args = parser.parse_args()

    run_all = not (args.collect or args.organize or args.generate)
    config_dir = PROJECT_ROOT / "config"
    raw_dir = PROJECT_ROOT / "materials" / "raw"

    logger.info(f"Workflow started at {datetime.now().isoformat()}")
    logger.info(f"Project root: {PROJECT_ROOT}")

    xhs_page = None
    douyin_page = None

    try:
        # 采集阶段：启动浏览器 → 登录 → 采集 → 关闭
        if run_all or args.collect:
            xhs_page, douyin_page = init_browsers(config_dir)
            await run_collection(config_dir, raw_dir, xhs_page, douyin_page, args.topic)

        if run_all or args.organize:
            run_organization(PROJECT_ROOT)

        if run_all or args.generate:
            run_generation(PROJECT_ROOT, args.topic)

    finally:
        # 采集完成后关闭浏览器
        if xhs_page:
            try:
                xhs_page.quit()
                logger.info("XHS browser closed")
            except Exception:
                pass
        if douyin_page:
            try:
                douyin_page.quit()
                logger.info("Douyin browser closed")
            except Exception:
                pass

    logger.info("Workflow completed successfully.")


if __name__ == "__main__":
    asyncio.run(main())
