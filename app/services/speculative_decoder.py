from dataclasses import dataclass
from typing import Optional


@dataclass
class RoutingDecision:
    model: str
    draft_model: Optional[str] = None
    params: Optional[dict] = None


class SpeculativeDecoder:
    async def route_with_draft(self, target_model: str, server: dict) -> RoutingDecision:
        """Check for co-resident draft model."""
        draft_model = self._find_compatible_draft(target_model, server)
        if draft_model:
            return RoutingDecision(model=target_model, draft_model=draft_model, params={"draft": draft_model})
        return RoutingDecision(model=target_model)

    def _find_compatible_draft(self, target_model: str, server: dict) -> Optional[str]:
        # Example logic: if model is llama3:70b, look for llama3:8b as draft
        if "70b" in target_model.lower():
            draft_name = target_model.lower().replace("70b", "8b")
            available_models = server.get("available_models", [])
            for m in available_models:
                if isinstance(m, dict) and draft_name in m.get("name", "").lower():
                    return m["name"]
        return None
