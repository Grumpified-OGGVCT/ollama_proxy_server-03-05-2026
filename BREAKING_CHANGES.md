# Notice of Potential Breaking Changes

The `ollama-proxy-server` utilizes robust dynamic mechanisms for upgrades, but developers integrating against this proxy should be aware of a few structural design choices and non-breaking features that might alter expectations.

## 1. The `<tool_call>` Parsing Mechanism

**Context:**
As part of extending the real-time feedback UI of the proxy, we have integrated a custom mechanism to observe and debug "tool calls" originating from agentic interactions traversing the proxy streams (especially useful for vLLM architectures translating into Ollama formats).

In `app/core/vllm_translator.py`, when a model invokes a tool call, we parse the function and inject a pseudo-XML tag `\n<tool_call>\n{function_name}({arguments})\n</tool_call>\n` into the `content` field of the event stream chunks.

**Pros:**
- **Developer Transparency:** It immediately makes agentic loops and external tool connections visually apparent in the Chat Playground UI.
- **Unified Standard:** It piggy-backs on the now common `<think>` structural paradigm natively present in reasoning models like `DeepSeek-R1` or `Qwen2-Max`.

**Cons / Potential Breakage:**
- **Parsing Hazards:** If your client relies on strict payload lengths or explicitly breaks if it encounters `<tool_call>` XML block markers inside an otherwise raw `content` stream, you will need to adjust your client-side parsers to strip these UI-focused debugging tags before rendering.
- **Not a standard OpenAI protocol spec:** While standard `tool_calls` arrays are preserved and processed natively over JSON endpoints, the injected `content` additions are a custom quality-of-life extension for standard chat clients that do not parse arrays natively.

## 2. Dynamic Auto-Routing

**Context:**
The admin UI now allows selecting the "Auto (Best Available Model)" router in the Playground UI (internally mapped to `"model": "auto"`).

**Pros:**
- Automatically falls back to Vision models if an image is attached.
- Will route to Coding models if code structures are detected in the prompt.
- Fails over dynamically without user intervention.

**Cons / Potential Breakage:**
- When selecting "Auto", the request logs may reflect a different model name being executed than what was strictly supplied in the request body (`"model": "auto"` -> logs `model: "llava"`). Scripts matching explicit string metrics from usage dashboards might encounter discrepancies if they don't dynamically check the final routed `model` field.

## 3. Database Settings Migration

**Context:**
Rate limit boundaries (`rate_limit_requests`, `rate_limit_window_minutes`) and retry logic configurations have been elevated into the `app_settings` database constraints, allowing dynamic modification via the UI.

- No action is needed for current server owners. The `app/database/migrations.py` auto-migration mechanism will automatically patch your SQLite database with default fallback properties on start up.
