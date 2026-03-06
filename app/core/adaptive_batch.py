import time
import asyncio
from typing import Callable, List, Any


class AdaptiveBatcher:
    def __init__(self, target_latency_ms: float = 5.0):
        self.target_latency = target_latency_ms / 1000
        self.current_batch_size = 10
        self.queue: asyncio.Queue = asyncio.Queue()

    async def run(self, processor: Callable):
        while True:
            start = time.time()
            batch = await self._collect_batch()
            if batch:
                await processor(batch)
                # Adjust batch size based on latency
                elapsed = time.time() - start
                if elapsed > self.target_latency:
                    self.current_batch_size = max(10, int(self.current_batch_size * 0.9))
                else:
                    self.current_batch_size = min(1000, int(self.current_batch_size * 1.1))
            else:
                await asyncio.sleep(0.01)

    async def _collect_batch(self) -> List[Any]:
        batch = []
        try:
            # Wait for first item
            item = await asyncio.wait_for(self.queue.get(), timeout=0.1)
            batch.append(item)
            self.queue.task_done()

            # Grab remaining items up to current_batch_size without waiting
            while len(batch) < self.current_batch_size:
                try:
                    item = self.queue.get_nowait()
                    batch.append(item)
                    self.queue.task_done()
                except asyncio.QueueEmpty:
                    break
        except asyncio.TimeoutError:
            pass
        return batch
