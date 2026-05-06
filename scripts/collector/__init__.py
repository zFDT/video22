"""Collector package init"""

from .base_collector import BaseCollector, MaterialItem
from .xhs_collector import XhsCollector
from .douyin_collector import DouyinCollector
from .weibo_collector import WeiboCollector

__all__ = ["BaseCollector", "MaterialItem", "XhsCollector", "DouyinCollector", "WeiboCollector"]
