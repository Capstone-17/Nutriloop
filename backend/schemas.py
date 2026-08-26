from typing import Any, Dict, Literal, Optional, List, Union
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


DiseaseType = Literal["ckd", "hypertension", "diabetes"]
SexType = Literal["male", "female"]


class MealType(str, Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"


class SafetyLevel(str, Enum):
    SAFE = "safe"
    WARNING = "warning"
    MODERATE_RISK = "moderate_risk"
    HIGH_RISK = "high_risk"
    CRITICAL = "critical"


class PredictRiskRequest(BaseModel):
    disease: DiseaseType
    features: Dict[str, Any] = Field(default_factory=dict)
    user_id: Optional[str] = None


class PredictRiskResponse(BaseModel):
    disease: DiseaseType
    predicted_class: int
    risk_score: float
    risk_level: Literal["low", "moderate", "high"]
    threshold_used: float
    thresholds: Dict[str, float] = Field(default_factory=dict)
    threshold_band: str = "below_moderate"
    major_risk_factors: List[str] = Field(default_factory=list)
    model_name: str


class CKDRawInput(BaseModel):
    age_years: int = Field(ge=18, le=100)
    sex: SexType
    body_mass_index: float = Field(ge=10.0, le=90.0)
    diagnosed_diabetes: bool = False
    diagnosed_hypertension: bool = False
    systolic_bp_mmhg: Optional[float] = Field(default=None, ge=70.0, le=260.0)
    diastolic_bp_mmhg: Optional[float] = Field(default=None, ge=40.0, le=160.0)
    fasting_glucose_mg_dl: Optional[float] = Field(default=None, ge=40.0, le=450.0)


class HypertensionRawInput(BaseModel):
    age_years: int = Field(ge=18, le=100)
    sex: SexType
    education_level: int = Field(default=5, ge=1, le=9)
    current_smoker: bool = False
    cigarettes_per_day: float = Field(default=0.0, ge=0.0, le=100.0)
    prior_stroke: bool = False
    body_mass_index: float = Field(ge=10.0, le=90.0)
    diagnosed_diabetes: bool = False
    systolic_bp_mmhg: Optional[float] = Field(default=None, ge=70.0, le=260.0)
    diastolic_bp_mmhg: Optional[float] = Field(default=None, ge=40.0, le=160.0)
    fasting_glucose_mg_dl: Optional[float] = Field(default=None, ge=40.0, le=450.0)


class DiabetesRawInput(BaseModel):
    age_years: int = Field(ge=18, le=100)
    sex: SexType
    body_mass_index: float = Field(ge=10.0, le=90.0)
    current_smoker: bool = False
    diagnosed_hypertension: bool = False
    systolic_bp_mmhg: Optional[float] = Field(default=None, ge=70.0, le=260.0)
    diastolic_bp_mmhg: Optional[float] = Field(default=None, ge=40.0, le=160.0)
    fasting_glucose_mg_dl: Optional[float] = Field(default=None, ge=40.0, le=450.0)


class PredictRiskRawRequest(BaseModel):
    disease: DiseaseType
    raw_inputs: Dict[str, Any] = Field(default_factory=dict)
    user_id: Optional[str] = None


class PredictRiskRawResponse(PredictRiskResponse):
    transformed_features: Dict[str, Any]
    raw_inputs: Dict[str, Any]
    validation_warnings: List[str] = Field(default_factory=list)


class RiskExplanationRawRequest(BaseModel):
    disease: DiseaseType
    raw_inputs: Dict[str, Any] = Field(default_factory=dict)
    user_id: Optional[str] = None


class RiskExplanationRawResponse(PredictRiskRawResponse):
    top_factors: List[Dict[str, Any]] = Field(default_factory=list)
    calibration_context: Dict[str, Any] = Field(default_factory=dict)
    explanation_text: str


class RiskExplanationLogRecord(BaseModel):
    id: int
    user_id: Optional[str] = None
    disease: str
    model_name: str
    predicted_class: int
    risk_score: float
    risk_level: str
    thresholds: Dict[str, float] = Field(default_factory=dict)
    threshold_band: str
    major_risk_factors: List[str] = Field(default_factory=list)
    validation_warnings: List[str] = Field(default_factory=list)
    raw_inputs: Dict[str, Any] = Field(default_factory=dict)
    transformed_features: Dict[str, Any] = Field(default_factory=dict)
    top_factors: List[Dict[str, Any]] = Field(default_factory=list)
    calibration_context: Dict[str, Any] = Field(default_factory=dict)
    explanation_text: str
    source: str
    created_at: str


class RiskExplanationLogListResponse(BaseModel):
    count: int
    limit: int
    offset: int
    items: List[RiskExplanationLogRecord] = Field(default_factory=list)


class RecommendPlanRequest(BaseModel):
    user_id: str
    disease: DiseaseType
    profile: Dict[str, Any] = Field(default_factory=dict)
    risk_score: float = Field(ge=0.0, le=1.0)


class RecommendPlanResponse(BaseModel):
    user_id: str
    disease: DiseaseType
    calories_target: int
    protein_target_g: int
    carb_target_g: int
    fat_target_g: int
    sodium_limit_mg: int
    potassium_limit_mg: int
    sugar_limit_g: Optional[int] = None
    phosphorus_limit_mg: Optional[int] = None
    fiber_target_g: Optional[int] = None
    fluid_target_ml: Optional[int] = None
    diet_focus: List[str] = Field(default_factory=list)
    calibration_context: Dict[str, Any] = Field(default_factory=dict)
    recommendation_note: str


class LogMealRequest(BaseModel):
    user_id: str
    planned_calories: int = Field(gt=0)
    consumed_calories: int = Field(gt=0)
    notes: str = ""


class LogMealResponse(BaseModel):
    meal_log_id: int
    user_id: str
    deviation_flag: bool
    deviation_percent: float
    alert_created: bool
    alert_message: Optional[str] = None


class RiskReportRequest(BaseModel):
    disease: DiseaseType
    features: Dict[str, Any] = Field(default_factory=dict)
    profile: Dict[str, Any] = Field(default_factory=dict)
    user_id: Optional[str] = None
    top_n_foods: int = Field(default=8, ge=1, le=25)


class RiskReportResponse(BaseModel):
    disease: DiseaseType
    predicted_class: int
    risk_score: float
    risk_level: Literal["low", "moderate", "high"]
    model_name: str
    thresholds: Dict[str, float]
    top_factors: List[Dict[str, Any]]
    calibration_context: Dict[str, Any] = Field(default_factory=dict)
    plan: Dict[str, Any]
    recommended_foods: List[Dict[str, Any]]
    report_text: str


class RiskReportRawRequest(BaseModel):
    disease: DiseaseType
    raw_inputs: Dict[str, Any] = Field(default_factory=dict)
    profile: Dict[str, Any] = Field(default_factory=dict)
    user_id: Optional[str] = None
    top_n_foods: int = Field(default=8, ge=1, le=25)


class RiskReportRawResponse(RiskReportResponse):
    transformed_features: Dict[str, Any]
    raw_inputs: Dict[str, Any]
    validation_warnings: List[str] = Field(default_factory=list)


class ChatbotRequest(BaseModel):
    user_id: str
    message: str = Field(min_length=1, max_length=4000)
    disease: Optional[DiseaseType] = None
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)


class ChatbotResponse(BaseModel):
    reply: str
    tool_calls_made: List[str] = Field(default_factory=list)
    escalated: bool
    latency_ms: float
    steps: int


# Agentic AI Schemas

class UserProfile(BaseModel):
    user_id: str
    disease: DiseaseType
    risk_level: Literal["low", "moderate", "high"]
    dietary_preferences: List[str] = Field(default_factory=list)
    allergies: List[str] = Field(default_factory=list)
    medications: List[str] = Field(default_factory=list)
    calorie_target: int = Field(default=1500, ge=1000, le=4000)
    cultural_preferences: List[str] = Field(default_factory=list)
    cooking_skill: Literal["beginner", "intermediate", "advanced"] = "intermediate"
    time_constraints: Literal["low", "moderate", "high"] = "moderate"


class AgentRequest(BaseModel):
    user_id: str
    user_message: str
    user_profile: UserProfile
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    intent: str
    content: str
    meal_plans: List[Dict[str, Any]] = Field(default_factory=list)
    safety_alerts: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    follow_up_questions: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    requires_medical_supervision: bool = False


class SafetyValidationRequest(BaseModel):
    user_id: str
    disease: DiseaseType
    meal_data: Dict[str, float]
    risk_level: Literal["low", "moderate", "high"] = "moderate"
    user_medications: List[str] = Field(default_factory=list)
    validation_type: Literal["meal", "daily_plan"] = "meal"


class SafetyValidationResponse(BaseModel):
    is_safe: bool
    safety_score: float = Field(default=0.0, ge=0.0, le=1.0)
    violations: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    adjusted_values: Dict[str, float] = Field(default_factory=dict)
    medical_compliance: Dict[str, Any] = Field(default_factory=dict)


class MealLogRequest(BaseModel):
    user_id: str
    meal_type: MealType
    planned_calories: int = Field(gt=0)
    consumed_calories: int = Field(gt=0)
    planned_nutrients: Dict[str, float] = Field(default_factory=dict)
    consumed_nutrients: Dict[str, float] = Field(default_factory=dict)
    planned_time: Optional[datetime] = None
    actual_time: Optional[datetime] = None
    notes: str = ""


class MealLogResponse(BaseModel):
    meal_id: str
    deviation_detected: bool
    deviation_type: Optional[str] = None
    deviation_severity: str
    adaptation_triggered: bool
    alert_generated: bool


class AdaptationSummaryRequest(BaseModel):
    user_id: str


class AdaptationSummaryResponse(BaseModel):
    user_id: str
    active_adaptations: int
    pending_adaptations: List[Dict[str, Any]] = Field(default_factory=list)
    unresolved_alerts: int
    recent_alerts: List[Dict[str, Any]] = Field(default_factory=list)
    learned_patterns: int
    pattern_summary: List[Dict[str, Any]] = Field(default_factory=list)
    recent_meal_count: int
    adherence_rate: float


class FeedbackRequest(BaseModel):
    user_id: str
    feedback_type: Literal["meal_rating", "satisfaction", "adherence", "symptom_report", "suggestion", "complaint"]
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    text_feedback: str = ""
    meal_id: Optional[str] = None
    recommendation_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FeedbackResponse(BaseModel):
    feedback_id: str
    acknowledged: bool
    impact_on_recommendations: str


class HealthOutcomeRequest(BaseModel):
    user_id: str
    outcome_type: Literal["weight_change", "blood_pressure_change", "blood_glucose_change", "kidney_function_change", "symptom_improvement"]
    value: float
    unit: str
    measurement_context: Dict[str, Any] = Field(default_factory=dict)


class HealthOutcomeResponse(BaseModel):
    outcome_id: str
    clinical_significance: str
    change_from_baseline: Optional[float] = None
    trend_analysis: Dict[str, Any] = Field(default_factory=dict)


class MedicalGuidelineRequest(BaseModel):
    disease: DiseaseType
    condition: Optional[str] = None


class MedicalGuidelineResponse(BaseModel):
    guidelines: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class DrugInteractionRequest(BaseModel):
    drug_name: str


class DrugInteractionResponse(BaseModel):
    interactions: List[Dict[str, Any]] = Field(default_factory=list)
    severity_summary: Dict[str, int] = Field(default_factory=dict)
