# AI Router Service

A config-driven, multi-provider LLM routing engine that supports:

- Multiple providers (Gemini, DeepSeek, future-ready)
- Multiple versions per provider
- Parallel execution
- Optional ensemble consolidation
- Version-aware routing
- Per-call logging and cost tracking
- Clean extension path for new providers

---

# 🚀 Overview

This service routes user prompts to one or more LLM providers and optionally consolidates results.

It is designed to be:

- Config-driven
- Extensible
- Production-ready
- Debuggable
- Version-aware

---

# 🧠 Core Capabilities

## ✅ Config-Driven Providers

Providers and versions are defined in:

```
backend/app/config/providers.json
```

No router changes required to:

- Add new version
- Disable version
- Disable provider

---

## ✅ Version-Aware Routing

Each provider can have multiple versions:

Example:

```json
{
  "id": "gemini",
  "versions": [
    {
      "id": "2.0-flash",
      "enabled": true
    },
    {
      "id": "2.5-mini",
      "enabled": true
    }
  ]
}
```

Routing resolves:

- Provider ID
- Version ID
- Base URL
- Model ID
- Enabled state

---

## ✅ Multi-Version Execution

UI can select:

- Multiple providers
- Multiple versions per provider

Example:

- Gemini 2.0 Flash
- Gemini 2.5 Mini
- DeepSeek Chat

All will execute in parallel.

---

## ✅ Parallel Execution

`asyncio.gather()` is used inside `call_providers()` to execute:

- Multiple providers
- Multiple versions

Simultaneously.

This ensures:

- Lower latency
- Fair comparison
- Scalable architecture

---

## ✅ Optional Ensemble

If consolidation is enabled:

1. Base results are collected
2. Consolidation model is selected
3. Ensemble service merges results

Location:

```
backend/app/services/ensemble_service.py
```

---

# 🏗 System Architecture

High-Level Flow:

```
Frontend UI
    ↓
Router (call_providers)
    ↓
call_single
    ↓
Provider Config Resolution
    ↓
Provider Adapter
    ↓
External LLM API
```

---

# 📁 Project Structure

```
backend/app/
│
├── router/
│   └── call_service.py
│
├── config/
│   ├── providers.json
│   └── providers_loader.py
│
├── providers/
│   ├── gemini_provider.py
│   └── deepseek_provider.py
│
├── services/
│   ├── ensemble_service.py
│   └── logging_service.py
│
├── routing/
│   ├── deepseek_classifier.py
│   └── deepseek_pricing.py
```

---

# ⚙️ How Routing Works

## Step 1 — UI Sends Request

User selects:

- Providers
- Versions
- Profile
- Consolidation mode

---

## Step 2 — call_providers()

- Creates router request record
- Normalizes messages
- Builds execution tasks
- Runs providers in parallel

---

## Step 3 — call_single()

For each provider-version pair:

1. Resolve config from providers.json
2. Validate enabled status
3. Instantiate provider client
4. Execute API call
5. Capture:
   - tokens_in
   - tokens_out
   - cost
   - latency
   - confidence
6. Persist invocation log

---

## Step 4 — Optional Consolidation

If enabled:

- Ensemble service merges base results
- Returns final result

---

# 🔧 Adding a New Provider

## Step 1 — Update providers.json

Add:

```json
{
  "id": "newprovider",
  "name": "New Provider",
  "enabled": true,
  "versions": [
    {
      "id": "v1",
      "name": "Version 1",
      "enabled": true,
      "base_url": "https://api.provider.com/v1/..."
    }
  ]
}
```

## Step 2 — Implement Provider Client (if protocol differs)

Create:

```
backend/app/providers/newprovider_provider.py
```

If API follows standard OpenAI format, no additional logic required.

---

# 🔒 Disabling a Provider

Set in JSON:

```json
"enabled": false
```

No code changes required.

---

# 💰 Cost Tracking

Each provider call tracks:

- Prompt tokens
- Completion tokens
- Estimated cost (USD)

DeepSeek pricing logic located in:

```
backend/app/routing/deepseek_pricing.py
```

---

# 📊 Logging

Every invocation logs:

- user_id
- session_id
- provider
- version
- tokens
- latency
- cost
- success / error

Handled in:

```
backend/app/services/logging_service.py
```

---

# 📈 Current System Status

You now have:

- Config-driven models
- Version-aware routing
- Multi-version support
- Parallel execution
- Clean future extension path
- Consolidation-ready architecture
- Cost tracking
- Logging pipeline

This is production-grade routing architecture.

---

# 🛣 Roadmap

Planned Enhancements:

- Per-version routing metadata
- Health-based failover
- Cost-aware smart routing
- A/B testing framework
- Caching layer
- Rate-limit protection
- Circuit breaker

---

# 🧩 Design Philosophy

This system follows:

- Separation of concerns
- Config over hardcoding
- Extensible provider design
- Async-first architecture
- Observability-first logging

---

# 🏁 Conclusion

AI Router Service is a flexible, scalable LLM routing engine designed for:

- Model comparison
- Multi-provider orchestration
- Production environments
- Enterprise-ready extensibility

It is built to evolve without architectural rewrites.
