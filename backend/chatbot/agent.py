"""
backend/chatbot/agent.py
─────────────────────────
ReAct-pattern agent that drives the diet chatbot using Ollama.

Architecture (§4 of project brief)
────────────────────────────────────
  1. User message arrives.
  2. BEFORE calling Ollama, run regex escalation check against
     ESCALATION_PATTERNS — if matched, return fixed escalation
     response immediately (never touches the LLM).
  3. Build messages list: system prompt + conversation history +
     current user message.
  4. POST to Ollama /api/chat with the llama3.2:3b model.
  5. Parse the response for <tool_call>…</tool_call> JSON blocks.
  6. Execute each tool call via TOOL_REGISTRY and append the
     result as a tool message.
  7. Repeat steps 4–6 up to MAX_STEPS times.
  8. Log the turn via log_interaction tool.
  9. Return the final assistant message.

Model: llama3.2:3b (configurable via OLLAMA_MODEL env var).
Transport: httpx (already in requirements-backend.txt).

Why no streaming: the REST endpoint returns a complete reply;
streaming is a nice-to-have for the demo UI but adds complexity
without changing evaluation outcomes.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from backend.chatbot.system_prompt import (
    ESCALATION_PATTERNS,
    ESCALATION_RESPONSE,
    SYSTEM_PROMPT,
)
from backend.chatbot.tools import TOOL_REGISTRY

log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL",    "llama3.2:3b")
MAX_STEPS       = 6          # max reasoning iterations before forced reply
TIMEOUT_S       = 120        # seconds — 3B model on CPU can be slow


# ──────────────────────────────────────────────────────────────────────────────
# Escalation check (pre-LLM)
# ──────────────────────────────────────────────────────────────────────────────

_COMPILED_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in ESCALATION_PATTERNS
]


def _is_escalation_required(text: str) -> bool:
    """Return True if the message matches any hard-escalation pattern."""
    for pattern in _COMPILED_PATTERNS:
        if pattern.search(text):
            return True
    return False


# ──────────────────────────────────────────────────────────────────────────────
# Tool-call parsing
# ──────────────────────────────────────────────────────────────────────────────

_TOOL_CALL_RE = re.compile(
    r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL
)
_XML_TOOL_RE = re.compile(
    r"<(?P<name>get_risk_profile|get_diet_plan|search_food_kb|log_meal)\b"
    r"(?P<attributes>[^>]*?)(?:/>|>(?P<body>.*?)</(?P=name)>)",
    re.IGNORECASE | re.DOTALL,
)
_XML_ATTRIBUTE_RE = re.compile(r"(?P<key>[A-Za-z_]+)=(?:\"(?P<double>[^\"]*)\"|'(?P<single>[^']*)')")


def _parse_tool_calls(text: str) -> List[Dict[str, Any]]:
    """
    Extract all <tool_call>{…}</tool_call> JSON blocks from an LLM response.
    Returns a list of dicts with keys: name, arguments (dict).
    """
    calls = []
    for match in _TOOL_CALL_RE.finditer(text):
        raw = match.group(1)
        try:
            obj = json.loads(raw)
            calls.append({
                "name":      obj.get("name", ""),
                "arguments": obj.get("arguments", {}),
            })
        except json.JSONDecodeError as exc:
            log.warning("Failed to parse tool call JSON: %s — raw: %s", exc, raw)

    # llama3.2 commonly emits function calls as XML-like tags even when the
    # prompt requests the JSON wrapper. Accept that format at the boundary.
    for match in _XML_TOOL_RE.finditer(text):
        arguments: Dict[str, Any] = {}
        for attribute in _XML_ATTRIBUTE_RE.finditer(match.group("attributes")):
            value = attribute.group("double") or attribute.group("single") or ""
            if value.startswith(("[", "{")):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass
            arguments[attribute.group("key")] = value
        calls.append({"name": match.group("name"), "arguments": arguments})
    return calls


def _strip_tool_calls(text: str) -> str:
    """Remove all <tool_call> blocks from the text so the user sees clean prose."""
    cleaned = _TOOL_CALL_RE.sub("", text)
    return _XML_TOOL_RE.sub("", cleaned).strip()


def _required_tool_for_message(message: str) -> Optional[str]:
    """Infer the mandatory grounding tool for common user intents."""
    lowered = message.lower()
    if any(token in lowered for token in ("log this", "log that", "log my", "had ")):
        return "log_meal"
    if any(token in lowered for token in ("risk", "risk score", "risk level", "risk factor")):
        return "get_risk_profile"
    if any(token in lowered for token in ("diet plan", "calorie", "sodium limit", "potassium limit")):
        return "get_diet_plan"
    if any(token in lowered for token in ("food", "foods", "meal", "snack", "vegetarian", "dairy", "gluten", "fruit")):
        return "search_food_kb"
    return None


def _fallback_tool_arguments(tool_name: str, message: str, disease: Optional[str]) -> Dict[str, Any]:
    if tool_name == "get_risk_profile":
        return {"disease": disease or "general"}
    if tool_name == "get_diet_plan":
        return {}
    if tool_name == "log_meal":
        portion_match = re.search(r"(\d+(?:\.\d+)?)\s*g", message, re.IGNORECASE)
        food_match = re.search(r"(?:of|had)\s+(.+?)(?:\s+for\s+|\s+can you|\s+please|\?|$)", message, re.IGNORECASE)
        return {
            "food_name": (food_match.group(1).strip() if food_match else message),
            "portion_g": float(portion_match.group(1)) if portion_match else 100.0,
        }
    return {"query": message, "exclude": None, "disease": disease or "general"}


# ──────────────────────────────────────────────────────────────────────────────
# Ollama HTTP client
# ──────────────────────────────────────────────────────────────────────────────

def _ollama_chat(messages: List[Dict[str, str]]) -> str:
    """
    Call Ollama /api/chat and return the assistant content string.
    Raises httpx.HTTPStatusError on non-2xx responses.
    """
    payload = {
        "model":    OLLAMA_MODEL,
        "messages": messages,
        "stream":   False,
        "options":  {
            "temperature": 0.2,    # low temp → less hallucination
            "top_p":       0.9,
        },
    }

    with httpx.Client(timeout=TIMEOUT_S) as client:
        resp = client.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
        )
        resp.raise_for_status()

    data    = resp.json()
    content = data.get("message", {}).get("content", "")
    return content


# ──────────────────────────────────────────────────────────────────────────────
# Tool execution
# ──────────────────────────────────────────────────────────────────────────────

def _execute_tool(
    name: str,
    arguments: Dict[str, Any],
    user_id: str,
    disease: Optional[str],
) -> str:
    """Call a tool from TOOL_REGISTRY and return its JSON result as a string."""
    if name not in TOOL_REGISTRY:
        return json.dumps({"error": f"Unknown tool: '{name}'"})

    # The model should choose the food/query arguments, while request identity
    # stays under application control and cannot be omitted or changed.
    tool_arguments = dict(arguments)
    for key, value in list(tool_arguments.items()):
        if isinstance(value, str) and value.strip().lower() in {"null", "none"}:
            tool_arguments[key] = None
    if name in {"get_risk_profile", "log_meal", "log_interaction"}:
        tool_arguments["user_id"] = user_id
    if name in {"get_risk_profile", "search_food_kb", "log_interaction"}:
        tool_arguments["disease"] = disease or "general"

    try:
        result = TOOL_REGISTRY[name](**tool_arguments)
    except TypeError as exc:
        result = {"error": f"Invalid arguments for tool '{name}': {exc}"}
    except Exception as exc:
        log.exception("Tool '%s' raised an unexpected error", name)
        result = {"error": f"Tool '{name}' failed: {exc}"}

    return json.dumps(result, ensure_ascii=False, default=str)


# ──────────────────────────────────────────────────────────────────────────────
# Main agent function
# ──────────────────────────────────────────────────────────────────────────────

def run_agent(
    user_id: str,
    message: str,
    disease: Optional[str] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Run one agent turn and return a structured response dict.

    Parameters
    ----------
    user_id              : str   — identifies the user in the DB
    message              : str   — the current user message
    disease              : str   — 'ckd' | 'hypertension' | 'diabetes' | None
    conversation_history : list  — prior [{role, content}] turns (optional)

    Returns
    -------
    {
        reply          : str   — text to show the user
        tool_calls_made: list  — names of tools called this turn
        escalated      : bool  — True if hard escalation was triggered
        latency_ms     : float — wall-clock time for this turn
        steps          : int   — reasoning iterations used
    }
    """
    t_start = time.perf_counter()

    # ── 1. Pre-LLM escalation check ────────────────────────────────────────
    if _is_escalation_required(message):
        log.info("[agent] escalation triggered for user=%s  msg='%s'", user_id, message[:80])
        latency_ms = (time.perf_counter() - t_start) * 1000
        # Still log the interaction for audit
        TOOL_REGISTRY["log_interaction"](
            user_id=user_id,
            turn_summary=f"ESCALATED: {message[:200]}",
            disease=disease or "general",
        )
        return {
            "reply":           ESCALATION_RESPONSE,
            "tool_calls_made": [],
            "escalated":       True,
            "latency_ms":      round(latency_ms, 1),
            "steps":           0,
        }

    # ── 2. Build message history ────────────────────────────────────────────
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]

    if conversation_history:
        # Trim to last 10 turns to keep context within model window
        messages.extend(conversation_history[-10:])

    messages.append({"role": "user", "content": message})

    # ── 3. ReAct loop ──────────────────────────────────────────────────────
    tool_calls_made: List[str] = []
    executed_call_keys: set[tuple[str, str]] = set()
    steps = 0
    final_reply = ""

    for step in range(MAX_STEPS):
        steps = step + 1
        try:
            assistant_content = _ollama_chat(messages)
        except httpx.ConnectError:
            log.error("Cannot connect to Ollama at %s", OLLAMA_BASE_URL)
            final_reply = (
                "I'm unable to process your request right now (model service unavailable). "
                "Please try again in a moment."
            )
            break
        except httpx.HTTPStatusError as exc:
            log.error("Ollama returned HTTP %s", exc.response.status_code)
            final_reply = "I encountered an error processing your request.  Please try again."
            break

        log.debug("[agent step=%d] raw response: %s", step, assistant_content[:200])

        # Parse any tool calls in this response
        calls = _parse_tool_calls(assistant_content)

        if not calls:
            required_tool = _required_tool_for_message(message)
            if required_tool and required_tool not in tool_calls_made and step < MAX_STEPS - 1:
                log.info("[agent] recovering missing required tool '%s'", required_tool)
                tool_calls_made.append(required_tool)
                result_str = _execute_tool(
                    required_tool,
                    _fallback_tool_arguments(required_tool, message, disease),
                    user_id=user_id,
                    disease=disease,
                )
                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({
                    "role": "user",
                    "content": f"<tool_result name=\"{required_tool}\">{result_str}</tool_result>",
                })
                continue
            # No tool calls → this is the final answer
            final_reply = _strip_tool_calls(assistant_content)
            break

        # Execute tools and append results
        messages.append({"role": "assistant", "content": assistant_content})
        for call in calls:
            tool_name = call["name"]
            call_key = (tool_name, json.dumps(call["arguments"], sort_keys=True, default=str))
            if call_key in executed_call_keys:
                log.info("[agent] skipping duplicate tool call '%s'", tool_name)
                messages.append({
                    "role": "user",
                    "content": f"<tool_result name=\"{tool_name}\">{{\"status\": \"duplicate_call_skipped\"}}</tool_result>",
                })
                continue
            executed_call_keys.add(call_key)
            tool_calls_made.append(tool_name)
            log.info("[agent] calling tool '%s' args=%s", tool_name, call["arguments"])
            result_str = _execute_tool(
                tool_name,
                call["arguments"],
                user_id=user_id,
                disease=disease,
            )
            messages.append({
                "role":    "user",
                "content": f"<tool_result name=\"{tool_name}\">{result_str}</tool_result>",
            })
    else:
        # MAX_STEPS reached without a clean final answer
        if not final_reply:
            final_reply = _strip_tool_calls(assistant_content if 'assistant_content' in dir() else "")
            if not final_reply:
                final_reply = "I'm having trouble formulating a response.  Please try rephrasing."

    # ── 4. Audit this turn ────────────────────────────────────────────────
    summary = f"Q: {message[:150]} | Tools: {tool_calls_made} | A: {final_reply[:150]}"
    TOOL_REGISTRY["log_interaction"](
        user_id=user_id,
        turn_summary=summary,
        disease=disease or "general",
    )

    latency_ms = (time.perf_counter() - t_start) * 1000
    log.info(
        "[agent] done  user=%s  steps=%d  tools=%s  latency=%.0fms",
        user_id, steps, tool_calls_made, latency_ms,
    )

    return {
        "reply":           final_reply,
        "tool_calls_made": tool_calls_made,
        "escalated":       False,
        "latency_ms":      round(latency_ms, 1),
        "steps":           steps,
    }
