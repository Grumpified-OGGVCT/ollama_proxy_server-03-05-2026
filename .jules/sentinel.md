YYYY-MM-DD - 2026-03-06
Title: Model Pull Denial of Service
Context: Users could request large models to be pulled from servers, resulting in disk/network DoS.
Learning: Lacking validation on model pull sizes exposes an attack surface for disk and bandwidth exhaustion.
Fix Applied: Added `max_pull_size_gb` settings limitation configuration for the app.
Residual Risk: The proxy blocks normal user pull requests by default, but admin operations need sizing limits.
Prevention: Implement size guardrails on all operations downloading from the internet.
