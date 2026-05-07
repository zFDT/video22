"""重试与退避工具 - 提供统一的网络请求重试机制"""

import asyncio
import logging
import random
import time
from functools import wraps
from typing import Callable, Any, TypeVar, Optional

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RetryConfig:
    """重试配置"""
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 30.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def get_delay(self, attempt: int) -> float:
        """计算指定尝试次数的等待时长（指数退避）"""
        delay = min(
            self.initial_delay * (self.exponential_base ** attempt),
            self.max_delay,
        )
        if self.jitter:
            # 添加随机抖动以避免同时重试
            delay *= (0.5 + random.random())
        return delay


def retry_sync(
    config: Optional[RetryConfig] = None,
    on_exception: Optional[Callable[[Exception, int], None]] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """同步函数的重试装饰器"""
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            for attempt in range(config.max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if on_exception:
                        on_exception(e, attempt)
                    if attempt < config.max_retries - 1:
                        delay = config.get_delay(attempt)
                        logger.debug(
                            f"{func.__name__} failed (attempt {attempt + 1}/{config.max_retries}): "
                            f"{e.__class__.__name__}. Retrying in {delay:.2f}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.warning(
                            f"{func.__name__} failed after {config.max_retries} attempts: {e}"
                        )
            if last_exception:
                raise last_exception
        return wrapper
    return decorator


def retry_async(
    config: Optional[RetryConfig] = None,
    on_exception: Optional[Callable[[Exception, int], None]] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """异步函数的重试装饰器"""
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            for attempt in range(config.max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if on_exception:
                        on_exception(e, attempt)
                    if attempt < config.max_retries - 1:
                        delay = config.get_delay(attempt)
                        logger.debug(
                            f"{func.__name__} failed (attempt {attempt + 1}/{config.max_retries}): "
                            f"{e.__class__.__name__}. Retrying in {delay:.2f}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.warning(
                            f"{func.__name__} failed after {config.max_retries} attempts: {e}"
                        )
            if last_exception:
                raise last_exception
        return wrapper
    return decorator


def retry_call_sync(
    func: Callable[..., T],
    *args,
    config: Optional[RetryConfig] = None,
    on_exception: Optional[Callable[[Exception, int], None]] = None,
    **kwargs
) -> T:
    """直接调用同步函数并实现重试"""
    if config is None:
        config = RetryConfig()
    
    last_exception = None
    for attempt in range(config.max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if on_exception:
                on_exception(e, attempt)
            if attempt < config.max_retries - 1:
                delay = config.get_delay(attempt)
                logger.debug(
                    f"{func.__name__} failed (attempt {attempt + 1}/{config.max_retries}): "
                    f"{e.__class__.__name__}. Retrying in {delay:.2f}s..."
                )
                time.sleep(delay)
            else:
                logger.warning(
                    f"{func.__name__} failed after {config.max_retries} attempts: {e}"
                )
    if last_exception:
        raise last_exception


async def retry_call_async(
    func: Callable[..., Any],
    *args,
    config: Optional[RetryConfig] = None,
    on_exception: Optional[Callable[[Exception, int], None]] = None,
    **kwargs
) -> Any:
    """直接调用异步函数并实现重试"""
    if config is None:
        config = RetryConfig()
    
    last_exception = None
    for attempt in range(config.max_retries):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if on_exception:
                on_exception(e, attempt)
            if attempt < config.max_retries - 1:
                delay = config.get_delay(attempt)
                logger.debug(
                    f"{func.__name__} failed (attempt {attempt + 1}/{config.max_retries}): "
                    f"{e.__class__.__name__}. Retrying in {delay:.2f}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.warning(
                    f"{func.__name__} failed after {config.max_retries} attempts: {e}"
                )
    if last_exception:
        raise last_exception
