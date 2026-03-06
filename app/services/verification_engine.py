from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class RoutingResult:
    model_name: str
    server_id: int
    requires_reasoning: bool
    model_capabilities: List[str]
    prompt_tokens: int
    model_context_length: int
    estimated_vram_usage: float
    server_vram_available: float
    server_error_rate: float


@dataclass
class VerificationReport:
    checks: List[Tuple[str, bool, str]]
    passed: bool
    recommendations: List[str]


class VerificationEngine:
    async def verify_routing_decision(self, routing_result: RoutingResult) -> VerificationReport:
        report = VerificationReport(checks=[], passed=True, recommendations=[])

        # Check 1: Model capability match
        if routing_result.requires_reasoning and "reasoning" not in routing_result.model_capabilities:
            report.checks.append(("capability_match", False, "Model lacks reasoning capability"))
            report.passed = False

        # Check 2: Context length sufficiency
        if routing_result.prompt_tokens > routing_result.model_context_length * 0.8:
            report.checks.append(("context_sufficiency", False, "Prompt nears model context limit"))
            report.recommendations.append("Consider model with larger context window")

        # Check 3: VRAM headroom
        if routing_result.estimated_vram_usage > routing_result.server_vram_available * 0.9:
            report.checks.append(("vram_headroom", False, "Insufficient VRAM headroom"))
            report.passed = False

        # Check 4: Server health
        if routing_result.server_error_rate > 0.1:
            report.checks.append(("server_health", False, "Elevated server error rate"))
            report.recommendations.append("Consider alternative server")

        return report
