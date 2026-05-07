"""并发控制工具 - 提供受限的并发执行能力"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Any, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')


class AsyncSemaphore:
    """异步信号量包装器"""
    def __init__(self, max_concurrent: int = 3):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.max_concurrent = max_concurrent

    async def run(self, coro):
        """使用信号量限制并发"""
        async with self.semaphore:
            return await coro


class ConcurrentExecutor:
    """线程池执行器包装器"""
    def __init__(self, max_workers: int = 3):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def map(self, func: Callable[[T], Any], items: List[T], timeout: Optional[int] = None) -> List[Any]:
        """并发执行函数映射"""
        results = []
        futures = {self.executor.submit(func, item): item for item in items}
        
        for future in as_completed(futures, timeout=timeout):
            item = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.warning(f"Error processing {item}: {e}")
                results.append(None)
        
        return results

    def submit(self, func: Callable[..., T], *args, **kwargs) -> Any:
        """提交单个任务"""
        return self.executor.submit(func, *args, **kwargs)

    def shutdown(self, wait: bool = True):
        """关闭执行器"""
        self.executor.shutdown(wait=wait)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()


async def gather_with_limit(
    coros: List[Any],
    max_concurrent: int = 3,
    return_exceptions: bool = False,
) -> List[Any]:
    """带并发限制的 asyncio.gather"""
    semaphore = AsyncSemaphore(max_concurrent)
    
    async def limited_coro(coro):
        async with semaphore.semaphore:
            return await coro
    
    return await asyncio.gather(
        *[limited_coro(coro) for coro in coros],
        return_exceptions=return_exceptions
    )


async def batch_async_tasks(
    tasks: List[Callable[[], Any]],
    max_concurrent: int = 3,
    timeout: Optional[float] = None,
) -> List[Any]:
    """批量执行异步任务（返回结果列表，失败时记录并继续）"""
    semaphore = AsyncSemaphore(max_concurrent)
    results = []

    async def run_task(task_func):
        try:
            async with semaphore.semaphore:
                return await asyncio.wait_for(task_func(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"Task {task_func.__name__} timed out")
            return None
        except Exception as e:
            logger.warning(f"Task {task_func.__name__} failed: {e}")
            return None

    pending = [run_task(task) for task in tasks]
    results = await asyncio.gather(*pending, return_exceptions=False)
    return [r for r in results if r is not None]


def batch_sync_tasks(
    tasks: List[Callable[[], T]],
    max_workers: int = 3,
    timeout: Optional[int] = None,
) -> List[T]:
    """批量执行同步任务（返回结果列表，失败时记录并继续）"""
    results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(task): task for task in tasks}
        
        for future in as_completed(futures, timeout=timeout):
            task = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.warning(f"Task {task.__name__} failed: {e}")
    
    return results
