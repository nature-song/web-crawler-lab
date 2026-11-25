"""待抓取队列。

三种爬取策略的差别只有"下一个抓谁"：
  - bfs：先进先出，一层抓完再下一层，覆盖均匀，最不容易跑偏；
  - dfs：后进先出，顺着一条链一路往下钻，容易陷进日历/分页这类"深井"；
  - best：按 priority 从堆里取最大的，可以先抓"看起来最相关"的页面。

三者共用同一个 _seen 集合，所以"换策略"只影响顺序，不影响去重结果。
"""

import collections
import heapq
import itertools

from .models import Task

__all__ = ["Frontier", "Task"]


class Frontier:
    """只由调度线程使用，所以内部不加锁；多线程同时 push 会出问题。"""

    STRATEGIES = ("bfs", "dfs", "best")

    def __init__(self, strategy: str = "bfs"):
        if strategy not in self.STRATEGIES:
            raise ValueError(f"未知策略: {strategy}")
        self.strategy = strategy
        self.dup = 0                     # 被去重挡下的次数，界面要显示
        self._deque = collections.deque()   # bfs 和 dfs 共用一个双端队列
        self._heap: list[tuple[float, int, Task]] = []
        self._seq = itertools.count()
        self._seen: set[str] = set()

    def push(self, task: Task) -> bool:
        """入队。URL 已经见过则返回 False，并给 dup 加一。"""
        if task.url in self._seen:
            self.dup += 1
            return False
        self._seen.add(task.url)

        if self.strategy == "best":
            # 堆里存 (-优先级, 序号, 任务)：取负号让"分高的"先出；
            # 序号保证分数相同时不会去比较 Task 对象（那样会直接报错）
            heapq.heappush(self._heap, (-task.priority, next(self._seq), task))
        else:
            self._deque.append(task)
        return True

    def pop(self) -> Task | None:
        """取下一个任务。队列空了返回 None，不抛异常。"""
        if self.strategy == "best":
            return heapq.heappop(self._heap)[2] if self._heap else None
        if not self._deque:
            return None
        return self._deque.popleft() if self.strategy == "bfs" else self._deque.pop()

    def __len__(self) -> int:
        """队列里还剩多少个待抓任务。"""
        return len(self._heap) if self.strategy == "best" else len(self._deque)

    @property
    def seen_count(self) -> int:
        """累计见过多少不同的 URL（含已抓完的）。"""
        return len(self._seen)
