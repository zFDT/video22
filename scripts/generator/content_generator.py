"""内容生成模块 - 调用 Claude 生成文案，图片生成预留接口"""

import json
import subprocess
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class ContentGenerator:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.output_dir = project_root / "output"
        self.config = self._load_config()

    def _load_config(self) -> dict:
        config_path = self.project_root / "config" / "generation.json"
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def generate_all(self, topic_slug: str, materials: list[dict]) -> dict:
        """完整生成流程：分析 → 文案 → 图片（如果可用）"""
        if not materials:
            logger.warning(f"No materials for topic: {topic_slug}")
            return {}

        # Step 1: 分析选题方向
        analysis = self._analyze_topic(topic_slug, materials)

        # Step 2: 生成文案
        posts = self._generate_copywriting(topic_slug, analysis, materials)

        # Step 3: 保存结果
        output = {
            "topic": topic_slug,
            "generated_at": datetime.now().isoformat(),
            "analysis": analysis,
            "posts": posts,
        }
        self._save_output(topic_slug, output)
        return output

    def _analyze_topic(self, topic_slug: str, materials: list[dict]) -> dict:
        """分析素材，提取选题方向"""
        titles = [m.get("title", "") for m in materials[:10]]
        platforms = {}
        for m in materials:
            p = m.get("platform", "unknown")
            platforms[p] = platforms.get(p, 0) + 1

        total_likes = sum(m.get("metrics", {}).get("likes", 0) for m in materials)
        avg_likes = total_likes // len(materials) if materials else 0

        # 从素材标题中提取热门角度
        angles = self._suggest_angles(topic_slug, titles)

        return {
            "topic_slug": topic_slug,
            "material_count": len(materials),
            "platform_distribution": platforms,
            "avg_engagement": avg_likes,
            "top_titles": titles[:5],
            "suggested_angles": angles,
        }

    def _suggest_angles(self, topic_slug: str, titles: list[str]) -> list[str]:
        """基于素材推荐创作角度"""
        angle_map = {
            "fdm_3d_printing": [
                "新手入门：FDM 3D打印避坑指南",
                "耗材实测对比：PLA vs PETG vs ABS",
                "创意作品展示：用3D打印改造生活",
            ],
            "example_topic_2": [
                "示例话题角度一",
                "示例话题角度二",
                "示例话题角度三",
            ],
        }
        return angle_map.get(topic_slug, ["热门话题深度解读"])

    def _generate_copywriting(self, topic_slug: str, analysis: dict, materials: list[dict]) -> list[dict]:
        """使用 Claude 生成多平台文案"""
        copy_config = self.config.get("copywriting", {})
        platforms_style = copy_config.get("platforms", {})
        angles = analysis.get("suggested_angles", [])

        posts = []
        for i, angle in enumerate(angles[:3]):
            ref_material = materials[i] if i < len(materials) else materials[0]

            for platform, style_config in platforms_style.items():
                # 构建 prompt
                prompt = self._build_prompt(angle, platform, style_config, ref_material)

                # 调用 Claude 生成文案
                generated_text = self._call_claude(prompt)

                post = {
                    "angle": angle,
                    "platform": platform,
                    "style": style_config.get("style", ""),
                    "generated_text": generated_text,
                    "reference_material": {
                        "title": ref_material.get("title", ""),
                        "source_url": ref_material.get("source_url", ""),
                    },
                    "image_prompt": self._build_image_prompt(angle, topic_slug),
                    "status": "text_done" if generated_text else "failed",
                }
                posts.append(post)

        return posts

    def _build_prompt(self, angle: str, platform: str, style_config: dict, ref_material: dict) -> str:
        """构建文案生成 prompt"""
        style = style_config.get("style", "")
        max_len = self.config.get("copywriting", {}).get("max_length", 500)
        hashtag_count = self.config.get("copywriting", {}).get("hashtag_count", 5)

        platform_names = {"xhs": "小红书", "douyin": "抖音", "weibo": "微博"}
        platform_cn = platform_names.get(platform, platform)

        return f"""请为{platform_cn}平台生成一篇关于"{angle}"的内容文案。

要求：
- 风格：{style}
- 字数：{max_len}字以内
- 包含{hashtag_count}个相关话题标签
- 参考素材：{ref_material.get('title', '')}
- 内容要有信息量，不要空洞

直接输出文案（标题 + 正文 + 标签），不要解释。"""

    def _call_claude(self, prompt: str) -> str:
        """调用 Claude 生成文案（通过 claude CLI）"""
        try:
            result = subprocess.run(
                ["claude", "--print", "-p", prompt],
                capture_output=True, text=True, timeout=60, encoding="utf-8",
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            else:
                logger.warning(f"Claude CLI returned code {result.returncode}")
                if result.stderr:
                    logger.debug(f"stderr: {result.stderr[:200]}")
        except FileNotFoundError:
            logger.warning("Claude CLI not found, using prompt-only mode")
        except subprocess.TimeoutExpired:
            logger.warning("Claude CLI timed out")
        except Exception as e:
            logger.warning(f"Claude CLI error: {e}")

        return ""

    def _build_image_prompt(self, angle: str, topic_slug: str) -> str:
        """生成配图的英文 prompt（供后续图片生成服务使用）"""
        image_config = self.config.get("image", {})
        style = image_config.get("style", "modern_tech")

        return (
            f"Create a visually appealing social media image for: {angle}. "
            f"Style: {style}, clean modern design, vibrant colors. "
            f"Aspect ratio: {image_config.get('aspect_ratio', '1:1')}. "
            f"No text overlay."
        )

    def _save_output(self, topic_slug: str, output: dict):
        """保存生成结果"""
        posts_dir = self.output_dir / "posts"
        posts_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = posts_dir / f"{topic_slug}_{timestamp}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        logger.info(f"Generated content saved to {filepath}")

        # 同时保存纯文案文件（方便直接使用）
        text_dir = self.output_dir / "posts" / "text"
        text_dir.mkdir(parents=True, exist_ok=True)
        for i, post in enumerate(output.get("posts", [])):
            if post.get("generated_text"):
                text_file = text_dir / f"{topic_slug}_{post['platform']}_{i:02d}.txt"
                text_file.write_text(post["generated_text"], encoding="utf-8")

        logger.info(f"Text files saved to {text_dir}")
