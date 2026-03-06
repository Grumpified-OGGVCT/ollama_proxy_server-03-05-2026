YYYY-MM-DD - 2026-03-06
Title: Reasoning model capability routing
Context: 2026 LLM models (e.g. DeepSeek R1) need routing based on prompt reasoning needs.
Learning: Users typing complex logic prompts might be routed to basic chat models without reasoning capabilities.
Design System Impact: Adding complex reasoning capability parsing allows the router to optimize response logic dynamically.
Action: Added reasoning token detection logic ("thought", "cot", "r1") in catalog capabilities.
