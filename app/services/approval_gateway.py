import uuid
import asyncio
import logging

logger = logging.getLogger(__name__)


class ApprovalGateway:
    HIGH_STAKES_OPERATIONS = ["model_pull_gt_20gb", "switch_production_router", "delete_model_from_all_servers", "change_retry_timeout_in_production"]

    def __init__(self):
        self.pending_approvals = {}

    async def require_approval(self, operation: str, context: dict) -> bool:
        if operation not in self.HIGH_STAKES_OPERATIONS:
            return True  # Auto-approve low-risk ops

        approval_id = await self._create_approval_request(operation, context)
        await self._notify_admin(approval_id)

        # BLOCKING: Wait for explicit approval
        approved = await self._wait_for_approval(approval_id, timeout_seconds=300)
        return approved

    async def _create_approval_request(self, operation: str, context: dict) -> str:
        approval_id = str(uuid.uuid4())
        self.pending_approvals[approval_id] = {"operation": operation, "context": context, "event": asyncio.Event(), "approved": False}
        return approval_id

    async def _notify_admin(self, approval_id: str):
        # Placeholder for actual notification logic (e.g., WebSocket, email)
        logger.warning(f"ACTION REQUIRED: Pending approval ID: {approval_id}")

    async def _wait_for_approval(self, approval_id: str, timeout_seconds: int) -> bool:
        if approval_id not in self.pending_approvals:
            return False

        req = self.pending_approvals[approval_id]
        try:
            await asyncio.wait_for(req["event"].wait(), timeout=timeout_seconds)
            return req["approved"]
        except asyncio.TimeoutError:
            logger.error(f"Approval request {approval_id} timed out.")
            return False
        finally:
            if approval_id in self.pending_approvals:
                del self.pending_approvals[approval_id]

    def resolve_approval(self, approval_id: str, approved: bool):
        if approval_id in self.pending_approvals:
            self.pending_approvals[approval_id]["approved"] = approved
            self.pending_approvals[approval_id]["event"].set()
