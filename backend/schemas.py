from typing import Any, Dict, Literal, Optional, List, Union
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


DiseaseType = Literal["ckd", "hypertension", "diabetes"]
ComorbidDiseaseType = Literal[
    "ckd",
    "hypertension",
    "diabetes",
    "ckd_hypertension",
    "diabetes_hypertension",
    "ckd_diabetes",
    "ckd_diabetes_hypertension",
]
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
    disease: str
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
    serum_creatinine_mg_dl: Optional[float] = Field(default=None, ge=0.1, le=25.0)
    blood_urea_mg_dl: Optional[float] = Field(default=None, ge=1.0, le=400.0)
    hemoglobin_g_dl: Optional[float] = Field(default=None, ge=3.0, le=25.0)
    urine_albumin_dipstick: Optional[int] = Field(default=None, ge=0, le=5)


class HypertensionRawInput(BaseModel):
    age_years: int = Field(ge=18, le=100)
    sex: SexType
    education_level: int = Field(default=2, ge=1, le=9)
    current_smoker: bool = False
    cigarettes_per_day: float = Field(default=0.0, ge=0.0, le=100.0)
    prior_stroke: bool = False
    body_mass_index: float = Field(ge=10.0, le=90.0)
    diagnosed_diabetes: bool = False
    systolic_bp_mmhg: Optional[float] = Field(default=None, ge=70.0, le=260.0)
    diastolic_bp_mmhg: Optional[float] = Field(default=None, ge=40.0, le=160.0)
    fasting_glucose_mg_dl: Optional[float] = Field(default=None, ge=40.0, le=450.0)
    total_cholesterol_mg_dl: Optional[float] = Field(default=None, ge=50.0, le=600.0)
    heart_rate_bpm: Optional[float] = Field(default=None, ge=30.0, le=220.0)
    blood_pressure_meds: bool = False


class DiabetesRawInput(BaseModel):
    age_years: int = Field(ge=18, le=100)
    sex: SexType
    body_mass_index: float = Field(ge=10.0, le=90.0)
    current_smoker: bool = False
    diagnosed_hypertension: bool = False
    systolic_bp_mmhg: Optional[float] = Field(default=None, ge=70.0, le=260.0)
    diastolic_bp_mmhg: Optional[float] = Field(default=None, ge=40.0, le=160.0)
    fasting_glucose_mg_dl: Optional[float] = Field(default=None, ge=40.0, le=450.0)
    fasting_insulin_uIU_ml: Optional[float] = Field(default=None, ge=1.0, le=500.0)
    hba1c_pct: Optional[float] = Field(default=None, ge=3.0, le=20.0)
    skin_thickness_mm: Optional[float] = Field(default=None, ge=1.0, le=100.0)
    diabetes_pedigree: Optional[float] = Field(default=None, ge=0.0, le=3.0)


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
    disease: Optional[str] = "ckd"
    diseases: Optional[List[str]] = None
    profile: Dict[str, Any] = Field(default_factory=dict)
    risk_score: float = Field(default=0.5, ge=0.0, le=1.0)
    risk_scores: Optional[Dict[str, float]] = None


class RecommendPlanResponse(BaseModel):
    user_id: str
    disease: str
    diseases: List[str] = Field(default_factory=list)
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
    disease: Optional[str] = "ckd"
    diseases: Optional[List[str]] = None
    features: Dict[str, Any] = Field(default_factory=dict)
    profile: Dict[str, Any] = Field(default_factory=dict)
    user_id: Optional[str] = None
    top_n_foods: int = Field(default=8, ge=1, le=25)


class RiskReportResponse(BaseModel):
    disease: str
    diseases: List[str] = Field(default_factory=list)
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
    disease: Optional[str] = "ckd"
    diseases: Optional[List[str]] = None
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
    disease: Optional[str] = None
    diseases: Optional[List[str]] = None
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)


class ChatbotResponse(BaseModel):
    reply: str
    tool_calls_made: List[str] = Field(default_factory=list)
    escalated: bool
    latency_ms: float
    steps: int
    engine_mode: Optional[str] = "Dr. Nutriloop Clinical AI"
    updated_diet_plan: Optional[Dict[str, Any]] = None


# Agentic AI Schemas

class UserProfile(BaseModel):
    user_id: str
    disease: str = "ckd"
    diseases: List[str] = Field(default_factory=list)
    risk_level: Literal["low", "moderate", "high"] = "moderate"
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
    disease: Optional[str] = "ckd"
    diseases: Optional[List[str]] = None
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


# ==================== Weekly Diet Recommendation Schemas ====================

class LatestTestReportInput(BaseModel):
    systolic_bp_mmhg: Optional[float] = Field(default=None, ge=70.0, le=260.0)
    diastolic_bp_mmhg: Optional[float] = Field(default=None, ge=40.0, le=160.0)
    fasting_glucose_mg_dl: Optional[float] = Field(default=None, ge=40.0, le=500.0)
    postprandial_glucose_mg_dl: Optional[float] = Field(default=None, ge=50.0, le=600.0)
    hba1c_pct: Optional[float] = Field(default=None, ge=3.5, le=18.0)
    serum_creatinine_mg_dl: Optional[float] = Field(default=None, ge=0.2, le=25.0)
    blood_urea_mg_dl: Optional[float] = Field(default=None, ge=2.0, le=400.0)
    egfr_ml_min: Optional[float] = Field(default=None, ge=2.0, le=160.0)
    serum_potassium_meq_l: Optional[float] = Field(default=None, ge=1.5, le=9.0)
    serum_sodium_meq_l: Optional[float] = Field(default=None, ge=100.0, le=180.0)
    serum_phosphorus_mg_dl: Optional[float] = Field(default=None, ge=0.5, le=15.0)
    urine_albumin_dipstick: Optional[float] = Field(default=None, ge=0.0, le=5.0)
    total_cholesterol_mg_dl: Optional[float] = Field(default=None, ge=80.0, le=600.0)
    ldl_cholesterol_mg_dl: Optional[float] = Field(default=None, ge=20.0, le=400.0)
    hdl_cholesterol_mg_dl: Optional[float] = Field(default=None, ge=10.0, le=150.0)
    triglycerides_mg_dl: Optional[float] = Field(default=None, ge=30.0, le=1200.0)
    report_summary_text: Optional[str] = Field(default=None, max_length=5000)


class PatientPreferencesInput(BaseModel):
    native_place_region: str = Field(default="South Indian", description="Native region / culinary tradition (e.g. South Indian, North Indian, Gujarati, Maharashtrian, Bengali, Continental)")
    dietary_type: Literal["vegetarian", "non_vegetarian", "vegan", "eggetarian", "jain"] = "vegetarian"
    allergies: List[str] = Field(default_factory=list)
    interests_and_likes: List[str] = Field(default_factory=list, description="Preferred foods/ingredients e.g. millets, ragi, paneer, soups, light spices")
    dislikes: List[str] = Field(default_factory=list, description="Disliked foods e.g. bitter gourd, oats")
    cooking_skill: Literal["beginner", "intermediate", "advanced"] = "intermediate"
    time_constraints_mins: Optional[int] = Field(default=30, ge=10, le=180)
    active_medications: List[str] = Field(default_factory=list, description="Active prescriptions e.g. lisinopril, amlodipine, jardiance, metformin")
    calorie_target_override: Optional[int] = Field(default=None, ge=1000, le=4000)
    craving_or_treat: Optional[str] = Field(default=None, description="Patient's specific craving or desired indulgence (e.g. sugar, sweet dessert, biryani, coffee) for smart weekly budgeting")

    @model_validator(mode="before")
    @classmethod
    def resolve_calorie_alias(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "calorie_target_kcal" in data and "calorie_target_override" not in data:
                data["calorie_target_override"] = data.get("calorie_target_kcal")
            val = data.get("calorie_target_override")
            if not val or str(val).strip() in ("", "0", "null", "None"):
                data["calorie_target_override"] = None
        return data

    @field_validator("dietary_type", mode="before")
    @classmethod
    def normalize_dietary_type(cls, v: Any) -> str:
        if isinstance(v, str):
            cleaned = v.strip().lower().replace("-", "_").replace(" ", "_")
            if cleaned in ("non_veg", "nonveg", "non_vegetarian"):
                return "non_vegetarian"
            if cleaned in ("veg", "vegetarian"):
                return "vegetarian"
            if cleaned in ("egg", "eggetarian", "ovo_vegetarian"):
                return "eggetarian"
            return cleaned
        return v



class MealItem(BaseModel):
    item_name: str
    portion: str
    nutrients: Dict[str, float] = Field(default_factory=dict)


class SingleMealInterval(BaseModel):
    interval_name: str  # "Breakfast", "Mid-Morning Snack", "Lunch", "Evening Snack", "Dinner"
    time_window: str
    meal_title: str
    items: List[MealItem]
    total_nutrients: Dict[str, float]
    clinical_justification: str
    prep_tips: str
    substitutions: List[Dict[str, str]] = Field(default_factory=list)


class DayDietPlan(BaseModel):
    day_number: int  # 1 to 7
    day_name: str    # "Monday" to "Sunday"
    intervals: List[SingleMealInterval]
    daily_total_nutrients: Dict[str, float]
    daily_target_compliance: Dict[str, Any]


class WeeklyDietPlanRequest(BaseModel):
    user_id: Optional[str] = "guest_patient"
    age_years: int = Field(default=52, ge=18, le=100)
    sex: Literal["male", "female"] = "male"
    body_mass_index: float = Field(default=26.5, ge=12.0, le=70.0)
    test_reports: LatestTestReportInput = Field(default_factory=LatestTestReportInput)
    preferences: PatientPreferencesInput = Field(default_factory=PatientPreferencesInput)


class WeeklyDietPlanResponse(BaseModel):
    user_id: str
    generated_at: str
    regional_cuisine: Optional[str] = "Regional Cuisine"
    patient_summary: Dict[str, Any]
    clinical_targets: Dict[str, Any]
    detected_conditions: List[str]
    days: List[DayDietPlan]
    weekly_nutritional_summary: Dict[str, Any]
    medication_alerts: List[str] = Field(default_factory=list)
    grocery_checklist: List[str] = Field(default_factory=list)
    categorized_grocery_checklist: Dict[str, List[str]] = Field(default_factory=dict)
    clinical_notes: str
    smart_craving_strategy: Optional[Dict[str, Any]] = None

