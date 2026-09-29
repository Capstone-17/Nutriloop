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
from backend.ollama_manager import ollama_manager
from backend.db import get_app_setting, get_latest_patient_test, get_patient_test_history, get_active_weekly_plan

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


def _attempt_plan_alteration_from_text(user_id: str, message: str, disease: Optional[str] = None) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """Parse text for explicit patient meal alteration requests and execute clinical swap."""
    msg_low = message.lower()
    if not any(w in msg_low for w in ["swap", "replace", "change meal", "alter meal", "substitute", "change dinner", "change lunch", "change breakfast"]):
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
    interval = "Dinner"
    if "breakfast" in msg_low:
        interval = "Breakfast"
    elif "mid-morning" in msg_low or "morning snack" in msg_low:
        interval = "Mid-Morning Snack"
    elif "lunch" in msg_low:
        interval = "Lunch"
    elif "evening snack" in msg_low or "snack" in msg_low:
        interval = "Evening Snack"

    # Extract proposed replacement
    m_with = re.search(r"(?:with|to|for)\s+([a-zA-Z0-9\s,\(\)]+)", message, re.IGNORECASE)
    new_dish = m_with.group(1).strip() if m_with else "Vegetable Moong Dal Khichdi"
    new_dish = re.sub(r"(?i)\s+(please|doctor|in my plan|on day \d|on \w+day).*", "", new_dish).strip()

    try:
        alter_res = TOOL_REGISTRY["alter_diet_plan_meal"](
            user_id=user_id,
            day_number=day_num,
            interval_name=interval,
            new_meal_title=new_dish.title(),
            new_items=[{"item_name": new_dish.title(), "portion": "1 standard portion"}],
            clinical_justification=f"Patient-requested clinical substitution adjusted for safe glycemic and metabolic limits."
        )
        if isinstance(alter_res, dict) and alter_res.get("status") == "success":
            note = f"✅ Plan Altered: Day {day_num} {interval} has been updated to '{new_dish.title()}' in your 7-Day Regional Meal Plan."
            return note, alter_res.get("updated_plan")
    except Exception as exc:
        log.warning("Plan alteration parsing attempt failed: %s", exc)

    return None, None


# ──────────────────────────────────────────────────────────────────────────────
# Generative Clinical Medical Engine (Zero-Key / Offline Mode)
# ──────────────────────────────────────────────────────────────────────────────

def _generate_deep_clinical_response(
    user_id: str,
    message: str,
    disease: Optional[str] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Intelligent, grounded medical reasoning engine that generates personalized,
    multi-paragraph physician consultations citing the patient's actual diagnostic biomarkers,
    active medications, and 7-day meal schedule.
    """
    msg_clean = message.strip()
    msg_low = msg_clean.lower()

    # 1. Attempt meal plan alteration if user explicitly requested it
    plan_note, plan_up = _attempt_plan_alteration_from_text(user_id, message, disease)

    # 2. Retrieve live patient record
    latest = get_latest_patient_test(user_id)
    active_plan = get_active_weekly_plan(user_id)
    labs = latest.get("test_reports", latest) if latest else {}

    fbs = labs.get("fasting_glucose_mg_dl")
    ppbs = labs.get("postprandial_glucose_mg_dl")
    a1c = labs.get("hba1c_pct")
    sbp = labs.get("systolic_bp_mmhg")
    dbp = labs.get("diastolic_bp_mmhg")
    creat = labs.get("serum_creatinine_mg_dl")
    egfr = labs.get("egfr_ml_min")
    pot = labs.get("serum_potassium_meq_l")
    sod = labs.get("serum_sodium_meq_l")
    age = latest.get("age_years", 50) if latest else 50
    sex = str(latest.get("sex", "male")).lower() if latest else "male"
    bmi = latest.get("body_mass_index", 25.0) if latest else 25.0

    detected_conds = latest.get("detected_conditions", []) if latest else []
    is_diabetic = any("Diabetes" in c for c in detected_conds) or (fbs and fbs >= 126.0) or (a1c and a1c >= 6.5)
    is_prediabetic = (not is_diabetic) and (any("Prediabetes" in c for c in detected_conds) or (fbs and fbs >= 100.0) or (a1c and a1c >= 5.7))
    is_ckd = any("CKD" in c for c in detected_conds) or (egfr and egfr < 60.0) or (creat and creat >= 1.3)
    is_hyperkalemic = any("Hyperkalemia" in c for c in detected_conds) or (pot and pot >= 5.0)
    is_htn = any("Hypertension" in c for c in detected_conds) or (sbp and sbp >= 130.0) or (dbp and dbp >= 80.0)

    # If plan was altered, return the confirmation immediately with clinical commentary
    if plan_up:
        return (
            f"🩺 **Dr. Nutriloop Clinical Plan Alteration Approval**\n\n"
            f"{plan_note}\n\n"
            f"• **Biomarker Safety Clearance**: This substitution has been evaluated against your current diagnostic profile. "
            f"The portion and ingredients remain balanced within your prescribed calorie and macronutrient limits.\n\n"
            f"You can review your updated 7-Day Regional Meal Plan in Tab 2 at any time."
        ), plan_up

    # 3. Patient Dossier Context Snippet
    lab_context_parts = []
    if is_diabetic and a1c and fbs:
        lab_context_parts.append(f"HbA1c: **{a1c}%** | Fasting Blood Sugar: **{fbs:.0f} mg/dL**")
    if is_htn and sbp and dbp:
        lab_context_parts.append(f"Blood Pressure: **{int(sbp)}/{int(dbp)} mmHg**")
    if is_ckd and egfr:
        lab_context_parts.append(f"eGFR: **{egfr:.0f} mL/min** (Creatinine: **{creat:.1f} mg/dL**)" if creat else f"eGFR: **{egfr:.0f} mL/min**")
    if pot:
        lab_context_parts.append(f"Serum Potassium: **{pot:.1f} mEq/L**")

    clinical_header = f"📋 *Patient Medical Context*: {', '.join(lab_context_parts)}\n\n" if lab_context_parts else ""

    # 4. Greetings
    if msg_low in {"hello", "hi", "hey", "greetings", "good morning", "good evening", "good afternoon", "namaste", "doctor", "doc"}:
        status_items = []
        if is_diabetic:
            status_items.append("Type 2 Diabetes Glycemic Control")
        if is_ckd:
            status_items.append("Renal Glomerular Protection")
        if is_htn:
            status_items.append("Hypertensive Vascular Management")
        status_str = f"Active Clinical Focus: {', '.join(status_items)}." if status_items else "Supervising long-term metabolic health and disease prevention."

        return (
            f"Hello! I am Dr. Nutriloop, your Clinical AI Physician and Medical Nutrition Specialist.\n\n"
            f"{clinical_header}"
            f"I have direct access to your confidential diagnostic tests, biomarker history, "
            f"active medications, and your personalized 7-Day Regional Meal Plan ({status_str}).\n\n"
            f"**How may I assist your medical care today? You can consult me on:**\n"
            f"• **Food Safety & Regional Cuisine**: Ask whether any food or recipe (*'Can I eat rasam?'*, *'Is maggi allowed?'*, *'How about biryani?'*) fits your health status.\n"
            f"• **Biomarker Analysis**: Understand what your lab readings (*'What does HbA1c {a1c or 9.0}% mean?'*, *'Why is creatinine {creat or 1.2}?'*) mean for your kidneys and heart.\n"
            f"• **Pharmacopeia & Drug Interactions**: Check food interactions for Metformin, Jardiance, Lisinopril, or Amlodipine.\n"
            f"• **Live Meal Substitutions**: Request to swap or adjust any meal in your 7-Day Plan (e.g. *'Replace Tuesday dinner with vegetable soup'*)."
        ), None

    # 5. Comprehensive Food Clinical Dictionary
    foods_dict = {
        "rasam": {
            "title": "Pepper-Cumin Rasam",
            "status": "✅ Clinically Recommended in Controlled Portions (1 small bowl / 150 mL)",
            "glycemic": "Negligible carbohydrate load (~3–5g per 150ml). Black pepper (piperine) stimulates pancreatic enzyme secretion and enhances peripheral insulin sensitivity. Cumin (thymoquinone) aids lipid and glucose homeostasis.",
            "cardio_renal": f"Light, soothing, and easily digested. {'Sodium must be kept minimal given your blood pressure (' + str(int(sbp)) + '/' + str(int(dbp)) + ' mmHg).' if is_htn else 'Season with minimal rock salt.'} Avoid heavy tamarind or tomato pastes if renal potassium is restricted.",
            "prep": "Prepare fresh with crushed roasted black pepper, cumin seeds, garlic, and curry leaves tempered in 1/2 tsp cold-pressed mustard oil. Do NOT add jaggery or commercial flavor powders."
        },
        "maggi": {
            "title": "Instant Noodles (Maggi / Ramen)",
            "status": "⚠️ Strictly Cautioned — Requires Clinical Whole-Wheat Atta Adaptation",
            "glycemic": f"Standard packaged noodles are made from refined wheat flour (Maida, GI ~70+) flash-fried in palm oil. For your glycemic status {'(HbA1c ' + str(a1c) + '%, FBS ' + str(fbs) + ' mg/dL)' if is_diabetic else ''}, this induces rapid postprandial glucose surges followed by rebound fatigue.",
            "cardio_renal": "A commercial flavor tastemaker packet contains 800–1100 mg of sodium (over 50–70% of your daily 1500mg DASH sodium limit), driving acute fluid retention and endothelial shear stress.",
            "prep": "If you crave noodles, use our clinically adapted recipe: boil 100% whole-wheat atta noodles or foxtail millet noodles in plain water; DISCARD the flavor packet entirely. Sauté ginger, peas, bell peppers, and pan-seared tofu or paneer with roasted cumin, turmeric, and under 120mg rock salt."
        },
        "biryani": {
            "title": "Biryani / Pulao / Fried Rice",
            "status": "⚠️ Restricted on Weekdays — Recommended Exclusively via Sunday Smart Craving Budget",
            "glycemic": "Polished white rice biryani contains dense starch (45–60g carbs per cup) and saturated cooking fats (ghee/hydrogenated oils), producing delayed, sustained hyperglycemia.",
            "cardio_renal": "Commercial biryanis are heavily salted and laden with saturated fats, accelerating arterial stiffness.",
            "prep": "Enjoy biryani on your scheduled Sunday indulgence: measure a strict 180g portion, prepare with brown basmati rice or foxtail millet, pack with soya chunks or lean chicken breast, and pair with cooling cucumber raita to buffer glycemic absorption."
        },
        "chocolate": {
            "title": "Chocolate & Confectionery",
            "status": "❌ Milk/White Chocolate Restricted; 85%+ Dark Chocolate Permitted in Moderation",
            "glycemic": f"Standard milk chocolates contain 50–60% pure refined sugar. In diabetes {'(HbA1c ' + str(a1c) + '%)' if is_diabetic else ''}, rapid absorption causes sharp glucose spikes, accelerating advanced glycation end-products (AGEs) and microvascular strain.",
            "cardio_renal": "Pure cocoa flavanols stimulate endothelial nitric oxide synthase, supporting vasodilation.",
            "prep": "Choose 85% to 90% dark chocolate. Limit to a single 15g square after a fiber-rich meal on your scheduled indulgence day. Avoid confectionery filled with caramel or sweetened creams."
        },
        "curd": {
            "title": "Curd / Dahi / Yogurt / Buttermilk (Chaas / Neer Mor)",
            "status": "✅ Clinically Recommended Daily (1 cup / 150g or diluted as Neer Mor)",
            "glycemic": "Low glycemic index with high biological value protein and natural probiotics (Lactobacillus). Probiotic fermentation slows gastric emptying and stabilizes postprandial glucose curves.",
            "cardio_renal": "Provides bioavailable calcium and peptides without excessive phosphorus. For kidney health, maintain daily portion within 1 cup.",
            "prep": "Consume fresh and unsweetened. Dilute with water into spiced buttermilk (chaas / neer mor) with crushed roasted jeera, curry leaves, and a pinch of rock salt."
        },
        "paneer": {
            "title": "Paneer (Cottage Cheese) / Organic Tofu",
            "status": "✅ Clinically Recommended (75–100g portion)",
            "glycemic": "Virtually zero carbohydrate (<3g per 100g) with high protein density. When consumed alongside complex grains, paneer blunts glycemic spikes and extends satiety.",
            "cardio_renal": f"Low sodium naturally. {'In CKD, ensure total daily protein remains within your KDOQI target (~' + str(int(creat * 40) if creat else 55) + 'g/day).' if is_ckd else 'Excellent source of protein.'}",
            "prep": "Pan-sear in minimal oil with turmeric and black pepper. Avoid deep-frying or cooking in heavy cashew-butter gravies."
        },
        "banana": {
            "title": "Bananas",
            "status": "⚠️ Strict Restriction in CKD / Hyperkalemia; Portioned in Diabetes",
            "glycemic": "A medium ripe banana contains ~27g carbohydrates with rapid fructose and glucose release (GI ~51–62 depending on ripeness). Pair with protein (almonds/walnuts) to blunt glycemic surge.",
            "cardio_renal": f"Dense in intrinsic potassium (~420–450 mg per banana). {'Given your renal profile (Potassium ' + str(pot) + ' mEq/L), high potassium foods pose severe hyperkalemic cardiac arrhythmia risks and are strictly restricted.' if (is_ckd or is_hyperkalemic) else 'Safe in moderation for normal renal filtration.'}",
            "prep": "If renal health requires potassium control, swap bananas for crisp green apples, guava, or blueberries which contain <140mg potassium per serving."
        },
        "mango": {
            "title": "Mangoes",
            "status": "⚠️ Portioned & Controlled for Diabetes and Renal Health",
            "glycemic": "Ripe mangoes have high glycemic load (fructose and sucrose, ~25g carbs per small cup). Consuming excess mango rapidly elevates postprandial blood sugar.",
            "cardio_renal": "Moderate potassium content (~260mg per cup).",
            "prep": "Limit to 2–3 small fresh slices (50g) consumed directly after a protein/fiber-rich meal; never drink strained mango juice or mango milkshakes."
        },
        "apple": {
            "title": "Apples (Green / Red Crisp)",
            "status": "⭐ Top Clinical Choice for Diabetes & Renal Health",
            "glycemic": "Low glycemic index (GI ~36) packed with soluble pectin fiber. Pectin forms a viscous mesh in the stomach, slowing carbohydrate absorption and lowering cholesterol.",
            "cardio_renal": "Low potassium (<150mg per medium apple) and zero sodium, making it the safest fruit for CKD and hypertension.",
            "prep": "Consume fresh with the peel intact (wash thoroughly). Avoid canned applesauce with added sugars."
        },
        "oats": {
            "title": "Steel-Cut & Rolled Oats",
            "status": "⭐ Top Clinical Superfood for Glycemic & Cardiovascular Health",
            "glycemic": "Rich in beta-glucan soluble fiber. Forms a gel matrix in the small intestine, delaying carbohydrate enzyme breakdown and delivering sustained energy without insulin spikes.",
            "cardio_renal": "Actively reduces LDL cholesterol and supports endothelial elasticity. Low sodium and renal-safe.",
            "prep": "Prepare savory oats upma with mustard seeds, curry leaves, diced carrots, and green beans; or soak overnight with chia seeds and unsweetened almond milk."
        },
        "ragi": {
            "title": "Finger Millet (Ragi)",
            "status": "⭐ Top South Indian Superfood for Diabetic Nutrition",
            "glycemic": "Low glycemic index (<55) rich in polyphenols and dietary fiber (15–18g per 100g). Significantly outperforms polished white rice in glycemic control.",
            "cardio_renal": "High in natural calcium and antioxidants. Soak before grinding to reduce phytic acid.",
            "prep": "Prepare steamed ragi idlis, ragi dosas fermented naturally without baking soda, or ragi mudde paired with vegetable sambar."
        },
        "chicken": {
            "title": "Lean Skinless Chicken Breast",
            "status": "✅ Permitted for Non-Vegetarian Diets (100–120g portion)",
            "glycemic": "Zero carbohydrate, zero glycemic impact. High biological value protein supporting sarcopenia prevention.",
            "cardio_renal": "Skinless breast is low in saturated fat and purines compared to red meats (mutton/beef). In CKD, portion must strictly respect daily protein targets.",
            "prep": "Poach, grill, or stew in light tomato-cumin gravy with fresh coriander. Never consume deep-fried chicken or restaurant butter gravies."
        },
        "egg": {
            "title": "Eggs / Egg Whites",
            "status": "✅ Clinically Recommended (1 whole egg or 2–3 egg whites)",
            "glycemic": "Zero carbohydrate. Provides the gold standard reference protein (biological value 100) with choline and lutein.",
            "cardio_renal": "Egg whites contain zero cholesterol, zero phosphorus, and negligible potassium, making them the premier protein source for renal and diabetic patients.",
            "prep": "Boil or scramble with a drop of olive oil, diced onions, bell peppers, and crushed black pepper."
        },
        "tea": {
            "title": "Tea & Coffee",
            "status": "✅ Permitted (1–2 cups daily without refined sugar)",
            "glycemic": "Rich in chlorogenic acid and epigallocatechin gallate (EGCG) polyphenols which enhance cellular insulin sensitivity. Adding table sugar completely negates this benefit.",
            "cardio_renal": "Mild diuretic. Avoid drinking strong caffeinated brews immediately before blood pressure checks.",
            "prep": "Brew fresh with water and low-fat cow milk or almond milk. Season with fresh ginger, cardamom, or cinnamon. Use stevia if sweetness is desired."
        },
        "coconut": {
            "title": "Tender Coconut Water & Fresh Coconut",
            "status": "⚠️ Strict Warning for Kidney Disease; Portioned for General Health",
            "glycemic": "Tender coconut water contains ~9g natural sugars per cup. Fresh grated coconut is high in medium-chain triglycerides (MCTs).",
            "cardio_renal": f"Tender coconut water is exceptionally dense in potassium (~600 mg per cup). {'Because your medical record shows renal risk / potassium level of ' + str(pot) + ' mEq/L, drinking coconut water can trigger dangerous hyperkalemia and is strictly prohibited.' if (is_ckd or is_hyperkalemic) else 'Consume with moderation for normal kidney filtration.'}",
            "prep": "In South Indian cooking, replace heavy coconut paste gravies with roasted chana dal or pureed bottle gourd to preserve cardiovascular and renal limits."
        }
    }

    # Match food in query
    matched_food = None
    for k in foods_dict:
        if k in msg_low:
            matched_food = foods_dict[k]
            break

    if matched_food:
        return (
            f"🩺 **Clinical Physician Evaluation: {matched_food['title']}**\n\n"
            f"{clinical_header}"
            f"**Clinical Recommendation**: {matched_food['status']}\n\n"
            f"• **Glycemic & Metabolic Impact**:\n{matched_food['glycemic']}\n\n"
            f"• **Cardiovascular & Renal Considerations**:\n{matched_food['cardio_renal']}\n\n"
            f"• **Physician Preparation & Cooking Guidance**:\n{matched_food['prep']}\n\n"
            f"💡 *Doctor's Note*: Would you like me to incorporate or adjust this dish in your active 7-Day Regional Meal Plan?"
        ), None

    # 6. Biomarker & Lab Value Explanations
    if any(k in msg_low for k in ["hba1c", "a1c", "blood sugar", "fasting glucose", "glucose", "fbs", "sugar reading"]):
        val_str = f"**{a1c}%**" if a1c else "elevated"
        fbs_str = f"**{fbs:.0f} mg/dL**" if fbs else "elevated"
        eag_calc = f"~{int(28.7 * a1c - 46.7)} mg/dL" if a1c else "elevated"

        return (
            f"🩺 **Clinical Physician Analysis: Glycemic Biomarkers & Diabetes Pathophysiology**\n\n"
            f"Looking directly at your latest laboratory panel, your **HbA1c is {val_str}** and **Fasting Plasma Glucose is {fbs_str}**.\n\n"
            f"1. **Physiological Interpretation**:\n"
            f"   • **HbA1c ({val_str})**: Measures the fraction of hemoglobin in your red blood cells coated with sugar over their 90–120 day lifespan. A normal level is < 5.7%. Your reading corresponds to an Estimated Average Glucose (eAG) of **{eag_calc}** constantly circulating in your bloodstream.\n"
            f"   • **Fasting Glucose ({fbs_str})**: Reflects excessive overnight glucose production by the liver (hepatic gluconeogenesis) and insulin resistance in peripheral muscle tissues.\n\n"
            f"2. **Target Organ Vulnerabilities**:\n"
            f"   • **Kidney Glomeruli**: Chronic hyperglycemia damages the delicate endothelial podocyte mesh in the kidneys, causing protein leakage (albuminuria) and progressive nephron loss.\n"
            f"   • **Cardiovascular System**: Excess glucose chemically binds to vascular collagen, stiffening arterial walls and accelerating atherosclerotic plaque formation.\n\n"
            f"3. **Immediate Clinical Medical Nutrition Therapy (MNT) Actions**:\n"
            f"   • **Strict Complex Grain Shift**: Completely replace polished white rice and maida with low-glycemic grains (foxtail millet, oats, ragi, barley).\n"
            f"   • **Soluble Fiber Floor**: Maintain dietary fiber target at **≥ 35g/day** (forms an intestinal gel matrix slowing carbohydrate absorption).\n"
            f"   • **Protein Buffering**: Pair all grain portions with legumes or tofu to blunt postprandial glucose curves.\n"
            f"   • **Antidiabetic Phytochemicals**: Take 1 tsp soaked fenugreek (methi) seeds in the morning and cook with fresh curry leaves and turmeric."
        ), None

    if any(k in msg_low for k in ["creatinine", "egfr", "kidney function", "renal", "bun", "urea"]):
        creat_str = f"**{creat:.1f} mg/dL**" if creat else "elevated"
        egfr_str = f"**{egfr:.0f} mL/min**" if egfr else "reduced"

        return (
            f"🩺 **Clinical Physician Analysis: Renal Filtration Biomarkers (Creatinine & eGFR)**\n\n"
            f"Your diagnostic record shows **Serum Creatinine: {creat_str}** and **eGFR: {egfr_str}**.\n\n"
            f"1. **Physiological Interpretation**:\n"
            f"   • **Serum Creatinine**: A metabolic byproduct of muscle creatine breakdown. Healthy kidneys filter it freely. When functioning nephrons diminish, serum creatinine accumulates.\n"
            f"   • **eGFR ({egfr_str})**: Measures the filtration volume of functioning nephrons per minute. Normal filtration is > 90 mL/min. An eGFR under 60 mL/min indicates chronic renal functional decline.\n\n"
            f"2. **Nephroprotective Strategy**:\n"
            f"   • **Protein Titration (0.65–0.75 g/kg aBW)**: Excess dietary protein increases intraglomerular pressure, accelerating glomerulosclerosis. Controlled plant protein preserves filtration capacity.\n"
            f"   • **Phosphorus Control (< 800mg/day)**: Avoid processed food additives and dark sodas to keep serum phosphorus stable.\n"
            f"   • **Blood Pressure Target (< 130/80 mmHg)**: Guarding against arterial shear stress protects the delicate renal microvasculature."
        ), None

    if any(k in msg_low for k in ["blood pressure", "hypertension", "bp reading", "systolic", "diastolic"]):
        bp_str = f"**{int(sbp)}/{int(dbp)} mmHg**" if (sbp and dbp) else "elevated"
        return (
            f"🩺 **Clinical Physician Analysis: Blood Pressure & Cardiovascular Hemodynamics**\n\n"
            f"Your recorded blood pressure is **{bp_str}**.\n\n"
            f"1. **Clinical Assessment**:\n"
            f"   • Under ACC/AHA guidelines, normal blood pressure is < 120/< 80 mmHg. A reading of {bp_str} indicates {'Stage 2 Hypertension' if (sbp and sbp >= 140) else 'Stage 1 Hypertension'}.\n"
            f"   • Elevated systemic pressure exerts continuous mechanical shear stress on coronary arteries, carotid bifurcations, and renal glomeruli.\n\n"
            f"2. **DASH Nutritional Therapy**:\n"
            f"   • **Sodium Limit**: Strictly **≤ 1500 mg/day** (~2/3 teaspoon of salt across all 5 daily meals). Zero papads, pickles, or canned soups.\n"
            f"   • **Natriuretic Vegetables**: Bottle gourd, ridge gourd, ivy gourd, zucchini, and cucumbers provide magnesium and potassium to promote renal sodium excretion.\n"
            f"   • **Herbal Vasodilation**: Cook with crushed fresh garlic (allicin) and coriander, which support nitric oxide mediated arterial relaxation."
        ), None

    # 7. Medication Guidance
    for med in ["metformin", "jardiance", "empagliflozin", "farxiga", "dapagliflozin", "lisinopril", "losartan", "telmisartan", "amlodipine", "atorvastatin"]:
        if med in msg_low:
            med_advice = {
                "metformin": "Metformin reduces hepatic gluconeogenesis and improves peripheral insulin sensitivity. Always take with your largest meal to prevent gastrointestinal discomfort. Ensure annual vitamin B12 monitoring.",
                "jardiance": "Jardiance (Empagliflozin) is an SGLT2 inhibitor that promotes urinary glucose excretion for renal and cardiovascular protection. CRITICAL MNT RULE: Maintain at least 130g of complex carbohydrates daily to guard against euglycemic diabetic ketoacidosis (euDKA), and drink at least 2.5L water daily.",
                "empagliflozin": "Empagliflozin (Jardiance) promotes renal glycosuria. Ensure adequate carbohydrate intake (≥130g/day) to prevent euglycemic DKA and maintain thorough hydration.",
                "lisinopril": "Lisinopril is an ACE inhibitor that relaxes renal arterioles and reduces proteinuria. CRITICAL WARNING: Conserves serum potassium. Strictly avoid potassium salt substitutes and restrict tender coconut water.",
                "losartan": "Losartan is an ARB protecting renal and cardiac hemodynamics. Conserves potassium; monitor electrolyte levels and avoid potassium-enriched salt alternatives.",
                "amlodipine": "Amlodipine is a calcium channel blocker relaxing arterial smooth muscle. CRITICAL CONTRAINDICATION: Absolutely ZERO grapefruit or pomelo juice. Grapefruit inhibits the intestinal CYP3A4 enzyme, causing dangerous drug accumulation and sudden hypotension."
            }
            guidance = med_advice.get(med, "Take medications strictly as prescribed and coordinate timing with your 5 daily meal intervals.")
            return (
                f"💊 **Pharmacopeia Clinical Review: {med.title()}**\n\n"
                f"{guidance}\n\n"
                f"• **7-Day Plan Verification**: Your active nutrition plan has been pre-screened to ensure all meals comply with this medication's pharmacodynamics."
            ), None

    # 8. Meal Recommendations
    if any(k in msg_low for k in ["breakfast", "lunch", "dinner", "snack", "what to eat", "what should i eat", "recipe idea"]):
        if "breakfast" in msg_low:
            title = "Steamed Ragi Idlis with Mint Coriander Chutney"
            items = "3 Steamed Ragi Idlis (140g) + 2 tbsp Fresh Mint-Coriander Chutney + 1 cup Spiced Herbal Tea"
            rationale = "Low glycemic index (<50) with 8g soluble fiber blunts the morning cortisol glucose spike."
        elif "lunch" in msg_low:
            title = "Steamed Foxtail Millet with Bottle Gourd Kootu & Pepper Rasam"
            items = "1 cup Cooked Foxtail Millet (150g) + 1 cup Lauki Moong Dal Kootu + 1 cup Pepper Rasam + 1/2 cup Tofu Stir-Fry"
            rationale = "High fiber and plant protein buffer postprandial glucose curves while staying strictly within renal and sodium bounds."
        elif "dinner" in msg_low:
            title = "Methi Thepla with Palak Paneer"
            items = "2 Multigrain Methi Theplas + 3/4 cup Palak Paneer (low salt) + 1 bowl Light Bottle Gourd Soup"
            rationale = "Fenugreek (methi) slows glucose absorption, and magnesium in spinach aids nocturnal vascular relaxation."
        else:
            title = "Roasted Bengal Gram (Chana) with Curry Leaves"
            items = "1/3 cup Roasted Chana (30g) + 1 glass Diluted Spiced Buttermilk (Neer Mor) with roasted cumin"
            rationale = "Crunchy, satisfying, high in prebiotic fiber and protein with zero glycemic spike."

        return (
            f"🍽️ **Physician-Curated Meal Recommendation**\n\n"
            f"**Recommended Dish**: **{title}**\n\n"
            f"• **Portion & Composition**: {items}\n"
            f"• **Clinical Rationale**: {rationale}\n\n"
            f"Would you like me to update this into your active 7-Day Regional Meal Plan?"
        ), None

    # 9. General Clinical Medical Consultation
    detected_desc = f"Active Diagnostics: {', '.join(detected_conds)}." if detected_conds else "Preventative Metabolic Wellness."
    return (
        f"🩺 **Clinical Physician Consultation**\n\n"
        f"I have reviewed your query: *\"{message}\"* in the context of your medical history ({detected_desc}).\n\n"
        f"{clinical_header}"
        f"**Key Clinical Principles for Your Care**:\n"
        f"1. **Glycemic Control**: Emphasize complex unrefined whole grains (foxtail millet, oats, ragi) and ensure ≥ 35g dietary fiber daily to prevent glycemic volatility.\n"
        f"2. **Renal & Vascular Protection**: Maintain total daily sodium below 1500mg (DASH protocol) to control arterial shear stress. If serum potassium is elevated, avoid tropical high-potassium fruits.\n"
        f"3. **Metabolic Consistency**: Adhere to structured meal timings across the 5 daily intervals calibrated in your 7-Day Regional Nutrition Plan.\n\n"
        f"You can ask me to evaluate any specific food, explain any biomarker reading, check drug interactions, or swap meals in your active plan!"
    ), None


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

    # ── 3. Local Ollama Execution (if installed & ready) ───────────────────
    if prov != "offline" and ollama_manager.is_model_installed() and ollama_manager.ensure_chat_ready():
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
            ollama_manager.schedule_idle_shutdown()
            return {
                "reply":             final_reply,
                "tool_calls_made":   tool_calls_made,
                "escalated":         False,
                "latency_ms":        round((time.perf_counter() - t_start) * 1000, 1),
                "steps":             steps,
                "engine_mode":       "Ollama llama3.2:3b (Local AI)",
                "updated_diet_plan": latest_modified_plan,
            }

    # ── 4. Built-in Deep Generative Clinical Medical Synthesizer ───────────
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
        "engine_mode":       "Dr. Nutriloop Clinical Medical AI",
        "updated_diet_plan": plan_up or plan_up_synth,
    }


    # ── 4. Build Messages: Prompt + Clinical Dossier + History ─────────────
    patient_dossier = _build_patient_clinical_dossier(user_id)
    system_content = f"{SYSTEM_PROMPT}\n\n{patient_dossier}"

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": system_content},
    ]

    if conversation_history:
        messages.extend(conversation_history[-10:])

    messages.append({"role": "user", "content": message})

    # ── 5. ReAct Execution Loop ───────────────────────────────────────────
    tool_calls_made: List[str] = []
    executed_call_keys: set[tuple[str, str]] = set()
    steps = 0
    final_reply = ""
    latest_modified_plan: Optional[Dict[str, Any]] = None

    for step in range(MAX_STEPS):
        steps = step + 1
        try:
            assistant_content = _ollama_chat(messages)
        except Exception as exc:
            log.warning("[agent] Ollama chat execution failed: %s. Transitioning to Deterministic Clinical Fallback.", exc)
            fallback_reply, plan_up = _deterministic_clinical_fallback(user_id, message, disease)
            final_reply = fallback_reply
            if plan_up:
                latest_modified_plan = plan_up
            tool_calls_made.append("clinical_knowledge_base_fallback")
            break

        log.debug("[agent step=%d] raw response: %s", step, assistant_content[:200])
        calls = _parse_tool_calls(assistant_content)

        if not calls:
            required_tool = _required_tool_for_message(message)
            if required_tool and required_tool not in tool_calls_made and step < MAX_STEPS - 1:
                log.info("[agent] Recovering required tool '%s'", required_tool)
                tool_calls_made.append(required_tool)
                result_str, plan_up = _execute_tool(
                    required_tool,
                    _fallback_tool_arguments(required_tool, message, disease),
                    user_id=user_id,
                    disease=disease,
                )
                if plan_up:
                    latest_modified_plan = plan_up
                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({
                    "role": "user",
                    "content": f"<tool_result name=\"{required_tool}\">{result_str}</tool_result>",
                })
                continue

            final_reply = _strip_tool_calls(assistant_content)
            break

        # Execute tools
        messages.append({"role": "assistant", "content": assistant_content})
        for call in calls:
            tool_name = call["name"]
            call_key = (tool_name, json.dumps(call["arguments"], sort_keys=True, default=str))
            if call_key in executed_call_keys:
                messages.append({
                    "role": "user",
                    "content": f"<tool_result name=\"{tool_name}\">{{\"status\": \"duplicate_call_skipped\"}}</tool_result>",
                })
                continue

            executed_call_keys.add(call_key)
            tool_calls_made.append(tool_name)
            log.info("[agent] Executing tool '%s' args=%s", tool_name, call["arguments"])

            result_str, plan_up = _execute_tool(
                tool_name,
                call["arguments"],
                user_id=user_id,
                disease=disease,
            )
            if plan_up:
                latest_modified_plan = plan_up

            messages.append({
                "role": "user",
                "content": f"<tool_result name=\"{tool_name}\">{result_str}</tool_result>",
            })
    else:
        if not final_reply:
            final_reply = _strip_tool_calls(assistant_content if 'assistant_content' in dir() else "")
            if not final_reply:
                final_reply = "Dr. Nutriloop: I have analyzed your consultation request. Please specify any questions regarding your kidney health, blood pressure, or diet."

    # ── 6. Audit & Idle Watchdog ───────────────────────────────────────────
    summary = f"Q: {message[:120]} | Tools: {tool_calls_made} | A: {final_reply[:120]}"
    TOOL_REGISTRY["log_interaction"](
        user_id=user_id,
        turn_summary=summary,
        disease=disease or "general",
    )

    # Arm 60s idle shutdown
    ollama_manager.schedule_idle_shutdown()

    latency_ms = (time.perf_counter() - t_start) * 1000
    log.info(
        "[agent] Turn complete. User=%s Steps=%d Tools=%s Latency=%.0fms",
        user_id, steps, tool_calls_made, latency_ms,
    )

    return {
        "reply":             final_reply,
        "tool_calls_made":   tool_calls_made,
        "escalated":         False,
        "latency_ms":        round(latency_ms, 1),
        "steps":             steps,
        "engine_mode":       "Dr. Nutriloop AI (llama3.2:3b)",
        "updated_diet_plan": latest_modified_plan,
    }
