# AI Router – System Architecture

## 1. Purpose

This document describes the architecture of the AI Router Service.

The system is designed to:

- Route prompts to multiple LLM providers
- Support multiple versions per provider
- Execute in parallel
- Optionally consolidate results
- Track cost, latency, and tokens
- Be config-driven and easily extensible

---

# 2. Architectural Principles

The system follows these principles:

### 2.1 Config Over Hardcoding
Providers and versions are defined in:

```
backend/app/config/providers.json
```

Adding or disabling providers requires no router modification.

---

### 2.2 Separation of Concerns

| Layer | Responsibility |
|--------|---------------|
| Router Layer | Orchestrates execution |
| Provider Layer | Handles external API protocols |
| Config Layer | Defines available providers/versions |
| Service Layer | Logging, ensemble logic |
| Routing Layer | Classifiers, pricing, helpers |

---

### 2.3 Async-First Execution

All provider calls are executed using `asyncio.gather()` to enable:

- Parallel execution
- Lower latency
- Clean scalability

---

# 3. High-Level Architecture

```
Frontend UI
    ↓
API Endpoint
    ↓
call_providers()
    ↓
┌───────────────────────────────────────┐
│ For each (provider, version) pair    │
│                                       │
│     call_single()                    │
│         ↓                            │
│     Resolve config                   │
│         ↓                            │
│     Provider client invocation       │
│         ↓                            │
│     Log invocation                   │
└───────────────────────────────────────┘
    ↓
Optional Ensemble Consolidation
    ↓
FinalResult returned
```

---

# 4. Directory Structure

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
│   ├── logging_service.py
│   └── ensemble_service.py
│
├── routing/
│   ├── deepseek_classifier.py
│   ├── deepseek_pricing.py
│   └── prompt_helpers.py
│
└── db/
    └── models.py
```

---

# 5. Component Breakdown

---

## 5.1 call_providers()

**Location:** `router/call_service.py`

Responsibilities:

- Create router request record
- Normalize messages
- Build provider-version execution tasks
- Execute in parallel
- Aggregate results
- Trigger ensemble if enabled

Key Features:

- Multi-provider support
- Multi-version support
- Async parallel execution
- Clean result aggregation

---

## 5.2 call_single()

Handles a single:

(provider, version)

Responsibilities:

1. Resolve provider version config
2. Validate enabled status
3. Instantiate provider client
4. Execute API call
5. Capture:
   - tokens
   - latency
   - cost
   - success/failure
6. Persist invocation log
7. Return RouterResultItem

This function isolates provider execution logic.

---

## 5.3 Provider Layer

Each provider handles its own protocol.

Example:

```
providers/gemini_provider.py
providers/deepseek_provider.py
```

Responsibilities:

- Build request payload
- Handle HTTP call
- Normalize response
- Return:
  (content, tokens_in, tokens_out)

Providers are swappable and isolated.

---

## 5.4 Config Layer

`providers.json` defines:

- Provider ID
- Display name
- Enabled state
- Versions
- Base URL pattern

Example:

```json
{
  "id": "gemini",
  "enabled": true,
  "versions": [
    {
      "id": "2.0-flash",
      "enabled": true,
      "base_url": "https://..."
    }
  ]
}
```

This allows:

- Add new version without code change
- Disable version instantly
- Future UI-driven configuration

---

## 5.5 Ensemble Service

**Location:** `services/ensemble_service.py`

If consolidation is enabled:

1. Collect base results
2. Build consolidation prompt
3. Call consolidation model
4. Return final merged output

Ensemble is optional and modular.

---

## 5.6 Logging Layer

**Location:** `services/logging_service.py`

Each invocation logs:

- user_id
- session_id
- provider
- model
- tokens_in
- tokens_out
- cost_usd
- latency_ms
- success
- error_code

This enables:

- Observability
- Cost tracking
- Debugging
- Analytics

---

# 6. Execution Flow (Detailed)

## Step 1 – Request Received

Frontend sends:

- messages
- providers
- version hints
- profile
- consolidate config

---

## Step 2 – Router Request Created

Database record created:

```
AiRouterRequest
```

---

## Step 3 – Provider Tasks Built

For each provider and selected version:

```
call_single(...)
```

Tasks collected.

---

## Step 4 – Parallel Execution

```
results = await asyncio.gather(*tasks)
```

All providers execute concurrently.

---

## Step 5 – Aggregation

If:
- Only one result → return directly
- Consolidation disabled → return base result
- Consolidation enabled → run ensemble

---

# 7. Scalability Characteristics

| Feature | Status |
|----------|--------|
| Horizontal scaling | Yes |
| Multi-provider | Yes |
| Multi-version | Yes |
| Async execution | Yes |
| Cost tracking | Yes |
| Extensible | Yes |

---

# 8. Error Handling Strategy

Each provider call:

- Isolated try/except
- Logs error_code
- Does not crash entire router
- Returns structured failure response

Router remains resilient even if one provider fails.

---

# 9. Extensibility Strategy

To add a new provider:

1. Add entry to `providers.json`
2. Create provider client file
3. Add routing branch in call_single (if needed)

To add new version:

1. Add version entry in JSON
2. Done

No router-level structural change required.

---

# 10. Future Evolution Path

Planned improvements:

- Provider adapter registry pattern
- Health-based routing
- Cost-aware routing
- Circuit breaker
- Rate limiting protection
- Caching layer
- A/B testing support
- Observability dashboards

Architecture supports all of the above without rewrite.

---

# 11. Security Considerations

- API keys stored in environment variables
- No API key leakage in logs
- Provider isolation
- Strict message normalization

---

# 12. Summary

The AI Router system provides:

- Config-driven model management
- Version-aware execution
- Parallel provider calls
- Optional ensemble consolidation
- Full logging and cost tracking
- Clean extension strategy

The system is production-ready and designed for long-term scalability.
