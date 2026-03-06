YYYY-MM-DD - 2026-03-06
Title: Model Pull Denial of Service
Context: Users could request large models to be pulled from servers, resulting in disk/network DoS.
Learning: Lacking validation on model pull sizes exposes an attack surface for disk and bandwidth exhaustion.
Fix Applied: Added `max_pull_size_gb` settings limitation configuration for the app.
Residual Risk: The proxy blocks normal user pull requests by default, but admin operations need sizing limits.
Prevention: Implement size guardrails on all operations downloading from the internet.

YYYY-MM-DD - 2026-03-06
Title: HITL and Phase Rollbacks
Context: Automated proxy models require gates to protect state logic and expensive actions.
Learning: Unrestricted proxy configurations allow system states to silently fail or cascade errors.
Fix Applied: Added blocking HITL approval gates and phase-locked rollback execution.
Residual Risk: Depends on human response times.
Prevention: Implement hard timeouts and automated fallback triggers.
