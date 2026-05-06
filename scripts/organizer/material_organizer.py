"""素材整理模块 - 对采集的原始素材进行分类、去重、排序"""

import json
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class MaterialOrganizer:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.raw_dir = project_root / "materials" / "raw"
        self.organized_dir = project_root / "materials" / "organized"
        self.metadata_path = project_root / "materials" / "metadata.json"
        self.config = self._load_config()

    def _load_config(self) -> dict:
        config_path = self.project_root / "config" / "topics.json"
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def organize(self) -> dict:
        """主入口：整理所有原始素材"""
        all_items = self._load_all_raw()
        logger.info(f"Loaded {len(all_items)} raw items total")

        deduped = self._deduplicate(all_items)
        logger.info(f"After dedup: {len(deduped)} items")

        classified = self._classify_by_topic(deduped)

        min_likes = self.config.get("collection", {}).get("min_likes", 0)
        for topic_slug, items in classified.items():
            filtered = [i for i in items if i.get("metrics", {}).get("likes", 0) >= min_likes]
            filtered.sort(key=lambda x: x.get("metrics", {}).get("likes", 0), reverse=True)
            classified[topic_slug] = filtered
            self._save_organized(topic_slug, filtered)

        metadata = self._build_metadata(classified)
        self._save_metadata(metadata)

        return metadata

    def _load_all_raw(self) -> list[dict]:
        items = []
        for platform_dir in self.raw_dir.iterdir():
            if not platform_dir.is_dir():
                continue
            for json_file in platform_dir.glob("*.json"):
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            items.extend(data)
                except Exception as e:
                    logger.error(f"Error loading {json_file}: {e}")
        return items

    def _deduplicate(self, items: list[dict]) -> list[dict]:
        seen = set()
        unique = []
        for item in items:
            key = item.get("source_url", "") or f"{item.get('platform')}:{item.get('title', '')}"
            if key and key not in seen:
                seen.add(key)
                unique.append(item)
        return unique

    def _classify_by_topic(self, items: list[dict]) -> dict[str, list[dict]]:
        topics = self.config.get("topics", [])
        classified = {t["slug"]: [] for t in topics}

        for item in items:
            item_topic = item.get("topic", "")
            for topic in topics:
                if item_topic == topic["name"]:
                    classified[topic["slug"]].append(item)
                    break
            else:
                title_content = f"{item.get('title', '')} {item.get('content', '')}".lower()
                for topic in topics:
                    if any(kw.lower() in title_content for kw in topic["keywords"]):
                        classified[topic["slug"]].append(item)
                        break

        return classified

    def _save_organized(self, topic_slug: str, items: list[dict]):
        output_dir = self.organized_dir / topic_slug
        output_dir.mkdir(parents=True, exist_ok=True)
        filepath = output_dir / "materials.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(items)} items to {filepath}")

    def _build_metadata(self, classified: dict[str, list[dict]]) -> dict:
        metadata = {
            "last_organized": datetime.now().isoformat(),
            "total_items": sum(len(v) for v in classified.values()),
            "topics": {},
        }
        for slug, items in classified.items():
            platforms = {}
            for item in items:
                p = item.get("platform", "unknown")
                platforms[p] = platforms.get(p, 0) + 1

            metadata["topics"][slug] = {
                "count": len(items),
                "platforms": platforms,
                "top_items": [
                    {"title": i["title"], "likes": i.get("metrics", {}).get("likes", 0), "platform": i["platform"]}
                    for i in items[:5]
                ],
            }
        return metadata

    def _save_metadata(self, metadata: dict):
        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        logger.info(f"Metadata saved to {self.metadata_path}")

    def get_top_materials(self, topic_slug: str, limit: int = 10) -> list[dict]:
        """获取某话题下热度最高的素材"""
        filepath = self.organized_dir / topic_slug / "materials.json"
        if not filepath.exists():
            return []
        with open(filepath, "r", encoding="utf-8") as f:
            items = json.load(f)
        return items[:limit]
