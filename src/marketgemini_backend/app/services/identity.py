# Maps IdP claims -> your local user. JIT-provisions if first time.
from .db import db

def _provider_from_iss(iss: str) -> str:
    if "accounts.google.com" in iss:
        return "google"
    if "appleid.apple.com" in iss:
        return "apple"
    return "unknown"

def map_idp_claims_to_user(dbh, claims: dict):
    """
    Returns a local user dict {id, email,...}. Creates it if not found.
    Uses a stable synthetic id: "<provider>:<sub>" (good enough for tests/dev).
    """
    iss = claims["iss"]
    sub = claims["sub"]
    email = claims.get("email")

    provider = _provider_from_iss(iss)
    user_id = f"{provider}:{sub}"

    users = dbh["users"]
    if user_id not in users:
        users[user_id] = {"id": user_id, "email": email}
    else:
        # optional profile refresh
        if email:
            users[user_id]["email"] = email
    return users[user_id]
