"""待抓取队列。三种策略共用同一套去重集合，只在出队规则上不同。"""

import collections
import heapq
import itertools
from dataclasses import dataclass


@dataclass(slots=True)
class Task:
    url: str
    depth: int = 0
    parent: str | None = None
    anchor: str = ""        # 锚文本，最佳优先算相关性要用
    priority: float = 0.0


class Frontier:
    """只由调度线程使用，所以不加锁。"""

    STRATEGIES = ("bfs", "dfs", "best")

    def __init__(self, strategy: str = "bfs"):
        if strategy not in self.STRATEGIES:
            raise ValueError(f"未知策略: {strategy}")
        self.strategy = strategy
        self.dup = 0
        self._deque = collections.deque()
        self._heap: list[tuple[float, int, Task]] = []
        self._seq = itertools.count()
        self._seen: set[str] = set()

    def push(self, task: Task) -> bool:
        """入队。URL 已见过则返回 False，并给 dup 计数。"""
        if task.url in self._seen:
            self.dup += 1
            return False
        self._seen.add(task.url)
        if self.strategy == "best":
            # 堆里存 (-优先级, 序号, 任务)，序号保证同分时先来先出
            heapq.heappush(self._heap, (-task.priority, next(self._seq), task))
        else:
            self._deque.append(task)
        return True

    def pop(self) -> Task | None:
        if self.strategy == "best":
            return heapq.heappop(self._heap)[2] if self._heap else None
        if not self._deque:
            return None
        return self._deque.popleft() if self.strategy == "bfs" else self._deque.pop()

    def __len__(self) -> int:
        return len(self._heap) if self.strategy == "best" else len(self._deque)

    @property
    def seen_count(self) -> int:
        return len(self._seen)
