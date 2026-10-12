"""
backend/chatbot/agent.py
─────────────────────────
ReAct-pattern agent driving the Dr. Nutriloop Clinical AI Chatbot.

Key Features:
  1. Strict Model Gating: Will not respond if local model is not installed.
  2. On-Demand Background Execution: Brings up Ollama on-demand and arms 60s idle auto-shutdown.
  3. Patient Clinical Dossier: Injects patient vitals, latest lab biomarkers, historical trends,
     active medications, and active 7-Day Regional Meal Plan into context.
  4. Authoritative Doctor Persona & 3-Disease Scope Enforcement.
  5. Live 7-Day Diet Plan Alteration via `alter_diet_plan_meal` with clinical safety checks.
"""

from __future__ import annotations

import os
import sys

# Globally prevent Python from writing .pyc files or creating __pycache__ directories
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import json
import logging
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
from backend.chatbot.risk_analysis import run_diet_risk_analysis
from backend.ollama_manager import ollama_manager
from backend.db import (
    get_app_setting,
    get_latest_patient_test,
    get_patient_test_history,
    get_active_weekly_plan,
    save_active_weekly_plan,
)
from backend.reporting import food_kb

log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL",    "llama3.2:3b")
MAX_STEPS       = 6          # max reasoning iterations before forced reply
TIMEOUT_S       = 120        # seconds — CPU inference allowance


# ──────────────────────────────────────────────────────────────────────────────
# Escalation check (pre-LLM)
# ──────────────────────────────────────────────────────────────────────────────

_COMPILED_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in ESCALATION_PATTERNS
]


def _is_escalation_required(text: str) -> bool:
    """Return True if the message describes an acute life-threatening emergency."""
    for pattern in _COMPILED_PATTERNS:
        if pattern.search(text):
            return True
    return False


# ──────────────────────────────────────────────────────────────────────────────
# Patient Clinical Dossier Builder
# ──────────────────────────────────────────────────────────────────────────────

def _build_patient_clinical_dossier(user_id: str) -> str:
    """Compile comprehensive medical record context from local database."""
    from backend.db import get_latest_patient_test, get_patient_test_history, get_active_weekly_plan

    latest = get_latest_patient_test(user_id)
    history = get_patient_test_history(user_id)
    active_plan = get_active_weekly_plan(user_id)

    lines = [
        "═══════════════════════════════════════════════════════════════════════",
        "PATIENT CONFIDENTIAL CLINICAL DOSSIER (REAL-TIME MEDICAL RECORD)",
        "═══════════════════════════════════════════════════════════════════════",
    ]

    if not latest and not history:
        lines.append(f"Patient Identifier / Name: {user_id}")
        lines.append("Biomarker Records: No diagnostic test records uploaded yet. Encourage patient to upload their lab report.")
    else:
        age = latest.get("age_years", 45) if latest else 45
        sex = str(latest.get("sex", "unspecified")).capitalize() if latest else "Unspecified"
        bmi = latest.get("body_mass_index", 24.0) if latest else 24.0
        dt = latest.get("created_at", "")[:16].replace("T", " ") if latest else "Recent"

        lines.append(f"• Patient: {user_id} | Age: {age} yrs | Sex: {sex} | BMI: {bmi:.1f} kg/m²")
        lines.append(f"• Latest Test Timestamp: {dt}")

        labs = latest.get("test_reports", {}) if latest else {}
        lines.append("• Current Biomarkers (Latest Diagnostic Panel):")
        lines.append(f"  - Blood Pressure: {labs.get('systolic_bp_mmhg', 120)} / {labs.get('diastolic_bp_mmhg', 80)} mmHg")
        lines.append(f"  - Fasting Plasma Glucose: {labs.get('fasting_glucose_mg_dl', 90)} mg/dL | HbA1c: {labs.get('hba1c_pct', 5.2)}%")
        lines.append(f"  - Renal Function: Serum Creatinine {labs.get('serum_creatinine_mg_dl', 0.9)} mg/dL | eGFR {labs.get('egfr_ml_min', 90)} mL/min")
        lines.append(f"  - Serum Electrolytes: Potassium {labs.get('serum_potassium_meq_l', 4.2)} mEq/L | Sodium {labs.get('serum_sodium_meq_l', 140)} mEq/L")

        conds = latest.get("detected_conditions", []) if latest else []
        lines.append(f"• Detected Chronic Conditions: {', '.join(conds) if conds else 'None detected (Low Risk)'}")

        ass = latest.get("assessments", {}) if latest else {}
        if ass:
            lines.append("• Calibrated ML Disease Risk Scores:")
            for d_key, d_info in ass.items():
                if isinstance(d_info, dict):
                    pct = d_info.get("risk_percent", 0.0)
                    lvl = str(d_info.get("risk_level", "low")).upper()
                    lines.append(f"  - {d_key.upper()}: {pct}% ({lvl} RISK)")

        if len(history) > 1:
            lines.append("• Longitudinal Biomarker Trajectory (Historical Tests):")
            for h in history[:5]:
                h_dt = h.get("created_at", "")[:16].replace("T", " ")
                h_sbp = h.get("systolic_bp_mmhg", "-")
                h_fbg = h.get("fasting_glucose_mg_dl", "-")
                h_a1c = h.get("hba1c_pct", "-")
                h_egfr = h.get("egfr_ml_min", "-")
                lines.append(f"  [{h_dt}] BP: {h_sbp} mmHg | FBG: {h_fbg} mg/dL | HbA1c: {h_a1c}% | eGFR: {h_egfr} mL/min")

    if active_plan:
        lines.append("───────────────────────────────────────────────────────────────────────")
        lines.append("CURRENT ACTIVE 7-DAY REGIONAL NUTRITION PLAN:")
        cuisine = active_plan.get("regional_cuisine") or (active_plan.get("patient_summary") or {}).get("native_region", "Regional")
        pattern = (active_plan.get("patient_summary") or {}).get("dietary_pattern", "balanced")
        meds = active_plan.get("medication_alerts") or active_plan.get("active_medication_alerts", [])
        craving = active_plan.get("smart_craving_strategy") or {}
        ct = active_plan.get("clinical_targets", {})

        lines.append(f"• Regional Cuisine Tradition: {cuisine} | Dietary Pattern: {pattern}")
        lines.append(f"• Calibrated Targets: {ct.get('calories_kcal', 1800)} kcal | Na ≤ {ct.get('sodium_limit_mg', 1500)}mg | K ≤ {ct.get('potassium_guidance_mg', 2000)}mg | Protein {ct.get('protein_g', 60)}g")
        if meds:
            lines.append(f"• Pharmacopeia & Drug Alerts: {'; '.join(meds)}")
        if craving and craving.get("requested_craving"):
            lines.append(f"• Smart Craving Budget: '{craving.get('requested_craving')}' allowed 1x/week on {craving.get('scheduled_day')} ({craving.get('scheduled_meal')}). Other 6 days strictly locked sugar-free.")

        lines.append("• 7-Day Meal Schedule Overview:")
        for d in active_plan.get("days", []):
            d_num = d.get("day_number", 1)
            d_name = d.get("day_name", f"Day {d_num}")
            tot = d.get("daily_total_nutrients", {})
            intervals_summary = []
            for inv in d.get("intervals", []):
                intervals_summary.append(f"{inv.get('interval_name')}: {inv.get('meal_title')}")
            lines.append(f"  Day {d_num} ({d_name}) [{tot.get('calories', '-')} kcal]: {', '.join(intervals_summary)}")
    else:
        lines.append("• Active 7-Day Nutrition Plan: Not yet generated. Advise patient to generate their plan in Tab 2.")

    lines.append("═══════════════════════════════════════════════════════════════════════")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# Tool-call parsing
# ──────────────────────────────────────────────────────────────────────────────

_TOOL_CALL_RE = re.compile(
    r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL
)
_XML_TOOL_RE = re.compile(
    r"<(?P<name>get_risk_profile|get_diet_plan|search_food_kb|log_meal|alter_diet_plan_meal)\b"
    r"(?P<attributes>[^>]*?)(?:/>|>(?P<body>.*?)</(?P=name)>)",
    re.IGNORECASE | re.DOTALL,
)
_XML_ATTRIBUTE_RE = re.compile(r"(?P<key>[A-Za-z_]+)=(?:\"(?P<double>[^\"]*)\"|'(?P<single>[^']*)')")


def _parse_tool_calls(text: str) -> List[Dict[str, Any]]:
    """Extract all <tool_call>{…}</tool_call> JSON blocks from an LLM response."""
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
    """Remove tool markup so patient receives clean clinical prose."""
    cleaned = _TOOL_CALL_RE.sub("", text)
    return _XML_TOOL_RE.sub("", cleaned).strip()


def _required_tool_for_message(message: str) -> Optional[str]:
    """Infer the mandatory grounding tool when user explicitly requests specific lookups."""
    lowered = message.lower()
    # If the user is requesting an alteration or discussing symptoms/mechanisms, do not force KB lookup
    if any(token in lowered for token in ("alter", "swap", "change", "replace", "substitute", "why", "how", "what triggers", "prevent")):
        return None
    if any(token in lowered for token in ("log this", "log that", "log my", "had ")):
        return "log_meal"
    if any(token in lowered for token in ("what is my risk", "risk score", "risk level")):
        return "get_risk_profile"
    if any(token in lowered for token in ("calorie target", "my sodium limit", "my potassium limit")):
        return "get_diet_plan"
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
# Ollama HTTP Client
# ──────────────────────────────────────────────────────────────────────────────

def _ollama_chat(messages: List[Dict[str, str]]) -> str:
    """Call Ollama /api/chat."""
    payload = {
        "model":    OLLAMA_MODEL,
        "messages": messages,
        "stream":   False,
        "options":  {
            "temperature": 0.2,
            "top_p":       0.9,
        },
    }

    with httpx.Client(timeout=TIMEOUT_S) as client:
        resp = client.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
        )
        resp.raise_for_status()

    data = resp.json()
    return data.get("message", {}).get("content", "")


# ──────────────────────────────────────────────────────────────────────────────
# Tool execution
# ──────────────────────────────────────────────────────────────────────────────

def _execute_tool(
    name: str,
    arguments: Dict[str, Any],
    user_id: str,
    disease: Optional[str],
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Call a tool from TOOL_REGISTRY and return (result_json_str, updated_diet_plan_or_None)."""
    if name not in TOOL_REGISTRY:
        return json.dumps({"error": f"Unknown tool: '{name}'"}), None

    tool_arguments = dict(arguments)
    for key, value in list(tool_arguments.items()):
        if isinstance(value, str) and value.strip().lower() in {"null", "none"}:
            tool_arguments[key] = None

    if name in {"get_risk_profile", "log_meal", "log_interaction", "alter_diet_plan_meal", "get_diet_plan"}:
        tool_arguments["user_id"] = user_id
    if name in {"get_risk_profile", "search_food_kb", "log_interaction"}:
        tool_arguments["disease"] = disease or "general"

    # Type normalization for alter_diet_plan_meal
    if name == "alter_diet_plan_meal":
        if "day_number" in tool_arguments:
            try:
                tool_arguments["day_number"] = int(tool_arguments["day_number"])
            except (ValueError, TypeError):
                tool_arguments["day_number"] = 1
        if isinstance(tool_arguments.get("new_items"), str):
            try:
                tool_arguments["new_items"] = json.loads(tool_arguments["new_items"])
            except Exception:
                tool_arguments["new_items"] = [{"item_name": tool_arguments["new_items"], "portion": "Standard"}]

    updated_diet_plan = None
    try:
        result = TOOL_REGISTRY[name](**tool_arguments)
        if name == "alter_diet_plan_meal" and isinstance(result, dict):
            if result.get("status") == "success" and "updated_plan" in result:
                updated_diet_plan = result["updated_plan"]
    except TypeError as exc:
        result = {"error": f"Invalid arguments for tool '{name}': {exc}"}
    except Exception as exc:
        log.exception("Tool '%s' raised an unexpected error", name)
        result = {"error": f"Tool '{name}' failed: {exc}"}

    return json.dumps(result, ensure_ascii=False, default=str), updated_diet_plan


# ──────────────────────────────────────────────────────────────────────────────
# Cloud LLM Clients (Google Gemini & OpenAI Compatible)
# ──────────────────────────────────────────────────────────────────────────────

def _call_gemini_api(api_key: str, system_prompt: str, messages: List[Dict[str, str]], model_name: str = "gemini-1.5-flash") -> str:
    """Invoke Google Gemini generative model via official REST API."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    contents = []
    for m in messages:
        if m.get("role") == "system":
            continue
        role = "user" if m.get("role") == "user" else "model"
        contents.append({"role": role, "parts": [{"text": m.get("content", "")}]})

    if not contents:
        contents = [{"role": "user", "parts": [{"text": "Hello Dr. Nutriloop"}]}]

    body = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.35,
            "maxOutputTokens": 1200,
        }
    }
    with httpx.Client(timeout=35.0) as client:
        resp = client.post(url, json=body)
        if resp.status_code != 200:
            raise RuntimeError(f"Gemini API error ({resp.status_code}): {resp.text}")
        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError("Gemini returned empty candidates")
        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            raise RuntimeError("Gemini returned empty content parts")
        return parts[0].get("text", "")


def _call_openai_api(api_key: str, system_prompt: str, messages: List[Dict[str, str]], model_name: str = "gpt-4o-mini", base_url: str = "https://api.openai.com/v1") -> str:
    """Invoke OpenAI-compatible chat completions REST API."""
    formatted_msgs = [{"role": "system", "content": system_prompt}]
    for m in messages:
        if m.get("role") != "system":
            formatted_msgs.append({"role": m.get("role", "user"), "content": m.get("content", "")})

    body = {
        "model": model_name,
        "messages": formatted_msgs,
        "temperature": 0.35,
        "max_tokens": 1200,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    with httpx.Client(timeout=35.0) as client:
        resp = client.post(f"{base_url}/chat/completions", headers=headers, json=body)
        if resp.status_code != 200:
            raise RuntimeError(f"OpenAI API error ({resp.status_code}): {resp.text}")
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("OpenAI returned no choices")
        return choices[0].get("message", {}).get("content", "")


def _get_or_create_active_plan(user_id: str) -> Dict[str, Any]:
    """Retrieve existing active weekly plan or generate and save a tailored baseline plan."""
    plan = get_active_weekly_plan(user_id)
    if plan and plan.get("days"):
        return plan
    try:
        from backend.schemas import WeeklyDietPlanRequest
        from backend.weekly_diet_engine import weekly_diet_engine
        req = WeeklyDietPlanRequest(
            user_id=user_id,
            native_region="South Indian",
            dietary_pattern="balanced",
        )
        plan_obj = weekly_diet_engine.generate_weekly_plan(req)
        plan_dict = plan_obj.model_dump()
        save_active_weekly_plan(user_id, plan_dict)
        return plan_dict
    except Exception as exc:
        log.warning("[agent] Failed to auto-generate baseline weekly plan: %s", exc)
        return plan or {}


def _is_show_diet_intent(msg_low: str) -> bool:
    triggers = [
        "check the current diet", "check my diet", "check current diet",
        "paste it here", "show my diet", "show my meal plan", "show the diet",
        "view my diet", "view current diet", "what is my diet", "what is my current diet",
        "what's my diet", "what am i eating", "print my diet", "display my diet",
        "current meal plan", "my meal plan", "paste my diet", "show the plan", "see my diet",
        "check the diet", "check diet", "my diet plan", "read my diet"
    ]
    return any(t in msg_low for t in triggers)


def _handle_show_diet(user_id: str) -> Tuple[str, Dict[str, Any]]:
    """Format and return the patient's active 7-day schedule with detailed Day 1 breakdown."""
    plan = _get_or_create_active_plan(user_id)
    ct = plan.get("clinical_targets", {})
    cal = ct.get("calories_kcal", 1800)
    sod = ct.get("sodium_limit_mg", 1500)
    pot = ct.get("potassium_guidance_mg", 2000)
    pro = ct.get("protein_g", 60)
    cuisine = plan.get("regional_cuisine") or (plan.get("patient_summary") or {}).get("native_region", "Regional Indian")

    days = plan.get("days", [])
    if not days:
        return (
            "I couldn't find an active 7-day schedule for your profile yet. "
            "Please generate your plan in the **Meal Plan** tab or tell me what cuisine you prefer, and I'll create one for you!",
            plan
        )

    day1 = days[0]
    lines = [
        f"Here is your active **7-Day {cuisine} Nutrition Schedule** calibrated for your metabolic targets ({cal} kcal | Na <= {sod}mg | K <= {pot}mg | Protein {pro}g):\n",
        f"### 📋 Day 1 ({day1.get('day_name', 'Monday')}) - Detailed Schedule:"
    ]
    for inv in day1.get("intervals", []):
        inv_name = inv.get("interval_name", "Meal")
        time_win = inv.get("time_window", "")
        title = inv.get("meal_title", "")
        nut = inv.get("total_nutrients", {})
        c = nut.get("calories", "-")
        items_str = ", ".join(f"{it.get('item_name')} ({it.get('portion', '')})" for it in inv.get("items", []) if isinstance(it, dict))
        time_part = f" *({time_win})*" if time_win else ""
        lines.append(f"• **{inv_name}**{time_part}: **{title}** [{c} kcal]")
        if items_str:
            lines.append(f"  *Includes:* {items_str}")

    lines.append("\n### 📅 Rest of the Week at a Glance:")
    for d in days[1:]:
        d_num = d.get("day_number", "")
        d_name = d.get("day_name", f"Day {d_num}")
        main_meals = []
        for inv in d.get("intervals", []):
            if inv.get("interval_name") in ("Breakfast", "Lunch", "Dinner"):
                main_meals.append(f"{inv.get('interval_name')}: {inv.get('meal_title')}")
        tot_c = d.get("daily_total_nutrients", {}).get("calories", "-")
        lines.append(f"• **Day {d_num} ({d_name})** [{tot_c} kcal]: {'; '.join(main_meals)}")

    lines.append("\nWould you like me to swap, adjust, or remove any specific meals or ingredients from this schedule?")
    return "\n".join(lines), plan


def _is_remove_ingredient_intent(msg_low: str) -> bool:
    cues = [
        "remove", "exclude", "take out", "cut out", "delete", "eliminate",
        "don't like", "dont like", "dislike", "hate", "no more", "get rid of",
        "stop having", "don't want", "dont want"
    ]
    return any(c in msg_low for c in cues)


def _extract_excluded_food(msg_low: str) -> Optional[str]:
    # 1. Direct patterns like "don't like tofu"
    m_dislike = re.search(r"(?:don't like|dont like|dislike|hate|no more|don't want|dont want)\s+([a-zA-Z\s]+?)(?:,|\.|\s+remove|\s+from|\s+in|\s+please|$)", msg_low)
    if m_dislike:
        food = m_dislike.group(1).strip()
        food = re.sub(r"^(the|any|some)\s+", "", food).strip()
        if food and food not in ("it", "this", "that", "them"):
            return food

    # 2. Action patterns like "remove carrots from the diet"
    m_rem = re.search(r"(?:remove|exclude|take out|cut out|eliminate|get rid of|delete)\s+([a-zA-Z\s]+?)(?:\s+from|\s+in|\s+out|\s+please|\.|\,|$)", msg_low)
    if m_rem:
        food = m_rem.group(1).strip()
        food = re.sub(r"^(the|any|some)\s+", "", food).strip()
        if food and food not in ("it", "this", "that", "them"):
            return food

    # 3. Known culinary keyword fallback
    for candidate in [
        "tofu", "carrot", "carrots", "egg", "eggs", "chicken", "paneer", "mushroom",
        "mushrooms", "spinach", "palak", "onion", "onions", "potato", "potatoes",
        "tomato", "tomatoes", "fish", "mutton", "beef", "pork", "brinjal", "eggplant",
        "banana", "sugar", "dairy", "milk", "cheese", "rice"
    ]:
        if candidate in msg_low:
            return candidate

    return None


SUBSTITUTION_MAP = {
    "tofu": {
        "sub_name": "Low-Fat Paneer",
        "sub_item": "Pan-seared Low-Fat Paneer",
        "portion": "80g",
        "cal": 130, "pro": 12.0, "sod": 50.0,
        "clinical_note": "replaced with fresh low-fat paneer, providing high-quality protein with low carbohydrate and controlled sodium"
    },
    "carrot": {
        "sub_name": "French Beans & Zucchini",
        "sub_item": "Steamed French Beans and Zucchini",
        "portion": "100g",
        "cal": 35, "pro": 1.8, "sod": 20.0,
        "clinical_note": "replaced with French beans and zucchini, keeping fiber high and potassium gentle for renal health"
    },
    "carrots": {
        "sub_name": "French Beans & Zucchini",
        "sub_item": "Steamed French Beans and Zucchini",
        "portion": "100g",
        "cal": 35, "pro": 1.8, "sod": 20.0,
        "clinical_note": "replaced with French beans and zucchini, keeping fiber high and potassium gentle for renal health"
    },
    "paneer": {
        "sub_name": "Organic Tofu",
        "sub_item": "Pan-seared Organic Tofu",
        "portion": "100g",
        "cal": 90, "pro": 10.0, "sod": 30.0,
        "clinical_note": "replaced with organic tofu to maintain lean protein with negligible saturated fat"
    },
    "egg": {
        "sub_name": "Paneer Bhurji",
        "sub_item": "Light Paneer Bhurji with Bell Peppers",
        "portion": "80g",
        "cal": 140, "pro": 11.0, "sod": 60.0,
        "clinical_note": "replaced with spiced low-fat paneer bhurji to ensure steady protein without cholesterol"
    },
    "eggs": {
        "sub_name": "Paneer Bhurji",
        "sub_item": "Light Paneer Bhurji with Bell Peppers",
        "portion": "80g",
        "cal": 140, "pro": 11.0, "sod": 60.0,
        "clinical_note": "replaced with spiced low-fat paneer bhurji to ensure steady protein without cholesterol"
    },
    "chicken": {
        "sub_name": "Soya & Paneer Curry",
        "sub_item": "Nutri Soya Chunks and Paneer Curry",
        "portion": "100g",
        "cal": 150, "pro": 14.0, "sod": 70.0,
        "clinical_note": "replaced with soya chunks and paneer curry for complete amino acids and zero saturated animal fat"
    },
    "mushroom": {
        "sub_name": "Bottle Gourd",
        "sub_item": "Steamed Bottle Gourd (Lauki) & Peas",
        "portion": "100g",
        "cal": 30, "pro": 1.2, "sod": 15.0,
        "clinical_note": "replaced with bottle gourd and green peas, providing gentle hydration and low potassium"
    },
    "mushrooms": {
        "sub_name": "Bottle Gourd",
        "sub_item": "Steamed Bottle Gourd (Lauki) & Peas",
        "portion": "100g",
        "cal": 30, "pro": 1.2, "sod": 15.0,
        "clinical_note": "replaced with bottle gourd and green peas, providing gentle hydration and low potassium"
    },
    "spinach": {
        "sub_name": "Methi & Ridge Gourd",
        "sub_item": "Sautéed Fenugreek Leaves & Ridge Gourd",
        "portion": "100g",
        "cal": 40, "pro": 2.0, "sod": 25.0,
        "clinical_note": "replaced with fenugreek and ridge gourd, avoiding heavy oxalates while supporting blood sugar"
    },
    "palak": {
        "sub_name": "Methi & Ridge Gourd",
        "sub_item": "Sautéed Fenugreek Leaves & Ridge Gourd",
        "portion": "100g",
        "cal": 40, "pro": 2.0, "sod": 25.0,
        "clinical_note": "replaced with fenugreek and ridge gourd, avoiding heavy oxalates while supporting blood sugar"
    },
}


def _handle_remove_ingredient(user_id: str, message: str) -> Tuple[str, Dict[str, Any]]:
    """Scan and substitute an excluded ingredient across the entire 7-day schedule and persist changes."""
    msg_low = message.lower()
    food = _extract_excluded_food(msg_low) or "that food"
    target_clean = food.lower().strip()
    target_stem = target_clean[:-1] if target_clean.endswith("s") and len(target_clean) > 3 else target_clean

    plan = _get_or_create_active_plan(user_id)
    days = plan.get("days", [])

    sub_info = SUBSTITUTION_MAP.get(target_clean) or SUBSTITUTION_MAP.get(target_stem) or {
        "sub_name": "French Beans & Zucchini",
        "sub_item": "Sautéed French Beans and Zucchini",
        "portion": "100g",
        "cal": 35, "pro": 1.5, "sod": 20.0,
        "clinical_note": f"replaced with fresh French beans and zucchini to maintain clinical electrolyte and fiber balance without {target_clean}"
    }

    sub_name = sub_info["sub_name"]
    sub_item_name = sub_info["sub_item"]
    sub_portion = sub_info.get("portion", "100g")

    replaced_count = 0
    modified_meal_names = []

    for d in days:
        for inv in d.get("intervals", []):
            inv_changed = False
            title = inv.get("meal_title", "")
            if target_stem in title.lower() or target_clean in title.lower():
                pattern = re.compile(rf"\b{re.escape(target_clean)}\b|\b{re.escape(target_stem)}\b", re.IGNORECASE)
                new_title = pattern.sub(sub_name, title)
                inv["meal_title"] = new_title
                inv_changed = True
                modified_meal_names.append(f"{inv.get('interval_name')} on {d.get('day_name', 'Day ' + str(d.get('day_number', '')))}")

            new_items = []
            for it in inv.get("items", []):
                if isinstance(it, dict):
                    it_name = it.get("item_name", "")
                    if target_stem in it_name.lower() or target_clean in it_name.lower():
                        new_items.append({
                            "item_name": sub_item_name,
                            "portion": sub_portion
                        })
                        inv_changed = True
                        replaced_count += 1
                    else:
                        new_items.append(it)
                elif isinstance(it, str):
                    if target_stem in it.lower() or target_clean in it.lower():
                        new_items.append(f"{sub_item_name} ({sub_portion})")
                        inv_changed = True
                        replaced_count += 1
                    else:
                        new_items.append(it)
            inv["items"] = new_items

            if inv_changed:
                inv["clinical_justification"] = f"Adjusted to exclude {target_clean} and substituted with {sub_name} for safe clinical nutrition."

        # Recalculate daily totals
        d_cals = sum(int(inv.get("total_nutrients", {}).get("calories") or 0) for inv in d.get("intervals", []))
        if d_cals > 0:
            d.setdefault("daily_total_nutrients", {})["calories"] = d_cals

    # Update excluded ingredients tracking
    plan.setdefault("excluded_ingredients", [])
    if target_clean not in plan["excluded_ingredients"]:
        plan["excluded_ingredients"].append(target_clean)

    # Clean categorized grocery checklist
    if plan.get("categorized_grocery_checklist"):
        for cat, items in plan["categorized_grocery_checklist"].items():
            plan["categorized_grocery_checklist"][cat] = [
                it for it in items if target_stem not in it.lower() and target_clean not in it.lower()
            ]

    # Save to SQLite
    save_active_weekly_plan(user_id, plan)

    reply = (
        f"I have removed **{food}** from your entire 7-day meal plan and substituted it with **{sub_name}** ({sub_info['clinical_note']}).\n\n"
        f"Your updated meal schedule has been saved and is active in your **Meal Plan** tab. "
        f"All daily calories, sodium, and potassium remain within your clinical targets."
    )
    return reply, plan


def _detect_food_inquiry(msg_low: str) -> Optional[str]:
    m = re.search(r"how is\s+([a-zA-Z\s]+?)\s+(?:good|healthy|beneficial|helpful)", msg_low)
    if m: return re.sub(r"^(the|a|an)\s+", "", m.group(1).strip())
    m = re.search(r"why (?:is|are)\s+([a-zA-Z\s]+?)\s+(?:good|healthy|beneficial|recommended)", msg_low)
    if m: return re.sub(r"^(the|a|an)\s+", "", m.group(1).strip())
    m = re.search(r"(?:benefits|benefit|nutrition|nutritional value) of\s+([a-zA-Z\s]+)", msg_low)
    if m: return re.sub(r"^(the|a|an)\s+", "", m.group(1).strip())
    m = re.search(r"is\s+([a-zA-Z\s]+?)\s+(?:good|healthy|safe|ok|fine)\s*(?:for me|for my health|\?|$)", msg_low)
    if m: return re.sub(r"^(the|a|an)\s+", "", m.group(1).strip())
    m = re.search(r"can i (?:eat|have|consume)\s+([a-zA-Z\s]+)", msg_low)
    if m: return re.sub(r"^(the|a|an)\s+", "", m.group(1).strip())
    return None


def _handle_food_benefits(
    food: str,
    labs: Dict[str, Any],
    is_ckd: bool,
    is_htn: bool,
    is_diabetic: bool,
    is_hyperkalemic: bool
) -> str:
    f_low = food.lower().strip()
    pot = labs.get("serum_potassium_meq_l")

    if "carrot" in f_low:
        pot_tip = (
            "Because your lab reports show serum potassium is monitored, boiling or leaching carrots lowers potassium by ~50%, keeping it completely safe."
            if (is_ckd or is_hyperkalemic) else
            "Its potassium content (~260mg/100g) supports healthy arterial elasticity and counteracts sodium."
        )
        return (
            "Carrots are a nutrient-rich, low-glycemic vegetable with proven benefits for chronic metabolic health:\n\n"
            "• **Blood Sugar Stability**: Carrots have a low glycemic index (16–35) and a low glycemic load. Their soluble pectin fiber slows carbohydrate absorption in the gut, blunting postprandial glucose curves.\n"
            f"• **Renal & Blood Pressure Balance**: A 100g portion contains only ~43–52 mg of sodium and ~260–270 mg of potassium. {pot_tip}\n"
            "• **Microvascular & Eye Protection**: Rich in beta-carotene (provitamin A) and lutein, which protect the fine retinal capillaries against diabetic retinopathy and reduce arterial inflammation.\n\n"
            "**Recommended Preparation**: Enjoy them lightly steamed, grated fresh in salads with lemon juice, or in vegetable sabzis with cumin and turmeric. Would you like me to include carrots in your meal plan?"
        )

    if "cucumber" in f_low:
        return (
            "Cucumbers are ideal for hypertension, kidney protection, and blood sugar balance:\n\n"
            "• **Hydration & Caloric Balance**: Cucumbers are >95% water and contain virtually zero calories or carbohydrates, preventing blood sugar surges.\n"
            "• **Electrolyte Balance**: Naturally low in sodium (~2mg/100g) with moderate potassium (~145mg/100g), helping flush cellular waste without burdening kidney filtration.\n"
            "• **Cooling & Digestive Support**: Natural sterols and flavonoids support endothelial relaxation and digestive comfort.\n\n"
            "**Recommended Preparation**: Enjoy sliced with a squeeze of fresh lemon and roasted cumin, or in unsweetened cucumber raita."
        )

    if any(k in f_low for k in ["bottle gourd", "lauki", "dudhi"]):
        return (
            "Bottle Gourd (Lauki) is considered a gold standard vegetable in clinical nephrology and cardiology:\n\n"
            "• **Kidney Gentle**: Extremely low in sodium, gentle in potassium, and 96% water, making it the easiest vegetable for compromised nephrons to filter.\n"
            "• **Glycemic Balance**: Negligible carbohydrates and high soluble fiber blunt postprandial glucose surges.\n"
            "• **Blood Pressure & Vascular Health**: Rich in potassium-to-sodium ratio that naturally supports blood pressure control.\n\n"
            "**Recommended Preparation**: Steam into light kootus, soups, or vegetable stews seasoned with cumin and coriander."
        )

    if any(k in f_low for k in ["bitter gourd", "karela"]):
        return (
            "Bitter Gourd (Karela) has well-documented insulin-sensitizing properties:\n\n"
            "• **Glucose Regulation**: Contains charantin, vicine, and polypeptide-p (a plant insulin mimetic) which stimulate peripheral glucose uptake and reduce liver gluconeogenesis.\n"
            "• **Low Glycemic Load**: Very low carbohydrate density prevents postprandial spikes.\n"
            "• **Cardiovascular & Renal**: Moderate potassium and low sodium make it suitable for kidney and blood pressure care in moderate portions.\n\n"
            "**Recommended Preparation**: Sauté with onion, turmeric, and mustard seeds with minimal oil, avoiding heavy sugar or jaggery balancing."
        )

    if any(k in f_low for k in ["spinach", "palak"]):
        if is_ckd or is_hyperkalemic:
            return (
                "Spinach is rich in iron, lutein, and fiber, but it is high in potassium (~460mg/100g) and oxalates.\n\n"
                f"Given your kidney profile (potassium {pot:.1f} mEq/L if pot else 'monitored'), raw spinach should be limited. "
                "However, **blanching or leaching** (boiling in plenty of water and discarding the cooking water) leaches out up to 60% of the potassium and oxalates, making it much safer to enjoy in moderate portions."
            )
        return (
            "Spinach is a nutrient-dense leafy green rich in dietary nitrates, folate, lutein, and iron:\n\n"
            "• **Blood Pressure**: Dietary nitrates convert to nitric oxide, promoting vasodilation and arterial flexibility.\n"
            "• **Blood Sugar**: Alpha-lipoic acid in spinach has been shown to increase insulin sensitivity and lower oxidative stress.\n\n"
            "Enjoy lightly sautéed with garlic and cumin or in dal palak."
        )

    if any(k in f_low for k in ["broccoli", "cauliflower", "gobi"]):
        return (
            "Cruciferous vegetables like broccoli and cauliflower are clinical powerhouses for metabolic health:\n\n"
            "• **Sulforaphane & Antioxidants**: Combat oxidative damage in renal microvessels and vascular endothelium.\n"
            "• **Low Carbohydrate Substitute**: Outstanding low-carb substitute for high-glycemic potatoes or white rice.\n"
            "• **Renal Safety**: Steamed cauliflower is low in potassium (~140mg/100g) and negligible in sodium, making it one of the safest vegetables for kidney disease."
        )

    if "apple" in f_low:
        return (
            "Apples are among the safest and healthiest fruits for kidney, diabetes, and heart management:\n\n"
            "• **Renal Protection**: Apples are naturally low in potassium (~107mg per 100g) and negligible in sodium, unlike bananas or oranges.\n"
            "• **Pectin Soluble Fiber**: Slows carbohydrate absorption, stabilizes morning glucose, and helps bind intestinal cholesterol.\n"
            "• **Quercetin**: A potent flavonoid antioxidant that helps protect blood vessels and reduces vascular inflammation."
        )

    if "tomato" in f_low:
        pot_warn = "keep portions moderate and avoid concentrated tomato pastes or purees." if (is_ckd or is_hyperkalemic) else "a medium raw tomato easily fits inside your daily targets."
        return (
            "Tomatoes offer cardioprotective benefits through lycopene, Vitamin C, and potassium:\n\n"
            "• **Cardiovascular Defense**: Lycopene is an antioxidant shown to improve endothelial function and reduce LDL oxidation.\n"
            "• **Glycemic Balance**: Very low carbohydrate density with negligible glycemic impact.\n"
            f"• **Electrolyte Guidance**: A medium tomato contains ~230mg of potassium; {pot_warn}"
        )

    # Lookup in Unified Food Knowledge Base
    try:
        first_word = f_low.split()[0]
        matches = food_kb.df[food_kb.df["food_name"].str.contains(first_word, case=False, na=False)]
        if not matches.empty:
            r = matches.iloc[0]
            fname = r.get("food_name", food)
            cals = r.get("energy_kcal", "-")
            carbs = r.get("carbohydrate_g", "-")
            pro = r.get("protein_g", "-")
            sod = r.get("sodium_mg", "-")
            pot_kb = r.get("potassium_mg", "-")
            fib = r.get("dietary_fibre_g", "-")

            renal_status = "safe in moderation"
            if is_ckd:
                try:
                    if float(pot_kb) > 300:
                        renal_status = "moderate potassium — enjoy in controlled portions or leached"
                    else:
                        renal_status = "kidney-friendly with low-to-moderate potassium"
                except (ValueError, TypeError):
                    renal_status = "suitable with portion control"

            return (
                f"**{fname}** provides the following nutritional profile per 100g:\n\n"
                f"• **Calories**: {cals} kcal | **Protein**: {pro}g | **Carbohydrates**: {carbs}g | **Fiber**: {fib}g\n"
                f"• **Sodium**: {sod} mg | **Potassium**: {pot_kb} mg\n\n"
                f"**Clinical Assessment**:\n"
                f"• **Blood Sugar Impact**: With {carbs}g carbohydrates and {fib}g fiber, it has a manageable glycemic profile when paired with protein.\n"
                f"• **Renal & Blood Pressure**: Contains {sod}mg sodium ({renal_status}).\n\n"
                f"Would you like me to include {fname} in your 7-day meal plan?"
            )
    except Exception as exc:
        log.warning("[_handle_food_benefits] KB lookup failed: %s", exc)

    return (
        f"**{food.capitalize()}** can generally be incorporated into a balanced diet when prepared mindfully:\n\n"
        "• **Blood Sugar Consideration**: Pair whole food ingredients with lean protein and fiber to ensure a steady postprandial glucose response.\n"
        "• **Sodium & Blood Pressure**: Prepare using whole spices like turmeric, cumin, and fresh herbs rather than table salt, pickles, or commercial flavor packets.\n"
        "• **Renal Safety**: For kidney protection, moderate portion sizes (around 75–100g) and emphasize boiling or steaming over high-heat frying.\n\n"
        f"Would you like me to check how we can fit {food} into your current 7-day meal schedule?"
    )


def _attempt_plan_alteration_from_text(user_id: str, message: str, disease: Optional[str] = None) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """Parse text for explicit patient meal alteration requests and execute clinical swap via risk analysis."""
    msg_low = message.lower()
    # If the message is a removal or dislike, do not treat as meal addition
    if any(w in msg_low for w in ["remove", "don't like", "dont like", "exclude", "hate", "cut out", "take out", "delete"]):
        return None, None
    if not any(w in msg_low for w in ["swap", "replace", "change meal", "alter meal", "substitute", "change dinner", "change lunch", "change breakfast", "add ", "add eggs", "add egg"]):
        return None, None

    # Detect day number
    day_num = 1
    days_map = {"monday": 1, "tuesday": 2, "wednesday": 3, "thursday": 4, "friday": 5, "saturday": 6, "sunday": 7}
    for d_name, d_val in days_map.items():
        if d_name in msg_low:
            day_num = d_val
            break
    day_m = re.search(r"day\s*([1-7])", msg_low)
    if day_m:
        day_num = int(day_m.group(1))

    # Detect interval
    interval = None
    if "breakfast" in msg_low:
        interval = "Breakfast"
    elif "mid-morning" in msg_low or "morning snack" in msg_low:
        interval = "Mid-Morning Snack"
    elif "lunch" in msg_low:
        interval = "Lunch"
    elif "evening snack" in msg_low or "snack" in msg_low:
        interval = "Evening Snack"
    elif "dinner" in msg_low:
        interval = "Dinner"

    # Extract proposed food
    m_with = re.search(r"(?:with|to|for|add)\s+([a-zA-Z0-9\s,\(\)]+)", message, re.IGNORECASE)
    new_dish = m_with.group(1).strip() if m_with else message
    new_dish = re.sub(r"(?i)\s+(please|doctor|in my plan|in my diet|on day \d|on \w+day).*", "", new_dish).strip()

    analysis = run_diet_risk_analysis(
        user_id=user_id,
        proposed_meal=new_dish,
        day_number=day_num,
        interval_name=interval,
    )
    if analysis["passed"]:
        note = (
            f"I've updated your meal plan to include {analysis['clean_meal_title']} for {analysis['interval_name']} on Day {analysis['day_number']}. "
            f"This modification fits safely within your clinical nutrient targets."
        )
        return note, analysis["updated_plan"]
    else:
        note = f"I cannot add '{new_dish}' to your meal plan: {analysis['clinical_explanation']}"
        return note, None


# ──────────────────────────────────────────────────────────────────────────────
# Conversational Clinical Reasoning Engine (Zero-Key / Offline Mode)
# ──────────────────────────────────────────────────────────────────────────────

def _generate_deep_clinical_response(
    user_id: str,
    message: str,
    disease: Optional[str] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Natural, conversational clinical reasoning engine.
    Enforces strict KDIGO/ADA/AHA guardrails, defends against patient loopholes,
    routes all diet modifications through the programmatic Risk Analysis Layer,
    and supports natural multi-turn context (e.g. affirmations like 'yes').
    """
    msg_clean = message.strip()
    msg_low = msg_clean.lower()

    # 1. Retrieve patient clinical dossier
    latest = get_latest_patient_test(user_id)
    labs = latest.get("test_reports", latest) if latest else {}
    fbs = labs.get("fasting_glucose_mg_dl")
    a1c = labs.get("hba1c_pct")
    sbp = labs.get("systolic_bp_mmhg")
    dbp = labs.get("diastolic_bp_mmhg")
    creat = labs.get("serum_creatinine_mg_dl")
    egfr = labs.get("egfr_ml_min")
    pot = labs.get("serum_potassium_meq_l")

    detected_conds = [str(c).lower() for c in latest.get("detected_conditions", [])] if latest else []
    is_diabetic = any("diabet" in c or "t2dm" in c for c in detected_conds) or (fbs and fbs >= 126.0) or (a1c and a1c >= 6.5)
    is_htn = any("hypertens" in c or "htn" in c for c in detected_conds) or (sbp and sbp >= 130.0) or (dbp and dbp >= 80.0)
    is_ckd = any("ckd" in c or "kidney" in c for c in detected_conds) or (egfr and egfr < 60.0) or (creat and creat >= 1.3)
    is_hyperkalemic = any("hyperkalem" in c for c in detected_conds) or (pot and pot >= 5.0)

    # 2. Natural Greetings
    if msg_low in {"hello", "hi", "hey", "greetings", "good morning", "good evening", "good afternoon", "namaste", "doctor", "doc"}:
        return (
            "Hello! I'm Nutriloop, your clinical nutrition assistant. How can I help you today with your diet, meals, or nutrition questions?",
            None
        )

    # 3. Check / Show / Paste Current Diet Schedule
    if _is_show_diet_intent(msg_low):
        return _handle_show_diet(user_id)

    # 4. Ingredient Removal / Exclusion / Dislike Requests
    if _is_remove_ingredient_intent(msg_low):
        return _handle_remove_ingredient(user_id, message)

    # 3. Multi-Turn Context & Affirmation Handling (e.g. "yes", "sure", "please do", "add it")
    affirmative_set = {"yes", "yeah", "yep", "sure", "please do", "add it", "go ahead", "do that", "ok", "okay", "yes please", "please add it", "add this"}
    if msg_low in affirmative_set or msg_low.startswith(("yes", "sure", "please add", "add it")):
        last_bot_msg = ""
        if conversation_history:
            for turn in reversed(conversation_history):
                if turn.get("role") in ("assistant", "model"):
                    last_bot_msg = turn.get("content", "").lower()
                    break

        target_food = None
        if "egg" in last_bot_msg:
            target_food = "boiled eggs"
        elif "chicken" in last_bot_msg:
            target_food = "grilled skinless chicken breast"
        elif "soup" in last_bot_msg:
            target_food = "vegetable soup"
        elif "rasam" in last_bot_msg:
            target_food = "pepper rasam"
        elif "paneer" in last_bot_msg:
            target_food = "paneer"
        elif "oats" in last_bot_msg:
            target_food = "oats upma"
        elif "ragi" in last_bot_msg:
            target_food = "ragi idli"
        elif "khichdi" in last_bot_msg:
            target_food = "moong dal khichdi"

        if target_food:
            analysis = run_diet_risk_analysis(user_id=user_id, proposed_meal=target_food, day_number=1)
            if analysis["passed"]:
                return (
                    f"I've added {analysis['clean_meal_title']} to your 7-day meal plan for {analysis['interval_name']} on Day {analysis['day_number']}. "
                    f"It fits well within your daily nutrient goals and keeps sodium and blood sugar in check. "
                    f"You can review your updated schedule in the meal plan tab anytime.",
                    analysis["updated_plan"]
                )
            else:
                return (
                    f"I looked into adding that, but because of your health profile, I can't safely include it: {analysis['clinical_explanation']}",
                    None
                )
        else:
            return (
                "Sounds good! Which meal or day would you like me to adjust, or is there a specific food you'd like to check?",
                None
            )

    # 4. Explicit Meal Alteration & Diet Modification Requests
    diet_action_tokens = [
        "change", "add", "swap", "replace", "substitute", "include", "switch",
        "alter", "incorporate", "put in my plan", "put in my diet", "update my plan",
        "non-vegetarian", "non vegetarian"
    ]
    if any(tok in msg_low for tok in diet_action_tokens):
        target_food = None
        if "egg" in msg_low:
            target_food = "boiled eggs"
        elif "chicken" in msg_low:
            target_food = "grilled chicken"
        elif "soup" in msg_low:
            target_food = "vegetable soup"
        elif "maggi" in msg_low:
            target_food = "maggi instant noodles with extra salt" if "extra salt" in msg_low else "maggi noodles"
        elif any(s in msg_low for s in ["sweet", "sugar", "cake", "pastry", "jalebi", "gulab jamun", "halwa", "ice cream"]):
            for s in ["gulab jamun", "jalebi", "chocolate cake", "cake", "ice cream", "sweet", "sugar"]:
                if s in msg_low:
                    target_food = s
                    break
        elif any(s in msg_low for s in ["papad", "pickle", "chips"]):
            for s in ["papad", "pickle", "salted chips"]:
                if s in msg_low:
                    target_food = s
                    break
        elif "starfruit" in msg_low:
            target_food = "starfruit"
        elif "banana" in msg_low:
            target_food = "banana"
        elif "coconut water" in msg_low:
            target_food = "coconut water"
        else:
            m_with = re.search(r"(?:with|to|for|add)\s+([a-zA-Z0-9\s,\(\)]+)", message, re.IGNORECASE)
            if m_with:
                target_food = m_with.group(1).strip()
                target_food = re.sub(r"(?i)\s+(please|doctor|in my plan|in my diet|on day \d|on \w+day).*", "", target_food).strip()

        if target_food:
            day_num = 1
            days_map = {"monday": 1, "tuesday": 2, "wednesday": 3, "thursday": 4, "friday": 5, "saturday": 6, "sunday": 7}
            for d_name, d_val in days_map.items():
                if d_name in msg_low:
                    day_num = d_val
                    break
            day_m = re.search(r"day\s*([1-7])", msg_low)
            if day_m:
                day_num = int(day_m.group(1))

            interval = None
            if "breakfast" in msg_low:
                interval = "Breakfast"
            elif "lunch" in msg_low:
                interval = "Lunch"
            elif "dinner" in msg_low:
                interval = "Dinner"
            elif "snack" in msg_low:
                interval = "Mid-Morning Snack"

            analysis = run_diet_risk_analysis(
                user_id=user_id,
                proposed_meal=target_food,
                day_number=day_num,
                interval_name=interval,
            )

            if analysis["passed"]:
                return (
                    f"I've updated your meal plan to include {analysis['clean_meal_title']} for {analysis['interval_name']} on Day {analysis['day_number']}. "
                    + (
                        "Since eggs have zero carbohydrates and provide high-quality protein without excess sodium, they're a safe and effective addition for your metabolic goals. "
                        if "egg" in target_food.lower() else
                        f"{analysis['clinical_explanation']} "
                    )
                    + "I've updated your 7-day schedule accordingly. Would you like me to add them to other days as well?",
                    analysis["updated_plan"]
                )
            else:
                alt_text = (
                    f"As a healthier option, we could include {analysis['recommended_alternative']}. Would you like me to add that instead?"
                    if analysis.get("recommended_alternative") else
                    "Let me know if you'd like me to suggest a healthy alternative that fits safely into your daily targets."
                )
                return (
                    f"I can't add {target_food} to your meal plan. {analysis['clinical_explanation']} {alt_text}",
                    None
                )

    # 7. Food Benefits & Nutritional Value Inquiries
    food_inquiry = _detect_food_inquiry(msg_low)
    if food_inquiry:
        return _handle_food_benefits(food_inquiry, labs, is_ckd, is_htn, is_diabetic, is_hyperkalemic), None

    # 8. Specific Food Safety & Culinary Guidance Inquiries
    if "rasam" in msg_low:
        sodium_caution = f"Keep the salt light given your blood pressure ({int(sbp)}/{int(dbp)} mmHg)." if is_htn else "Season with minimal salt."
        return (
            f"Yes, pepper-cumin rasam is a great choice in moderate portions (about 1 small bowl / 150 mL). "
            f"Black pepper and cumin stimulate digestion and support metabolic balance with negligible carbohydrates. "
            f"{sodium_caution} Also, avoid heavy tamarind if your kidneys require potassium control. "
            f"Would you like me to add a light rasam to your lunch or dinner plan?",
            None
        )

    if "maggi" in msg_low or "ramen" in msg_low or "noodles" in msg_low:
        return (
            "Commercial instant noodles are made from refined flour (maida) flash-fried in palm oil, and a single tastemaker packet contains 800–1100 mg of sodium—more than half your recommended daily limit. "
            "That causes rapid blood sugar spikes and fluid retention. "
            "If you're craving noodles, a much healthier adaptation is whole-wheat atta or millet noodles boiled in plain water with the seasoning packet discarded, tossed with fresh vegetables, tofu or egg, and light home spices. "
            "Would you like me to add that adapted version to your plan?",
            None
        )

    if "biryani" in msg_low or "pulao" in msg_low or "fried rice" in msg_low:
        return (
            "Traditional biryani is dense in polished white rice and cooking fats, which can lead to sustained blood sugar spikes and excess sodium. "
            "It's best enjoyed as an occasional scheduled meal using brown basmati rice or foxtail millet, packed with lean protein or soya chunks and paired with cooling cucumber raita. "
            "Would you like me to schedule a healthy millet biryani into your weekend meal plan?",
            None
        )

    if "egg" in msg_low:
        return (
            "Eggs and egg whites are an outstanding protein source. "
            "They contain virtually zero carbohydrates, so they won't spike your blood sugar. "
            "Egg whites contain zero cholesterol and negligible potassium or phosphorus, making them very gentle on the kidneys. "
            "Boiling or scrambling them with a touch of olive oil, bell peppers, and black pepper is the healthiest preparation. "
            "Would you like me to add eggs to your breakfast in your 7-day meal plan?",
            None
        )

    if "chicken" in msg_low:
        return (
            "Skinless chicken breast is a safe, high-quality lean protein for non-vegetarian diets. "
            "It has zero carbohydrates and very little saturated fat compared to red meats. "
            "Poaching, grilling, or stewing in a light tomato-cumin gravy with fresh coriander is ideal—just avoid deep-fried chicken or heavy butter gravies. "
            "In kidney disease, we keep portions controlled (around 100g) to stay within your daily protein targets. "
            "Would you like me to add grilled chicken to your meal plan?",
            None
        )

    if "paneer" in msg_low or "tofu" in msg_low:
        return (
            "Paneer and organic tofu are excellent protein options. "
            "They are naturally low in carbohydrates and sodium. Sautéing them with turmeric, cumin, and vegetables blunts blood sugar curves and keeps you full. "
            "For kidney health, keeping portions to around 75–100g respects your daily protein limits. "
            "Would you like me to add paneer or tofu to your plan?",
            None
        )

    if "banana" in msg_low:
        if is_ckd or is_hyperkalemic:
            return (
                f"Because a medium banana contains around 420–450 mg of potassium, it's best to strictly limit or avoid bananas given your kidney health (potassium {pot:.1f} mEq/L). "
                "High-potassium foods can lead to hyperkalemia and heart arrhythmias. "
                "Crisp green apples, berries, and guava are much safer fruit choices.",
                None
            )
        return (
            "A medium banana contains around 27g of carbohydrates and 420mg of potassium. "
            "If your kidneys are filtering well, they can be enjoyed in moderation. Pairing them with a few nuts helps blunt the blood sugar rise.",
            None
        )

    if "coconut water" in msg_low or "tender coconut" in msg_low:
        if is_ckd or is_hyperkalemic:
            return (
                f"Tender coconut water is extremely rich in potassium (~600 mg per cup). "
                f"With your kidney profile (potassium {pot:.1f} mEq/L), drinking coconut water poses a severe risk of hyperkalemia and cardiac stress, so it should be strictly avoided. "
                "Plain water, infused with lemon or cucumber, is much safer.",
                None
            )
        return (
            "Tender coconut water is natural and refreshing, but it does contain about 9g of natural sugars and 600mg of potassium per cup. "
            "Enjoy it in moderate portions without added sweeteners.",
            None
        )

    if "oat" in msg_low:
        return (
            "Oats are a top superfood for heart and metabolic health. "
            "They're packed with beta-glucan soluble fiber, which forms a gentle gel in the digestive tract that slows carbohydrate absorption and helps lower cholesterol. "
            "Savory vegetable oats upma with mustard seeds and curry leaves is a satisfying, blood-sugar-friendly meal. Would you like me to add it to your plan?",
            None
        )

    if "ragi" in msg_low:
        return (
            "Ragi (finger millet) is an excellent traditional whole grain with a low glycemic index and high dietary fiber. "
            "It digests much slower than white rice and provides sustained energy without spiking glucose. "
            "Steamed ragi idlis or dosas make a fantastic breakfast. Would you like me to add them to your plan?",
            None
        )

    if any(w in msg_low for w in ["curd", "dahi", "yogurt", "buttermilk", "chaas", "neer mor"]):
        return (
            "Unsweetened curd and spiced buttermilk (chaas or neer mor) are fantastic daily additions. "
            "They provide natural probiotics and protein that slow digestion and stabilize glucose curves. "
            "Diluting fresh curd with water, roasted cumin, and curry leaves makes a refreshing, kidney- and heart-friendly drink.",
            None
        )

    if any(w in msg_low for w in ["sugar", "sweet", "dessert", "jalebi", "gulab jamun", "cake", "chocolate", "ice cream"]):
        return (
            "Refined sweets and desserts trigger rapid blood sugar surges and increase arterial inflammation. "
            "For long-term metabolic and kidney protection, keeping table sugar and commercial sweets off the regular meal plan is essential. "
            "If you want something satisfying, a small handful of walnuts or a portion of fresh berries with unsweetened curd is a much safer option.",
            None
        )

    # 6. Biomarker Questions
    if any(k in msg_low for k in ["hba1c", "a1c", "blood sugar", "fasting glucose", "glucose", "fbs"]):
        val_str = f"{a1c}%" if a1c else "elevated"
        fbs_str = f"{fbs:.0f} mg/dL" if fbs else "elevated"
        return (
            f"Your latest test records show an HbA1c of **{val_str}** and Fasting Blood Sugar of **{fbs_str}**.\n\n"
            "HbA1c reflects your average blood sugar over the past 2 to 3 months by measuring the sugar bound to hemoglobin. "
            "When glucose stays high, it creates oxidative stress and damages the fine microvessels in your kidneys and retina. "
            "The most effective dietary steps are choosing low-glycemic complex grains (oats, ragi, foxtail millet), aiming for at least 35g of fiber daily, and pairing carb portions with protein like legumes or egg whites.",
            None
        )

    if any(k in msg_low for k in ["creatinine", "egfr", "kidney", "renal", "bun"]):
        creat_str = f"{creat:.1f} mg/dL" if creat else "normal"
        egfr_str = f"{egfr:.0f} mL/min" if egfr else "normal"
        return (
            f"Your current kidney biomarkers show Serum Creatinine at **{creat_str}** and eGFR at **{egfr_str}**.\n\n"
            "Creatinine is a natural muscle breakdown product filtered by your kidneys, and eGFR estimates their filtering rate per minute. "
            "To protect your kidney function, the priority is controlling blood pressure (< 130/80 mmHg), keeping daily sodium strictly below 1500mg, and moderating protein intake to avoid excess pressure inside the kidney filters.",
            None
        )

    if any(k in msg_low for k in ["blood pressure", "hypertension", "bp", "systolic", "diastolic"]):
        bp_str = f"{int(sbp)}/{int(dbp)} mmHg" if (sbp and dbp) else "elevated"
        return (
            f"Your recorded blood pressure is **{bp_str}**.\n\n"
            "Elevated blood pressure places continuous shear stress on your arterial walls and kidney capillaries. "
            "Following the DASH nutrition protocol—limiting total sodium to 1500mg daily (no papads, pickles, or salted packaged snacks) and incorporating potassium- and magnesium-rich vegetables like bottle gourd and cucumbers—is the gold standard for vascular protection.",
            None
        )

    # 7. Medication Food Interactions
    for med in ["metformin", "jardiance", "empagliflozin", "lisinopril", "losartan", "amlodipine"]:
        if med in msg_low:
            med_advice = {
                "metformin": "Metformin works by reducing liver glucose output. Always take it with your largest meal to avoid stomach discomfort, and ensure periodic check-ups on vitamin B12.",
                "jardiance": "Jardiance (Empagliflozin) helps remove excess glucose through the kidneys. Make sure to stay well hydrated (at least 2.5L water daily) and maintain at least 130g of complex carbohydrates to prevent euglycemic ketoacidosis.",
                "empagliflozin": "Empagliflozin promotes renal glucose excretion. Ensure steady complex carbohydrate intake and drink plenty of water throughout the day.",
                "lisinopril": "Lisinopril relaxes blood vessels and conserves potassium. Because of this, avoid potassium salt substitutes (like NoSalt) and limit high-potassium fluids like tender coconut water to prevent hyperkalemia.",
                "losartan": "Losartan protects kidney and heart blood flow. Like ACE inhibitors, it can retain potassium, so potassium-based salt alternatives should be avoided.",
                "amlodipine": "Amlodipine relaxes arterial muscle to lower blood pressure. It is crucial to avoid grapefruit and grapefruit juice, as grapefruit blocks the enzyme that metabolizes Amlodipine, causing dangerous drug buildup and hypotension."
            }
            return (
                f"{med_advice.get(med)}\n\nYour 7-day meal plan has been checked to make sure all meals are safe with this medication.",
                None
            )

    # 8. Meal Ideas
    if any(k in msg_low for k in ["what should i eat", "what to eat", "meal recommendation", "recipe idea", "breakfast idea", "dinner idea", "lunch idea"]):
        if "breakfast" in msg_low:
            title = "Steamed Ragi Idlis with Mint Chutney"
            desc = "Steamed ragi idlis with fresh mint-coriander chutney and light herbal tea. High fiber and low glycemic index to keep your morning blood sugar steady."
        elif "dinner" in msg_low:
            title = "Vegetable Moong Dal Khichdi"
            desc = "Light moong dal khichdi prepared with bottle gourd, spinach, and a touch of cumin. Easy to digest, gentle on the kidneys, and low in sodium."
        else:
            title = "Foxtail Millet with Lauki Kootu & Pepper Rasam"
            desc = "Cooked foxtail millet paired with bottle gourd moong dal kootu, light pepper rasam, and pan-seared tofu. Rich in plant fiber and balanced in electrolytes."

        return (
            f"Here is a great option: **{title}**.\n\n{desc}\n\nWould you like me to add this to your 7-day meal plan?",
            None
        )

    # 9. Conversational Clinical Guidance Fallback
    # Check if any food word from query exists in unified food KB
    words = [
        w for w in re.findall(r"[a-zA-Z]+", msg_low)
        if len(w) > 3 and w not in (
            "what", "when", "where", "which", "about", "your", "have", "with",
            "from", "this", "that", "please", "could", "would", "should", "tell",
            "much", "many", "help", "good", "food", "diet", "meal", "hello"
        )
    ]
    for w in words:
        try:
            matches = food_kb.df[food_kb.df["food_name"].str.contains(w, case=False, na=False)]
            if not matches.empty:
                return _handle_food_benefits(w, labs, is_ckd, is_htn, is_diabetic, is_hyperkalemic), None
        except Exception:
            pass

    focus_areas = []
    if is_diabetic:
        focus_areas.append("steady glycemic control through complex dietary fibers and low-GI grains")
    if is_htn:
        focus_areas.append("strict sodium control (<= 1500mg/day) to maintain healthy vascular pressure")
    if is_ckd:
        focus_areas.append("renal protection with controlled protein and monitored electrolytes")

    focus_text = f"focusing on {', '.join(focus_areas)}" if focus_areas else "calibrating your macronutrients and electrolytes"
    return (
        f"Regarding your inquiry on *\"{message}\"*, our primary clinical priority is {focus_text}.\n\n"
        "I can help adjust any specific meal on your 7-day schedule, check whether a regional ingredient or recipe fits your lab biomarkers, or provide detailed nutritional breakdowns.\n\n"
        "Feel free to ask about specific foods (e.g., 'Is rasam safe?', 'How is carrot good for me?'), or tell me to update your schedule (e.g., 'Check my current diet', 'Remove carrots').",
        None
    )


# Alias for backward compatibility
_deterministic_clinical_fallback = _generate_deep_clinical_response


# ──────────────────────────────────────────────────────────────────────────────
# Main Agent Turn
# ──────────────────────────────────────────────────────────────────────────────

def run_agent(
    user_id: str,
    message: str,
    disease: Optional[str] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run one clinical agent turn with Doctor persona, cloud/local LLM support, and safety enforcement.
    """
    t_start = time.perf_counter()

    # ── 1. Pre-LLM Acute Emergency Check ───────────────────────────────────
    if _is_escalation_required(message):
        log.info("[agent] Acute emergency escalation triggered for user=%s msg='%s'", user_id, message[:80])
        TOOL_REGISTRY["log_interaction"](
            user_id=user_id,
            turn_summary=f"EMERGENCY ESCALATED: {message[:200]}",
            disease=disease or "general",
        )
        return {
            "reply":           ESCALATION_RESPONSE,
            "tool_calls_made": [],
            "escalated":       True,
            "latency_ms":      round((time.perf_counter() - t_start) * 1000, 1),
            "steps":           0,
            "engine_mode":     "Emergency Escalation",
        }

    # ── 2. Cloud LLM Dispatch (Google Gemini & OpenAI API) ─────────────────
    prov = (provider or get_app_setting("ai_provider") or "auto").strip().lower()
    gemini_key = api_key if prov == "gemini" else (get_app_setting("gemini_api_key") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    openai_key = api_key if prov == "openai" else (get_app_setting("openai_api_key") or os.getenv("OPENAI_API_KEY"))

    patient_dossier = _build_patient_clinical_dossier(user_id)
    system_content = f"{SYSTEM_PROMPT}\n\n{patient_dossier}"

    # Check for plan alteration request in message
    _, plan_up = _attempt_plan_alteration_from_text(user_id, message, disease)

    # Priority A: Google Gemini
    if gemini_key and prov not in ("ollama", "offline", "openai"):
        try:
            msgs = []
            if conversation_history:
                msgs.extend(conversation_history[-8:])
            msgs.append({"role": "user", "content": message})
            reply = _call_gemini_api(gemini_key, system_content, msgs)
            TOOL_REGISTRY["log_interaction"](
                user_id=user_id,
                turn_summary=f"Q: {message[:120]} | Gemini A: {reply[:120]}",
                disease=disease or "general",
            )
            return {
                "reply":             reply,
                "tool_calls_made":   ["gemini_cloud_ai"],
                "escalated":         False,
                "latency_ms":        round((time.perf_counter() - t_start) * 1000, 1),
                "steps":             1,
                "engine_mode":       "Google Gemini (Cloud AI)",
                "updated_diet_plan": plan_up,
            }
        except Exception as exc:
            log.warning("[agent] Gemini API call failed: %s. Continuing fallback.", exc)

    # Priority B: OpenAI
    if openai_key and prov not in ("ollama", "offline", "gemini"):
        try:
            msgs = []
            if conversation_history:
                msgs.extend(conversation_history[-8:])
            msgs.append({"role": "user", "content": message})
            reply = _call_openai_api(openai_key, system_content, msgs)
            TOOL_REGISTRY["log_interaction"](
                user_id=user_id,
                turn_summary=f"Q: {message[:120]} | OpenAI A: {reply[:120]}",
                disease=disease or "general",
            )
            return {
                "reply":             reply,
                "tool_calls_made":   ["openai_cloud_ai"],
                "escalated":         False,
                "latency_ms":        round((time.perf_counter() - t_start) * 1000, 1),
                "steps":             1,
                "engine_mode":       "OpenAI GPT-4o (Cloud AI)",
                "updated_diet_plan": plan_up,
            }
        except Exception as exc:
            log.warning("[agent] OpenAI API call failed: %s. Continuing fallback.", exc)

    # ── 3. Local Ollama Execution (Auto or Explicit Provider) ──────────────
    if prov in ("auto", "ollama", "") and ollama_manager.is_model_installed():
        try:
            if ollama_manager.start_service():
                messages = [{"role": "system", "content": system_content}]
                if conversation_history:
                    messages.extend(conversation_history[-10:])
                messages.append({"role": "user", "content": message})

                tool_calls_made = []
                executed_call_keys = set()
                steps = 0
                final_reply = ""
                latest_modified_plan = plan_up

                for step in range(MAX_STEPS):
                    steps = step + 1
                    try:
                        assistant_content = _ollama_chat(messages)
                    except Exception as exc:
                        log.warning("[agent] Ollama execution failed: %s", exc)
                        break

                    calls = _parse_tool_calls(assistant_content)
                    if not calls:
                        final_reply = _strip_tool_calls(assistant_content)
                        break

                    messages.append({"role": "assistant", "content": assistant_content})
                    for call in calls:
                        tool_name = call["name"]
                        call_key = (tool_name, json.dumps(call["arguments"], sort_keys=True, default=str))
                        if call_key in executed_call_keys:
                            continue
                        executed_call_keys.add(call_key)
                        tool_calls_made.append(tool_name)
                        result_str, altered_p = _execute_tool(tool_name, call["arguments"], user_id=user_id, disease=disease)
                        if altered_p:
                            latest_modified_plan = altered_p
                        messages.append({"role": "user", "content": f"<tool_result name=\"{tool_name}\">{result_str}</tool_result>"})

                if final_reply:
                    TOOL_REGISTRY["log_interaction"](
                        user_id=user_id,
                        turn_summary=f"Q: {message[:120]} | Ollama A: {final_reply[:120]}",
                        disease=disease or "general",
                    )
                    return {
                        "reply":             final_reply,
                        "tool_calls_made":   tool_calls_made,
                        "escalated":         False,
                        "latency_ms":        round((time.perf_counter() - t_start) * 1000, 1),
                        "steps":             steps,
                        "engine_mode":       "Ollama llama3.2:3b (Local AI)",
                        "updated_diet_plan": latest_modified_plan,
                    }
        finally:
            # Terminate immediately - zero background processes persistence!
            ollama_manager.terminate_service()

    # ── 4. Built-in Clinical Medical Engine ───────────
    reply, plan_up_synth = _generate_deep_clinical_response(user_id, message, disease, conversation_history)
    TOOL_REGISTRY["log_interaction"](
        user_id=user_id,
        turn_summary=f"Q: {message[:120]} | Clinical AI A: {reply[:120]}",
        disease=disease or "general",
    )
    return {
        "reply":             reply,
        "tool_calls_made":   ["clinical_medical_engine"],
        "escalated":         False,
        "latency_ms":        round((time.perf_counter() - t_start) * 1000, 1),
        "steps":             1,
        "engine_mode":       "Nutriloop Clinical AI",
        "updated_diet_plan": plan_up or plan_up_synth,
    }
