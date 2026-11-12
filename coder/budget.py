"""Budget and token telemetry for LLM API calls.

Enforces strict financial guards to guarantee total run spend remains well under
the US$1.00 cap mandated in BRIEF.md.
"""

import threading

# Default model pricing (USD per 1M tokens)
# gpt-4o-mini: $0.15 input / $0.60 output
GPT_4O_MINI_INPUT_PER_M = 0.15
GPT_4O_MINI_OUTPUT_PER_M = 0.60

# Hard limit: stop LLM calls once spent >= $0.80 (20% safety margin below $1.00)
BUDGET_HARD_STOP_USD = 0.80


class BudgetTracker:
    def __init__(self, max_budget_usd: float = BUDGET_HARD_STOP_USD):
        self.max_budget_usd = max_budget_usd
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cost_usd = 0.0
        self.call_count = 0
        self._lock = threading.Lock()

    def record_usage(self, prompt_tokens: int, completion_tokens: int, model: str = "gpt-4o-mini") -> float:
        with self._lock:
            self.total_prompt_tokens += prompt_tokens
            self.total_completion_tokens += completion_tokens
            self.call_count += 1

            # Calculate cost
            cost = (
                (prompt_tokens / 1_000_000.0) * GPT_4O_MINI_INPUT_PER_M
                + (completion_tokens / 1_000_000.0) * GPT_4O_MINI_OUTPUT_PER_M
            )
            self.total_cost_usd += cost
            return self.total_cost_usd

    def can_call(self) -> bool:
        with self._lock:
            # Leave safety buffer for one more call (~$0.001)
            return self.total_cost_usd < (self.max_budget_usd - 0.005)

    def summary(self) -> dict:
        with self._lock:
            return {
                "calls": self.call_count,
                "prompt_tokens": self.total_prompt_tokens,
                "completion_tokens": self.total_completion_tokens,
                "total_tokens": self.total_prompt_tokens + self.total_completion_tokens,
                "cost_usd": round(self.total_cost_usd, 6),
                "budget_cap_usd": self.max_budget_usd,
                "within_budget": self.total_cost_usd <= self.max_budget_usd,
            }


# Global shared instance
GLOBAL_BUDGET = BudgetTracker()
