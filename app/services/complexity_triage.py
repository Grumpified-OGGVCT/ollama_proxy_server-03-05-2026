import re
import random


class ComplexityScorer:
    def __init__(self):
        self.heuristics = {"simple": r"^(summarize|fix typo|explain|what is)\b", "complex": r"(prove|theorem|derive|architect|design pattern)"}

    async def score(self, prompt: str) -> int:
        """Returns 1-10 complexity score."""
        if re.search(self.heuristics["simple"], prompt, re.I):
            return random.randint(1, 3)
        elif re.search(self.heuristics["complex"], prompt, re.I):
            return random.randint(8, 10)
        return 5  # Default balanced
