import logging

logger = logging.getLogger(__name__)


class TokenCostTracker:
    # Cost per 1K tokens (input/output) by model tier
    COST_TABLE = {
        "nano": {"input": 0.0001, "output": 0.0002},
        "fast": {"input": 0.0005, "output": 0.0015},
        "balanced": {"input": 0.002, "output": 0.006},
        "deep": {"input": 0.005, "output": 0.015},
        "reasoning": {"input": 0.008, "output": 0.024},  # 3x premium for CoT
    }

    def __init__(self, default_budget_usd: float = 100.0):
        self.default_budget_usd = default_budget_usd
        self.user_budgets = {}  # user_id -> remaining_budget

    async def track_request(self, model_tier: str, input_tokens: int, output_tokens: int, user_id: str, request_id: str) -> float:
        tier_costs = self.COST_TABLE.get(model_tier, self.COST_TABLE["balanced"])

        cost = (input_tokens * tier_costs["input"] + output_tokens * tier_costs["output"]) / 1000

        # Update user budget
        await self._deduct_budget(user_id, cost)

        # Emit metric
        await self._emit_cost_metric(model_tier=model_tier, cost_usd=cost, request_id=request_id)

        return cost

    async def check_budget(self, user_id: str, estimated_tokens: int) -> bool:
        """Pre-flight budget check"""
        remaining = await self._get_remaining_budget(user_id)
        estimated_cost = (estimated_tokens * 0.01) / 1000  # Conservative estimate
        return remaining >= estimated_cost

    async def _deduct_budget(self, user_id: str, cost: float):
        if user_id not in self.user_budgets:
            self.user_budgets[user_id] = self.default_budget_usd
        self.user_budgets[user_id] -= cost

    async def _get_remaining_budget(self, user_id: str) -> float:
        if user_id not in self.user_budgets:
            self.user_budgets[user_id] = self.default_budget_usd
        return self.user_budgets[user_id]

    async def _emit_cost_metric(self, model_tier: str, cost_usd: float, request_id: str):
        # Placeholder for actual metrics logic (e.g., OpenTelemetry, statsd)
        logger.info(f"Cost recorded for {request_id}: ${cost_usd:.4f} (tier: {model_tier})")
