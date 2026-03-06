from typing import List, Tuple, Callable
import logging

logger = logging.getLogger(__name__)


class PhaseRollbackManager:
    def __init__(self):
        self.rollback_stack: List[Tuple[str, Callable]] = []

    async def register_rollback(self, phase_name: str, rollback_fn: Callable):
        self.rollback_stack.append((phase_name, rollback_fn))

    async def execute_rollbacks(self, failed_phase: str):
        while self.rollback_stack:
            phase_name, rollback_fn = self.rollback_stack.pop()
            if phase_name == failed_phase:
                break
            try:
                await rollback_fn()
            except Exception as e:
                logger.error(f"Rollback failed for {phase_name}: {e}")
