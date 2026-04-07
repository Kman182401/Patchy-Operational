# Task ID: 9

**Title:** Extract the LLM chat handler

**Status:** done

**Dependencies:** 1 ✓, 3 ✓

**Priority:** low

**Description:** Move Patchy chat methods into patchy_bot/handlers/chat.py: _chat_needs_qbt_snapshot, _build_qbt_snapshot, _patchy_system_prompt, _reply_patchy_chat. Re-enable Patchy chat by removing the hardcoded disable and relying on the patchy_chat_enabled config flag.

**Details:**

The LLM chat system is the smallest domain (~65 lines). It uses PatchyLLMClient to generate responses via an OpenAI-compatible API. The system prompt includes the bot's personality and optional qBT status snapshot. Chat history is maintained per-user in an LRU-bounded dict. Currently marked as a re-enablement target in CLAUDE.md. The _reply_patchy_chat method is the fallback handler in on_text when no other flow or intent matches.

**Test Strategy:**

Add at least 3 unit tests: _chat_needs_qbt_snapshot with various inputs, _patchy_system_prompt returns non-empty string, _build_qbt_snapshot with mock QBClient. Deploy and test: send a free-text message that triggers the chat fallback.
