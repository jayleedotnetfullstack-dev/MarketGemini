# backend/app/config/providers_loader.py

import json
import os
from typing import Dict, Any

# Cache so we only load once
_PROVIDERS_CACHE: Dict[str, Any] | None = None


class ProviderConfigError(RuntimeError):
    pass


def _load_raw_config() -> dict:
    base_dir = os.path.dirname(__file__)
    config_path = os.path.join(base_dir, "providers.json")

    if not os.path.exists(config_path):
        raise ProviderConfigError(f"providers.json not found at {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_providers_config(force_reload: bool = False) -> Dict[str, Any]:
    """
    Load and normalize providers.json

    Returns:
        {
          "gemini": {
              "name": "...",
              "versions": {
                  "2.0-flash": { ... },
                  "2.5-mini": { ... }
              }
          },
          "deepseek": {
              "name": "...",
              "versions": {
                  "chat": { ... },
                  "v3": { ... }
              }
          }
        }
    """
    global _PROVIDERS_CACHE

    if _PROVIDERS_CACHE is not None and not force_reload:
        return _PROVIDERS_CACHE

    raw = _load_raw_config()

    if "providers" not in raw or not isinstance(raw["providers"], list):
        raise ProviderConfigError("providers.json must contain a 'providers' list")

    providers: Dict[str, Any] = {}

    for p in raw["providers"]:
        provider_id = p.get("id")
        if not provider_id:
            raise ProviderConfigError("Provider missing 'id'")

        if not p.get("enabled", False):
            continue  # provider disabled

        versions_cfg = p.get("versions", [])
        if not isinstance(versions_cfg, list):
            raise ProviderConfigError(f"Provider '{provider_id}' versions must be a list")

        versions: Dict[str, Any] = {}

        for v in versions_cfg:
            version_id = v.get("id")
            if not version_id:
                raise ProviderConfigError(f"Provider '{provider_id}' version missing 'id'")

            if not v.get("enabled", False):
                continue  # version disabled

            versions[version_id] = {
                "id": version_id,
                "name": v.get("name", version_id),
                "base_url": v.get("base_url"),
            }

        if not versions:
            continue  # provider has no enabled versions

        providers[provider_id] = {
            "id": provider_id,
            "name": p.get("name", provider_id),
            "versions": versions,
        }

    if not providers:
        raise ProviderConfigError("No enabled providers found in providers.json")

    _PROVIDERS_CACHE = providers
    return providers


def get_provider_version(
    provider_id: str,
    version_id: str,
) -> Dict[str, Any]:
    """
    Lookup a specific provider + version.
    """
    providers = load_providers_config()

    if provider_id not in providers:
        raise ProviderConfigError(f"Provider '{provider_id}' not found or disabled")

    provider = providers[provider_id]
    versions = provider["versions"]

    if version_id not in versions:
        raise ProviderConfigError(
            f"Version '{version_id}' not found for provider '{provider_id}'"
        )

    return versions[version_id]
