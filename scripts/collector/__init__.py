"""Collector package init"""

from .base_collector import BaseCollector, MaterialItem
from .xhs_collector import XhsCollector
from .douyin_collector import DouyinCollector

__all__ = ["BaseCollector", "MaterialItem", "XhsCollector", "DouyinCollector"]
