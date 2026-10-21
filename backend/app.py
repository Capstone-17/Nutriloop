import os
import sys

# Globally prevent Python from writing .pyc files or creating __pycache__ directories
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
import json

from backend.db import (
    get_risk_explanations,
    get_risk_explanation_summary,
    get_open_alert_count,
    init_db,
    insert_alert,
    insert_diet_plan,
    insert_meal_log,
    insert_risk_explanation,
    insert_risk_profile,
)
from backend.model_registry import registry
from backend.raw_input import get_raw_template, map_raw_payload
from backend.reporting import build_explanation_text, build_report_text, recommend_foods
from backend.rules import (
    assess_meal_deviation,
    build_calibration_context,
    build_plan,
    calibrate_disease_risk,
    classify_risk_level,
)
from backend.schemas import (
    PredictRiskRawRequest,
    PredictRiskRawResponse,
    LogMealRequest,
    LogMealResponse,
    PredictRiskRequest,
    PredictRiskResponse,
    RiskExplanationRawRequest,
    RiskExplanationRawResponse,
    RiskExplanationLogListResponse,
    RiskReportRawRequest,
    RiskReportRawResponse,
    ChatbotRequest,
    ChatbotResponse,
    RiskReportRequest,
    RiskReportResponse,
    RecommendPlanRequest,
    RecommendPlanResponse,
    # Agentic AI schemas
    AgentRequest,
    AgentResponse,
    SafetyValidationRequest,
    SafetyValidationResponse,
    MealLogRequest as AdaptationMealLogRequest,
    MealLogResponse as AdaptationMealLogResponse,
    AdaptationSummaryResponse,
    FeedbackRequest,
    FeedbackResponse,
    HealthOutcomeRequest,
    HealthOutcomeResponse,
    MedicalGuidelineResponse,
    DrugInteractionResponse,
    WeeklyDietPlanRequest,
    WeeklyDietPlanResponse,
)

# Agentic AI imports
from backend.agent_engine import agent_engine, UserProfile as AgentUserProfile
from backend.safety_engine import safety_engine
from backend.adaptation_engine import adaptation_engine
from backend.feedback_learning import feedback_collector, outcome_tracker, learning_engine, FeedbackType, FeedbackSource, OutcomeType
from backend.medical_knowledge import medical_knowledge_base
from backend.chatbot.agent import run_agent
from backend.weekly_diet_engine import weekly_diet_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    registry.load()
    yield


app = FastAPI(
    title="A Deep Learning and Generative AI-Driven Diet Recommendation System for Personalized Chronic Disease Management",
    version="0.1.0",
    lifespan=lifespan,
)

# Load root .env file if present
_env_file = Path(__file__).resolve().parent.parent / ".env"
if _env_file.exists():
    try:
        with open(_env_file, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if not _line or _line.startswith("#") or "=" not in _line:
                    continue
                _k, _v = _line.split("=", 1)
                _k = _k.strip()
                _v = _v.strip().strip("'\"")
                if _k and _k not in os.environ:
                    os.environ[_k] = _v
    except Exception as _e:
        logger.warning(f"Failed to parse .env file: {_e}")

# Enable CORS for mobile clients, local development, and production endpoints
_cors_origins_env = os.getenv("CORS_ALLOWED_ORIGINS", "*")
_allowed_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins if _allowed_origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _read_project_model_metrics() -> List[dict]:
    base_dir = Path(__file__).resolve().parent.parent
    json_path = base_dir / "artifacts" / "risk_thresholds_and_factors.json"
    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        rows = []
        for ds, p in data.items():
            m = p.get("metrics", {})
            rows.append({
                "dataset": ds,
                "model": p.get("model_name", ""),
                "accuracy": float(m.get("accuracy", 0.0)),
                "macro_f1": float(m.get("macro_f1", 0.0)),
                "roc_auc": float(m.get("roc_auc", 0.0)),
                "pr_auc": float(m.get("pr_auc", 0.0)),
                "precision_pos": float(m.get("precision_pos", 0.0)),
                "recall_pos": float(m.get("recall_pos", 0.0)),
                "specificity": float(m.get("specificity", 0.0)),
                "brier_score": float(m.get("brier_score", 0.0)),
            })
        return sorted(rows, key=lambda r: r.get("dataset", ""))
    return []


def _count_generated_charts() -> int:
    return 0


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "models_loaded": sorted(list(registry.models.keys())),
        "open_alerts": get_open_alert_count(),
    }


@app.get("/implementation-progress")
def implementation_progress() -> dict:
    registry.load_feature_metadata()
    models_available = sorted(list(registry.features.keys()))
    models_loaded = sorted(list(registry.models.keys()))

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "models_available": models_available,
        "models_loaded": models_loaded,
        "open_alerts": get_open_alert_count(),
        "audit_summary": get_risk_explanation_summary(),
        "project_model_metrics": _read_project_model_metrics(),
        "generated_model_comparison_charts": _count_generated_charts(),
    }


@app.get("/raw-input-template/{disease}")
def raw_input_template(disease: str) -> dict:
    try:
        return get_raw_template(disease)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex


@app.post("/predict-risk", response_model=PredictRiskResponse)
def predict_risk(req: PredictRiskRequest) -> PredictRiskResponse:
    try:
        pred, score, model_name = registry.predict(req.disease, req.features)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex

    if req.user_id:
        insert_risk_profile(req.user_id, req.disease, score, pred)

    profile_cfg = registry.get_risk_profile(req.disease)
    thresholds = profile_cfg.get("thresholds", {})
    threshold_used = float(thresholds.get("moderate", 0.5))
    predicted_class = int(1 if score >= threshold_used else 0)
    risk_level = classify_risk_level(score, thresholds)
    calibration_context = build_calibration_context(
        disease=req.disease,
        risk_score=score,
        thresholds=thresholds,
        top_factors=profile_cfg.get("top_factors", []),
        transformed_features=req.features,
    )

    return PredictRiskResponse(
        disease=req.disease,
        predicted_class=predicted_class,
        risk_score=round(score, 6),
        risk_level=risk_level,
        threshold_used=round(threshold_used, 6),
        thresholds={
            "moderate": round(float(thresholds.get("moderate", 0.5)), 6),
            "high": round(float(thresholds.get("high", 0.75)), 6),
        },
        threshold_band=str(calibration_context.get("threshold_band", "below_moderate")),
        major_risk_factors=list(calibration_context.get("major_risk_factors", [])),
        model_name=model_name,
    )


@app.post("/predict-risk-raw", response_model=PredictRiskRawResponse)
def predict_risk_raw(req: PredictRiskRawRequest) -> PredictRiskRawResponse:
    try:
        mapped = map_raw_payload(req.disease, req.raw_inputs)
        pred, raw_score, model_name = registry.predict(req.disease, mapped.transformed_features)
        score = calibrate_disease_risk(req.disease, raw_score, req.raw_inputs)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex

    if req.user_id:
        insert_risk_profile(req.user_id, req.disease, score, pred)

    profile_cfg = registry.get_risk_profile(req.disease)
    thresholds = profile_cfg.get("thresholds", {})
    threshold_used = float(thresholds.get("moderate", 0.5))
    predicted_class = int(1 if score >= threshold_used else 0)
    risk_level = classify_risk_level(score, thresholds)
    calibration_context = build_calibration_context(
        disease=req.disease,
        risk_score=score,
        thresholds=thresholds,
        top_factors=profile_cfg.get("top_factors", []),
        transformed_features=mapped.transformed_features,
    )

    return PredictRiskRawResponse(
        disease=req.disease,
        predicted_class=predicted_class,
        risk_score=round(score, 6),
        risk_level=risk_level,
        threshold_used=round(threshold_used, 6),
        thresholds={
            "moderate": round(float(thresholds.get("moderate", 0.5)), 6),
            "high": round(float(thresholds.get("high", 0.75)), 6),
        },
        threshold_band=str(calibration_context.get("threshold_band", "below_moderate")),
        major_risk_factors=list(calibration_context.get("major_risk_factors", [])),
        model_name=model_name,
        transformed_features=mapped.transformed_features,
        raw_inputs=mapped.raw_inputs,
        validation_warnings=mapped.validation_warnings,
    )


@app.post("/risk-explanation-raw", response_model=RiskExplanationRawResponse)
def risk_explanation_raw(req: RiskExplanationRawRequest) -> RiskExplanationRawResponse:
    try:
        mapped = map_raw_payload(req.disease, req.raw_inputs)
        pred, score, model_name = registry.predict(req.disease, mapped.transformed_features)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex

    if req.user_id:
        insert_risk_profile(req.user_id, req.disease, score, pred)

    profile_cfg = registry.get_risk_profile(req.disease)
    thresholds = profile_cfg.get("thresholds", {})
    top_factors = profile_cfg.get("top_factors", [])
    threshold_used = float(thresholds.get("moderate", 0.5))
    predicted_class = int(1 if score >= threshold_used else 0)
    risk_level = classify_risk_level(score, thresholds)
    calibration_context = build_calibration_context(
        disease=req.disease,
        risk_score=score,
        thresholds=thresholds,
        top_factors=top_factors,
        transformed_features=mapped.transformed_features,
    )
    explanation_text = build_explanation_text(
        disease=req.disease,
        risk_score=score,
        risk_level=risk_level,
        threshold_band=str(calibration_context.get("threshold_band", "below_moderate")),
        major_risk_factors=list(calibration_context.get("major_risk_factors", [])),
        validation_warnings=mapped.validation_warnings,
    )

    insert_risk_explanation(
        disease=req.disease,
        model_name=model_name,
        predicted_class=predicted_class,
        risk_score=score,
        risk_level=risk_level,
        threshold_moderate=float(thresholds.get("moderate", 0.5)),
        threshold_high=float(thresholds.get("high", 0.75)),
        threshold_band=str(calibration_context.get("threshold_band", "below_moderate")),
        major_risk_factors=list(calibration_context.get("major_risk_factors", [])),
        validation_warnings=mapped.validation_warnings,
        raw_inputs=mapped.raw_inputs,
        transformed_features=mapped.transformed_features,
        top_factors=top_factors,
        calibration_context=calibration_context,
        explanation_text=explanation_text,
        user_id=req.user_id,
        source="api_risk_explanation_raw",
    )

    return RiskExplanationRawResponse(
        disease=req.disease,
        predicted_class=predicted_class,
        risk_score=round(score, 6),
        risk_level=risk_level,
        threshold_used=round(threshold_used, 6),
        thresholds={
            "moderate": round(float(thresholds.get("moderate", 0.5)), 6),
            "high": round(float(thresholds.get("high", 0.75)), 6),
        },
        threshold_band=str(calibration_context.get("threshold_band", "below_moderate")),
        major_risk_factors=list(calibration_context.get("major_risk_factors", [])),
        model_name=model_name,
        transformed_features=mapped.transformed_features,
        raw_inputs=mapped.raw_inputs,
        validation_warnings=mapped.validation_warnings,
        top_factors=top_factors,
        calibration_context=calibration_context,
        explanation_text=explanation_text,
    )


@app.get("/risk-explanations", response_model=RiskExplanationLogListResponse)
def risk_explanations(
    disease: Optional[str] = None,
    user_id: Optional[str] = None,
    source: Optional[str] = None,
    from_ts: Optional[str] = None,
    to_ts: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> RiskExplanationLogListResponse:
    items = get_risk_explanations(
        disease=disease,
        user_id=user_id,
        source=source,
        from_ts=from_ts,
        to_ts=to_ts,
        limit=limit,
        offset=offset,
    )
    return RiskExplanationLogListResponse(
        count=len(items),
        limit=limit,
        offset=offset,
        items=items,
    )


@app.post("/recommend-plan", response_model=RecommendPlanResponse)
def recommend_plan(req: RecommendPlanRequest) -> RecommendPlanResponse:
    disease_key = req.disease or ("_".join(req.diseases) if req.diseases else "ckd")
    clean_diseases = req.diseases or [disease_key]
    profile_cfg = registry.get_risk_profile(clean_diseases[0] if clean_diseases[0] in ["ckd", "hypertension", "diabetes"] else "ckd")
    thresholds = profile_cfg.get("thresholds", {})
    calibration_context = build_calibration_context(
        disease=disease_key,
        risk_score=req.risk_score,
        thresholds=thresholds,
        top_factors=profile_cfg.get("top_factors", []),
        transformed_features={},
    )
    plan = build_plan(
        disease=disease_key,
        risk_score=req.risk_score,
        profile=req.profile,
        thresholds=thresholds,
        calibration_context=calibration_context,
        diseases=req.diseases,
    )
    insert_diet_plan(req.user_id, disease_key, plan)

    return RecommendPlanResponse(
        user_id=req.user_id,
        disease=disease_key,
        diseases=clean_diseases,
        **plan,
    )


@app.post("/log-meal", response_model=LogMealResponse)
def log_meal(req: LogMealRequest) -> LogMealResponse:
    result = assess_meal_deviation(req.planned_calories, req.consumed_calories)
    meal_log_id = insert_meal_log(
        user_id=req.user_id,
        planned_calories=req.planned_calories,
        consumed_calories=req.consumed_calories,
        deviation_flag=result["deviation_flag"],
        deviation_percent=result["deviation_percent"],
        notes=req.notes,
    )

    alert_created = False
    alert_message = None

    if result["deviation_flag"]:
        severity = "moderate" if result["deviation_percent"] < 25.0 else "high"
        alert_message = (
            f"Meal deviation detected: {result['deviation_percent']}% "
            f"({severity} severity)."
        )
        insert_alert(req.user_id, severity, alert_message)
        alert_created = True

    return LogMealResponse(
        meal_log_id=meal_log_id,
        user_id=req.user_id,
        deviation_flag=result["deviation_flag"],
        deviation_percent=result["deviation_percent"],
        alert_created=alert_created,
        alert_message=alert_message,
    )



@app.post("/risk-report", response_model=RiskReportResponse)
def risk_report(req: RiskReportRequest) -> RiskReportResponse:
    try:
        pred, score, model_name = registry.predict(req.disease, req.features)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex

    profile_cfg = registry.get_risk_profile(req.disease)
    thresholds = profile_cfg.get("thresholds", {"moderate": 0.4, "high": 0.75})
    top_factors = profile_cfg.get("top_factors", [])

    threshold_used = float(thresholds.get("moderate", 0.5))
    predicted_class = int(1 if score >= threshold_used else 0)
    risk_level = classify_risk_level(score, thresholds)

    calibration_context = build_calibration_context(
        disease=req.disease,
        risk_score=score,
        thresholds=thresholds,
        top_factors=top_factors,
        transformed_features=req.features,
    )
    plan = build_plan(req.disease, score, req.profile, thresholds, calibration_context)
    foods = recommend_foods(req.disease, risk_level, plan, top_n=req.top_n_foods)
    narrative = build_report_text(req.disease, score, risk_level, top_factors, calibration_context)

    if req.user_id:
        insert_risk_profile(req.user_id, req.disease, score, pred)
        insert_diet_plan(req.user_id, req.disease, plan)

    return RiskReportResponse(
        disease=req.disease,
        predicted_class=predicted_class,
        risk_score=round(score, 6),
        risk_level=risk_level,
        model_name=model_name,
        thresholds={
            "moderate": round(float(thresholds.get("moderate", 0.4)), 6),
            "high": round(float(thresholds.get("high", 0.75)), 6),
        },
        top_factors=top_factors,
        calibration_context=calibration_context,
        plan=plan,
        recommended_foods=foods,
        report_text=narrative,
    )


@app.post("/risk-report-raw", response_model=RiskReportRawResponse)
def risk_report_raw(req: RiskReportRawRequest) -> RiskReportRawResponse:
    try:
        mapped = map_raw_payload(req.disease, req.raw_inputs)
        pred, score, model_name = registry.predict(req.disease, mapped.transformed_features)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex

    profile_cfg = registry.get_risk_profile(req.disease)
    thresholds = profile_cfg.get("thresholds", {"moderate": 0.4, "high": 0.75})
    top_factors = profile_cfg.get("top_factors", [])

    threshold_used = float(thresholds.get("moderate", 0.5))
    predicted_class = int(1 if score >= threshold_used else 0)
    risk_level = classify_risk_level(score, thresholds)

    calibration_context = build_calibration_context(
        disease=req.disease,
        risk_score=score,
        thresholds=thresholds,
        top_factors=top_factors,
        transformed_features=mapped.transformed_features,
    )
    plan = build_plan(req.disease, score, req.profile, thresholds, calibration_context)
    foods = recommend_foods(req.disease, risk_level, plan, top_n=req.top_n_foods)
    narrative = build_report_text(req.disease, score, risk_level, top_factors, calibration_context)

    if req.user_id:
        insert_risk_profile(req.user_id, req.disease, score, pred)
        insert_diet_plan(req.user_id, req.disease, plan)

    return RiskReportRawResponse(
        disease=req.disease,
        predicted_class=predicted_class,
        risk_score=round(score, 6),
        risk_level=risk_level,
        model_name=model_name,
        thresholds={
            "moderate": round(float(thresholds.get("moderate", 0.4)), 6),
            "high": round(float(thresholds.get("high", 0.75)), 6),
        },
        top_factors=top_factors,
        calibration_context=calibration_context,
        plan=plan,
        recommended_foods=foods,
        report_text=narrative,
        transformed_features=mapped.transformed_features,
        raw_inputs=mapped.raw_inputs,
        validation_warnings=mapped.validation_warnings,
    )


@app.post("/assess-patient")
def assess_patient_endpoint(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Unified multi-disease risk evaluation and clinical assessment.
    Provides identical diagnostic accuracy across PC and Android interfaces.
    """
    from desktop_api import DesktopAPI
    api = DesktopAPI()
    return api.assess_patient(payload)


# ==================== Agentic AI Endpoints ====================

@app.post("/agent/chat", response_model=AgentResponse)
def agent_chat(req: AgentRequest) -> AgentResponse:
    """Process user query through agentic AI engine"""
    try:
        # Convert schema to internal agent profile
        agent_profile = AgentUserProfile(
            user_id=req.user_profile.user_id,
            disease=req.user_profile.disease,
            risk_level=req.user_profile.risk_level,
            dietary_preferences=req.user_profile.dietary_preferences,
            allergies=req.user_profile.allergies,
            medications=req.user_profile.medications,
            calorie_target=req.user_profile.calorie_target,
            cultural_preferences=req.user_profile.cultural_preferences,
            cooking_skill=req.user_profile.cooking_skill,
            time_constraints=req.user_profile.time_constraints
        )
        
        # Process query through agent engine
        agent_response = agent_engine.process_user_query(
            user_message=req.user_message,
            user_id=req.user_id,
            user_profile=agent_profile
        )
        
        # Convert internal response to API response
        return AgentResponse(
            intent=agent_response.intent.value,
            content=agent_response.content,
            meal_plans=[
                {
                    "meal_type": meal.meal_type.value,
                    "meal_name": meal.meal_name,
                    "ingredients": meal.ingredients,
                    "instructions": meal.instructions,
                    "nutritional_info": meal.nutritional_info,
                    "preparation_time": meal.preparation_time,
                    "difficulty": meal.difficulty,
                    "safety_score": meal.safety_score,
                    "medical_compliance": meal.medical_compliance,
                    "substitutions": meal.substitutions
                }
                for meal in agent_response.meal_plans
            ],
            safety_alerts=agent_response.safety_alerts,
            recommendations=agent_response.recommendations,
            follow_up_questions=agent_response.follow_up_questions,
            confidence=agent_response.confidence,
            requires_medical_supervision=agent_response.requires_medical_supervision
        )
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex)) from ex


@app.post("/chatbot/chat", response_model=ChatbotResponse)
def chatbot_chat(req: ChatbotRequest) -> ChatbotResponse:
    """Run the grounded general-wellness chatbot layer."""
    try:
        result = run_agent(
            user_id=req.user_id,
            message=req.message,
            disease=req.disease,
            conversation_history=req.conversation_history,
        )
        return ChatbotResponse(**result)
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex)) from ex


@app.post("/safety/validate", response_model=SafetyValidationResponse)
def validate_safety(req: SafetyValidationRequest) -> SafetyValidationResponse:
    """Validate meal or daily plan against medical constraints"""
    try:
        if req.validation_type == "meal":
            validation_result = safety_engine.validate_meal(
                meal_data=req.meal_data,
                disease=req.disease,
                user_medications=req.user_medications,
                risk_level=req.risk_level
            )
        else:  # daily_plan
            validation_result = safety_engine.validate_daily_plan(
                daily_totals=req.meal_data,
                disease=req.disease,
                user_medications=req.user_medications,
                risk_level=req.risk_level
            )
        
        return SafetyValidationResponse(
            is_safe=validation_result.is_safe,
            safety_score=validation_result.safety_score,
            violations=[
                {
                    "constraint_type": v.constraint_type,
                    "current_value": v.current_value,
                    "limit_value": v.limit_value,
                    "severity": v.severity.value,
                    "message": v.message,
                    "recommendation": v.recommendation
                }
                for v in validation_result.violations
            ],
            warnings=validation_result.warnings,
            adjusted_values=validation_result.adjusted_values,
            medical_compliance={
                k: v for k, v in validation_result.adjusted_values.items()
                if k in req.meal_data
            }
        )
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex)) from ex


@app.post("/adaptation/log-meal", response_model=AdaptationMealLogResponse)
def log_meal_adaptation(req: AdaptationMealLogRequest) -> AdaptationMealLogResponse:
    """Log meal with adaptation and deviation detection"""
    try:
        meal_log = adaptation_engine.log_meal(
            user_id=req.user_id,
            meal_type=req.meal_type.value,
            planned_calories=req.planned_calories,
            consumed_calories=req.consumed_calories,
            planned_nutrients=req.planned_nutrients,
            consumed_nutrients=req.consumed_nutrients,
            planned_time=req.planned_time,
            actual_time=req.actual_time,
            notes=req.notes
        )
        
        return AdaptationMealLogResponse(
            meal_id=meal_log.meal_id,
            deviation_detected=meal_log.deviation_detected,
            deviation_type=meal_log.deviation_type,
            deviation_severity=meal_log.deviation_severity.value,
            adaptation_triggered=len(adaptation_engine.get_user_adaptations(req.user_id)) > 0,
            alert_generated=len(adaptation_engine.get_user_alerts(req.user_id)) > 0
        )
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex)) from ex


@app.get("/adaptation/summary/{user_id}", response_model=AdaptationSummaryResponse)
def get_adaptation_summary(user_id: str) -> AdaptationSummaryResponse:
    """Get adaptation summary for a user"""
    try:
        summary = adaptation_engine.get_adaptation_summary(user_id)
        
        return AdaptationSummaryResponse(
            user_id=summary["user_id"],
            active_adaptations=summary["active_adaptations"],
            pending_adaptations=summary["pending_adaptations"],
            unresolved_alerts=summary["unresolved_alerts"],
            recent_alerts=summary["recent_alerts"],
            learned_patterns=summary["learned_patterns"],
            pattern_summary=summary["pattern_summary"],
            recent_meal_count=summary["recent_meal_count"],
            adherence_rate=summary["adherence_rate"]
        )
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex)) from ex


@app.post("/feedback/submit", response_model=FeedbackResponse)
def submit_feedback(req: FeedbackRequest) -> FeedbackResponse:
    """Submit user feedback for learning"""
    try:
        feedback_type_map = {
            "meal_rating": FeedbackType.MEAL_RATING,
            "satisfaction": FeedbackType.SATISFACTION,
            "adherence": FeedbackType.ADHERENCE,
            "symptom_report": FeedbackType.SYMPTOM_REPORT,
            "suggestion": FeedbackType.SUGGESTION,
            "complaint": FeedbackType.COMPLAINT
        }
        
        feedback = feedback_collector.collect_feedback(
            user_id=req.user_id,
            feedback_type=feedback_type_map.get(req.feedback_type, FeedbackType.SATISFACTION),
            source=FeedbackSource.USER_APP,
            rating=req.rating,
            text_feedback=req.text_feedback,
            meal_id=req.meal_id,
            recommendation_id=req.recommendation_id,
            metadata=req.metadata
        )
        
        # Generate learning events
        learning_events = learning_engine.analyze_feedback_patterns(
            {req.user_id: [feedback]}
        )
        learning_engine.learning_events.extend(learning_events)
        
        return FeedbackResponse(
            feedback_id=feedback.feedback_id,
            acknowledged=True,
            impact_on_recommendations="processed_for_learning"
        )
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex)) from ex


@app.post("/outcomes/record", response_model=HealthOutcomeResponse)
def record_health_outcome(req: HealthOutcomeRequest) -> HealthOutcomeResponse:
    """Record health outcome for correlation analysis"""
    try:
        outcome_type_map = {
            "weight_change": OutcomeType.WEIGHT_CHANGE,
            "blood_pressure_change": OutcomeType.BLOOD_PRESSURE_CHANGE,
            "blood_glucose_change": OutcomeType.BLOOD_GLUCOSE_CHANGE,
            "kidney_function_change": OutcomeType.KIDNEY_FUNCTION_CHANGE,
            "symptom_improvement": OutcomeType.SYMPTOM_IMPROVEMENT
        }
        
        outcome = outcome_tracker.record_outcome(
            user_id=req.user_id,
            outcome_type=outcome_type_map.get(req.outcome_type, OutcomeType.SYMPTOM_IMPROVEMENT),
            value=req.value,
            unit=req.unit,
            measurement_context=req.measurement_context
        )
        
        # Get trend analysis
        trend_analysis = outcome_tracker.get_outcome_trends(req.user_id, outcome_type_map.get(req.outcome_type))
        
        return HealthOutcomeResponse(
            outcome_id=outcome.outcome_id,
            clinical_significance=outcome.clinical_significance,
            change_from_baseline=outcome.change_from_baseline,
            trend_analysis=trend_analysis
        )
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex)) from ex


@app.get("/medical/guidelines", response_model=MedicalGuidelineResponse)
def get_medical_guidelines(disease: str, condition: Optional[str] = None) -> MedicalGuidelineResponse:
    """Get medical guidelines for a disease"""
    try:
        guidelines = medical_knowledge_base.get_guidelines(disease, condition)
        
        guideline_data = [
            {
                "guideline_id": g.guideline_id,
                "source": g.source.value,
                "year": g.year,
                "disease": g.disease,
                "condition": g.condition,
                "recommendation": g.recommendation,
                "evidence_level": g.evidence_level.value,
                "recommendation_strength": g.recommendation_strength.value,
                "target_population": g.target_population,
                "exceptions": g.exceptions,
                "references": g.references
            }
            for g in guidelines
        ]
        
        summary = medical_knowledge_base.get_guideline_summary(disease)
        
        return MedicalGuidelineResponse(
            guidelines=guideline_data,
            summary=summary
        )
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex)) from ex


@app.get("/medical/drug-interactions/{drug_name}", response_model=DrugInteractionResponse)
def get_drug_interactions(drug_name: str) -> DrugInteractionResponse:
    """Get drug-food interactions for a medication"""
    try:
        interactions = medical_knowledge_base.get_drug_interactions(drug_name)
        
        interaction_data = [
            {
                "interaction_id": i.interaction_id,
                "drug_name": i.drug_name,
                "drug_category": i.drug_category,
                "food_components": i.food_components,
                "interaction_type": i.interaction_type,
                "severity": i.severity,
                "mechanism": i.mechanism,
                "clinical_significance": i.clinical_significance,
                "management": i.management,
                "alternatives": i.alternatives
            }
            for i in interactions
        ]
        
        severity_summary = {}
        for interaction in interactions:
            severity_summary[interaction.severity] = severity_summary.get(interaction.severity, 0) + 1
        
        return DrugInteractionResponse(
            interactions=interaction_data,
            severity_summary=severity_summary
        )
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex)) from ex


@app.get("/learning/summary")
def get_learning_summary() -> Dict[str, Any]:
    """Get system learning summary"""
    try:
        return learning_engine.get_learning_summary()
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex)) from ex


@app.post("/recommend-weekly-plan", response_model=WeeklyDietPlanResponse)
def recommend_weekly_plan(req: WeeklyDietPlanRequest) -> WeeklyDietPlanResponse:
    """
    Generate a personalized 7-day, 5-interval medical nutrition plan based on:
    - Patient's latest test reports (creatinine, HbA1c, glucose, BP, lipid panel, or summary text)
    - Native place / regional culinary traditions (South Indian, North Indian, Gujarati, Bengali, etc.)
    - Individual dietary preferences, interests, allergies, dislikes, and cooking skill
    - Active medications cross-referenced against 18+ drug pharmacopeia
    """
    try:
        plan = weekly_diet_engine.generate_weekly_plan(req)
        if req.user_id:
            insert_diet_plan(
                user_id=req.user_id,
                disease="_".join([c.replace(" ", "_") for c in plan.detected_conditions]),
                plan={
                    "calories_target": plan.clinical_targets.get("calories_kcal", 2000),
                    "protein_target_g": plan.clinical_targets.get("protein_g", 60.0),
                    "carb_target_g": plan.clinical_targets.get("carbohydrate_g", 200.0),
                    "fat_target_g": plan.clinical_targets.get("fat_g", 60.0),
                    "sodium_limit_mg": plan.clinical_targets.get("sodium_limit_mg", 1500.0),
                    "potassium_limit_mg": plan.clinical_targets.get("potassium_guidance_mg", 2000.0),
                    "recommendation_note": plan.clinical_notes,
                }
            )
        return plan
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex)) from ex

