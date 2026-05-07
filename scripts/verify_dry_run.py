"""干运行（Dry-run）验证脚本 - 测试项目配置和模块完整性（无需打开浏览器）"""

import sys
import json
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def check_config_files():
    """检查配置文件完整性"""
    logger.info("=== 检查配置文件 ===")
    config_dir = PROJECT_ROOT / "config"
    required_files = {
        "topics.json": "话题配置",
        "platforms.json": "平台配置",
        "generation.json": "生成配置",
    }

    all_ok = True
    for filename, description in required_files.items():
        filepath = config_dir / filename
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.info(f"✓ {filename} ({description})")
            except Exception as e:
                logger.error(f"✗ {filename} 格式错误: {e}")
                all_ok = False
        else:
            logger.error(f"✗ {filename} 不存在")
            all_ok = False

    return all_ok


def check_modules():
    """检查核心模块可加载性"""
    logger.info("\n=== 检查核心模块 ===")
    modules_to_check = [
        ("utils.retry_utils", "重试工具"),
        ("utils.concurrency_utils", "并发工具"),
        ("collector.base_collector", "采集基类"),
        ("collector.xhs_collector", "小红书采集器"),
        ("collector.douyin_collector", "抖音采集器"),
        ("organizer.material_organizer", "素材整理器"),
        ("generator.content_generator", "内容生成器"),
    ]

    all_ok = True
    for module_name, description in modules_to_check:
        try:
            __import__(module_name)
            logger.info(f"✓ {module_name} ({description})")
        except Exception as e:
            logger.error(f"✗ {module_name} 加载失败: {e}")
            all_ok = False

    return all_ok


def check_data_models():
    """检查数据模型和序列化"""
    logger.info("\n=== 检查数据模型 ===")
    try:
        from collector.base_collector import MaterialItem
        from datetime import datetime

        # 创建测试素材项
        item = MaterialItem(
            id="test-001",
            platform="xhs",
            topic="fdm_3d_printing",
            title="测试笔记",
            content="这是一条测试笔记内容",
            media_urls=["https://example.com/image.jpg"],
            media_type="image",
            metrics={"likes": 100, "author": "test_user"},
            source_url="https://www.xiaohongshu.com/explore/test",
        )

        # 检查序列化
        item_dict = item.to_dict()
        logger.info(f"✓ MaterialItem 创建和序列化成功")
        logger.info(f"  - ID: {item.id}")
        logger.info(f"  - 平台: {item.platform}")
        logger.info(f"  - 话题: {item.topic}")

        # 检查 JSON 序列化
        json_str = json.dumps(item_dict, ensure_ascii=False)
        logger.info(f"✓ JSON 序列化成功 ({len(json_str)} bytes)")

        return True
    except Exception as e:
        logger.error(f"✗ 数据模型检查失败: {e}")
        return False


def check_collector_init():
    """检查采集器初始化（不实际采集）"""
    logger.info("\n=== 检查采集器初始化 ===")
    try:
        from collector.base_collector import BaseCollector
        from collector.xhs_collector import XhsCollector

        config_dir = PROJECT_ROOT / "config"

        # 初始化小红书采集器（不启动浏览器）
        collector = XhsCollector(config_dir, page=None)
        logger.info(f"✓ {collector.get_platform_name()} 采集器初始化成功")
        logger.info(f"  - 平台名称: {collector.platform_name}")
        logger.info(f"  - 平台配置: {collector.platform_config.get('enabled', 'N/A')}")

        return True
    except Exception as e:
        logger.error(f"✗ 采集器初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_organizer():
    """检查素材整理器"""
    logger.info("\n=== 检查素材整理器 ===")
    try:
        from organizer.material_organizer import MaterialOrganizer

        organizer = MaterialOrganizer(PROJECT_ROOT)
        logger.info(f"✓ MaterialOrganizer 初始化成功")
        logger.info(f"  - 项目根: {organizer.project_root}")
        logger.info(f"  - 原始数据目录: {organizer.raw_dir}")
        logger.info(f"  - 整理后数据目录: {organizer.organized_dir}")

        # 检查元数据
        if organizer.metadata_path.exists():
            with open(organizer.metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            logger.info(f"✓ 元数据文件存在，包含 {metadata.get('total_items', 0)} 项素材")
        else:
            logger.info(f"ℹ 元数据文件不存在（首次运行正常）")

        return True
    except Exception as e:
        logger.error(f"✗ 素材整理器检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_generator():
    """检查内容生成器"""
    logger.info("\n=== 检查内容生成器 ===")
    try:
        from generator.content_generator import ContentGenerator

        generator = ContentGenerator(PROJECT_ROOT)
        logger.info(f"✓ ContentGenerator 初始化成功")
        logger.info(f"  - 输出目录: {generator.output_dir}")

        # 检查生成配置
        logger.info(f"  - 图片配置: {generator.config.get('image', {}).get('provider', 'N/A')}")
        logger.info(f"  - 视频配置: {generator.config.get('video', {}).get('provider', 'N/A')}")
        logger.info(f"  - 文案音调: {generator.config.get('copywriting', {}).get('tone', 'N/A')}")

        return True
    except Exception as e:
        logger.error(f"✗ 内容生成器检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_directories():
    """检查必要的目录结构"""
    logger.info("\n=== 检查目录结构 ===")
    required_dirs = {
        "config": "配置目录",
        "scripts": "脚本目录",
        "materials": "素材目录",
        "output": "输出目录",
        "logs": "日志目录",
    }

    all_ok = True
    for dirname, description in required_dirs.items():
        dirpath = PROJECT_ROOT / dirname
        if dirpath.exists():
            logger.info(f"✓ {dirname}/ ({description})")
        else:
            logger.warning(f"⚠ {dirname}/ ({description}) 不存在，首次运行时会创建")

    return True


def main():
    """执行所有检查"""
    logger.info("=" * 60)
    logger.info("多平台内容采集 & 自动化创作工作流 - Dry-run 验证")
    logger.info("=" * 60)

    checks = [
        ("配置文件", check_config_files),
        ("核心模块", check_modules),
        ("数据模型", check_data_models),
        ("采集器初始化", check_collector_init),
        ("素材整理器", check_organizer),
        ("内容生成器", check_generator),
        ("目录结构", check_directories),
    ]

    results = {}
    for check_name, check_func in checks:
        try:
            results[check_name] = check_func()
        except Exception as e:
            logger.error(f"检查 {check_name} 时出现异常: {e}")
            import traceback
            traceback.print_exc()
            results[check_name] = False

    # 总结
    logger.info("\n" + "=" * 60)
    logger.info("验证总结")
    logger.info("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for check_name, result in results.items():
        status = "✓ 通过" if result else "✗ 失败"
        logger.info(f"{status}: {check_name}")

    logger.info(f"\n总体: {passed}/{total} 项检查通过")

    if passed == total:
        logger.info("\n✓ 项目配置和模块完整性检查全部通过！")
        logger.info("可以开始执行采集任务：python scripts/main.py --collect")
        return 0
    else:
        logger.error("\n✗ 部分检查未通过，请解决问题后重试")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
