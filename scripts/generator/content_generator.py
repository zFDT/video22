"""内容生成编排脚本 - 调用 Claude Code skills 进行选题分析和内容生成"""

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

    def _load_topics_config(self) -> dict:
        config_path = self.project_root / "config" / "topics.json"
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def analyze_and_generate(self, topic_slug: str, materials: list[dict]) -> dict:
        """对指定话题的素材进行分析并生成内容"""
        if not materials:
            logger.warning(f"No materials for topic: {topic_slug}")
            return {}

        analysis = self._analyze_topic(topic_slug, materials)
        copywriting = self._generate_copywriting(topic_slug, analysis, materials)
        output = {
            "topic": topic_slug,
            "generated_at": datetime.now().isoformat(),
            "analysis": analysis,
            "posts": copywriting,
        }

        self._save_posts(topic_slug, output)
        return output

    def _analyze_topic(self, topic_slug: str, materials: list[dict]) -> dict:
        """分析话题趋势 - 生成选题方向建议"""
        titles = [m.get("title", "") for m in materials[:10]]
        contents = [m.get("content", "")[:200] for m in materials[:5]]
        platforms = {}
        for m in materials:
            p = m.get("platform", "unknown")
            platforms[p] = platforms.get(p, 0) + 1

        total_likes = sum(m.get("metrics", {}).get("likes", 0) for m in materials)
        avg_likes = total_likes // len(materials) if materials else 0

        analysis = {
            "topic_slug": topic_slug,
            "material_count": len(materials),
            "platform_distribution": platforms,
            "avg_engagement": avg_likes,
            "top_titles": titles[:5],
            "content_samples": contents[:3],
            "suggested_angles": self._suggest_angles(topic_slug, titles, contents),
        }
        return analysis

    def _suggest_angles(self, topic_slug: str, titles: list[str], contents: list[str]) -> list[str]:
        """基于素材内容推荐创作角度"""
        angle_map = {
            "fdm_3d_printing": [
                "新手入门指南：FDM打印避坑攻略",
                "耗材对比评测：PLA vs PETG 实测",
                "创意打印作品展示",
                "打印失败排查：常见问题解决方案",
            ],
            "atomic_reshaping": [
                "前沿科技解读：原子重塑技术原理",
                "应用场景展望：从实验室到产业化",
                "技术对比：传统制造 vs 原子级制造",
            ],
            "dreame": [
                "追觅新品深度评测",
                "追觅 vs 竞品对比",
                "智能清洁解决方案推荐",
                "追觅使用技巧分享",
            ],
        }
        return angle_map.get(topic_slug, ["通用话题讨论"])

    def _generate_copywriting(self, topic_slug: str, analysis: dict, materials: list[dict]) -> list[dict]:
        """生成多平台文案"""
        copy_config = self.config.get("copywriting", {})
        platforms_style = copy_config.get("platforms", {})
        angles = analysis.get("suggested_angles", [])

        posts = []
        for i, angle in enumerate(angles[:3]):
            ref_material = materials[i] if i < len(materials) else materials[0]

            for platform, style_config in platforms_style.items():
                post = {
                    "angle": angle,
                    "platform": platform,
                    "style": style_config.get("style", ""),
                    "reference_material": {
                        "title": ref_material.get("title", ""),
                        "source_url": ref_material.get("source_url", ""),
                    },
                    "prompt_for_claude": self._build_copy_prompt(angle, platform, style_config, ref_material),
                    "status": "pending_generation",
                }
                posts.append(post)

        return posts

    def _build_copy_prompt(self, angle: str, platform: str, style_config: dict, ref_material: dict) -> str:
        """构建给 Claude Code 的文案生成 prompt"""
        style = style_config.get("style", "")
        max_len = self.config.get("copywriting", {}).get("max_length", 500)
        hashtag_count = self.config.get("copywriting", {}).get("hashtag_count", 5)

        prompt = f"""请为{platform}平台生成一篇关于"{angle}"的内容文案。

要求：
- 风格：{style}
- 字数限制：{max_len}字以内
- 包含{hashtag_count}个相关话题标签
- 参考素材标题：{ref_material.get('title', '')}
- 参考素材内容摘要：{ref_material.get('content', '')[:200]}

请直接输出文案内容，包含标题和正文。"""
        return prompt

    def _save_posts(self, topic_slug: str, output: dict):
        posts_dir = self.output_dir / "posts"
        posts_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = posts_dir / f"{topic_slug}_{timestamp}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        logger.info(f"Posts saved to {filepath}")

    def generate_image_prompts(self, posts: list[dict]) -> list[dict]:
        """为文案生成配图 prompt"""
        image_config = self.config.get("image", {})
        prompts = []
        for post in posts:
            if post.get("status") == "pending_generation":
                prompt = {
                    "post_angle": post["angle"],
                    "platform": post["platform"],
                    "image_prompt": f"Create a visually appealing image for: {post['angle']}. "
                                    f"Style: modern tech, clean design. Aspect ratio: {image_config.get('aspect_ratio', '1:1')}",
                    "resolution": image_config.get("resolution", "1024x1024"),
                    "provider": image_config.get("provider", "inference-skills"),
                }
                prompts.append(prompt)
        return prompts

    def generate_video_prompts(self, posts: list[dict]) -> list[dict]:
        """为文案生成视频 prompt"""
        video_config = self.config.get("video", {})
        prompts = []
        for post in posts:
            if post.get("platform") == "douyin" and post.get("status") == "pending_generation":
                prompt = {
                    "post_angle": post["angle"],
                    "video_prompt": f"Create a short-form video about: {post['angle']}. "
                                    f"Duration: {video_config.get('duration_seconds', 15)}s. "
                                    f"Style: engaging, informative.",
                    "duration": video_config.get("duration_seconds", 15),
                    "resolution": video_config.get("resolution", "1080x1920"),
                    "provider": video_config.get("provider", "deer-flow"),
                }
                prompts.append(prompt)
        return prompts
