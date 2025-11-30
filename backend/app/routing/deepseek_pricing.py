# backend/app/routing/deepseek_pricing.py

DEEPSEEK_PRICING = {
    "deepseek-chat": {
        "input_per_million": 0.27,
        "output_per_million": 1.10,
    },
    "deepseek-v3": {
        "input_per_million": 0.27,
        "output_per_million": 1.10,
    },
    "deepseek-r1": {
        "input_per_million": 0.55,
        "output_per_million": 2.19,
    },
}

def estimate_deepseek_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    cfg = DEEPSEEK_PRICING.get(model)
    if not cfg:
        return 0.0
    cost_in = (input_tokens / 1_000_000) * cfg["input_per_million"]
    cost_out = (output_tokens / 1_000_000) * cfg["output_per_million"]
    return round(cost_in + cost_out, 6)
