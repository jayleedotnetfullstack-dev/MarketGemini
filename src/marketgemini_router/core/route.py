import random
from .config import CFG

# internal provider scores (simple bandit placeholder)
_provider_scores = {}

# Prepopulate scores
for name, prov in CFG.get("providers", {}).items():
    if prov.get("enabled", False):
        _provider_scores[name] = 1.0

def pick_provider(profile):
    """Simple epsilon-greedy routing based on cost and score."""
    providers = {
        k: v for k, v in CFG.get("providers", {}).items() if v.get("enabled", False)
    }
    if not providers:
        raise RuntimeError("No providers enabled in router.yml")

    epsilon = CFG.get("routing", {}).get("epsilon", 0.1)
    if random.random() < epsilon:
        return random.choice(list(providers.keys()))

    # exploit
    best = None
    best_value = -1
    for name, prov in providers.items():
        score = _provider_scores.get(name, 1.0)
        cin = prov.get("cost_in", 1.0)
        cout = prov.get("cost_out", 1.0)
        price = (cin + cout) / 2.0
        value = score / price
        if value > best_value:
            best_value = value
            best = name
    return best
