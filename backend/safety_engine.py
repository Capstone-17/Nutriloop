"""
Medical Constraint Engine with Safety Guardrails
Implements medical guidelines and safety checks for diet recommendations
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum


class SafetyLevel(Enum):
    """Safety severity levels"""
    SAFE = "safe"
    WARNING = "warning"
    MODERATE_RISK = "moderate_risk"
    HIGH_RISK = "high_risk"
    CRITICAL = "critical"


class DiseaseType(Enum):
    """Supported disease types"""
    CKD = "ckd"
    DIABETES = "diabetes"
    HYPERTENSION = "hypertension"


@dataclass
class MedicalConstraint:
    """Medical constraint definition"""
    nutrient: str
    min_value: Optional[float]
    max_value: float
    unit: str
    disease_relevance: List[str]
    safety_critical: bool = False
    clinical_guideline: str = ""


@dataclass
class SafetyViolation:
    """Safety violation record"""
    constraint_type: str
    current_value: float
    limit_value: float
    severity: SafetyLevel
    message: str
    recommendation: str


@dataclass
class ValidationResult:
    """Validation result for meal/plan"""
    is_safe: bool
    violations: List[SafetyViolation]
    warnings: List[str]
    adjusted_values: Dict[str, float]
    safety_score: float  # 0.0 (unsafe) to 1.0 (safe)


class MedicalGuidelines:
    """Medical guidelines from authoritative sources"""
    
    # CKD Guidelines (KDIGO 2023)
    CKD_CONSTRAINTS = {
        "sodium_mg": {"max": 2000, "critical": 2300, "guideline": "KDIGO: Sodium <2g/day for CKD patients"},
        "potassium_mg": {"max": 2000, "critical": 2500, "guideline": "KDIGO: Potassium restriction for advanced CKD"},
        "phosphorus_mg": {"max": 800, "critical": 1000, "guideline": "KDIGO: Phosphorus 800-1000mg/day"},
        "protein_g_kg": {"max": 0.8, "critical": 1.0, "guideline": "KDIGO: Protein 0.6-0.8g/kg/day"},
        "fluid_ml": {"max": 2000, "critical": 2500, "guideline": "KDIGO: Fluid restriction for advanced CKD"},
    }
    
    # Diabetes Guidelines (ADA 2024)
    DIABETES_CONSTRAINTS = {
        "carbs_g_meal": {"max": 45, "critical": 60, "guideline": "ADA: 45-60g carbs per meal"},
        "sugar_g_day": {"max": 25, "critical": 37.5, "guideline": "ADA: Added sugar <10% of calories"},
        "fiber_g_day": {"min": 25, "guideline": "ADA: 25-35g fiber daily"},
        "sodium_mg": {"max": 2300, "critical": 2300, "guideline": "ADA: Sodium <2300mg/day"},
        "saturated_fat_g": {"max": 13, "critical": 16, "guideline": "ADA: Saturated fat <13g/day"},
    }
    
    # Hypertension Guidelines (AHA/ACC 2023)
    HYPERTENSION_CONSTRAINTS = {
        "sodium_mg": {"max": 1500, "critical": 2300, "guideline": "AHA: Sodium <1500mg ideal, <2300mg limit"},
        "potassium_mg": {"min": 3500, "guideline": "AHA: Potassium 3500-4700mg/day"},
        "fiber_g_day": {"min": 25, "guideline": "AHA: 25-30g fiber daily"},
        "saturated_fat_g": {"max": 13, "critical": 16, "guideline": "AHA: Saturated fat <13g/day"},
    }
    
    @classmethod
    def get_constraints(cls, disease: str) -> Dict[str, Dict[str, Any]]:
        """Get constraints for a specific disease or merged comorbidity profile"""
        d_lower = disease.lower().strip()
        disease_map = {
            "ckd": cls.CKD_CONSTRAINTS,
            "diabetes": cls.DIABETES_CONSTRAINTS,
            "hypertension": cls.HYPERTENSION_CONSTRAINTS,
        }
        if d_lower in disease_map:
            return disease_map[d_lower]

        # Comorbidity constraint intersection
        diseases = [d for d in ["ckd", "hypertension", "diabetes"] if d in d_lower]
        if not diseases:
            return cls.CKD_CONSTRAINTS

        merged: Dict[str, Dict[str, Any]] = {}
        for d in diseases:
            for nutrient, limits in disease_map[d].items():
                if nutrient not in merged:
                    merged[nutrient] = limits.copy()
                else:
                    # Strictest maximum
                    if "max" in limits and "max" in merged[nutrient]:
                        # Potassium exception: if CKD is present, use CKD potassium limit
                        if nutrient == "potassium_mg" and "ckd" in diseases:
                            merged[nutrient]["max"] = cls.CKD_CONSTRAINTS["potassium_mg"]["max"]
                            merged[nutrient]["critical"] = cls.CKD_CONSTRAINTS["potassium_mg"]["critical"]
                        else:
                            merged[nutrient]["max"] = min(merged[nutrient]["max"], limits["max"])
                    if "critical" in limits and "critical" in merged[nutrient]:
                        merged[nutrient]["critical"] = min(merged[nutrient]["critical"], limits["critical"])
        return merged


class SafetyEngine:
    """Main safety engine for medical constraint validation"""
    
    def __init__(self):
        self.guidelines = MedicalGuidelines()
        self.medication_interactions = self._load_medication_interactions()
        self.emergency_thresholds = self._load_emergency_thresholds()
    
    def _load_medication_interactions(self) -> Dict[str, List[str]]:
        """Load medication-food interaction rules for 18+ medications"""
        return {
            "warfarin": ["vitamin_k", "leafy_greens", "spinach", "broccoli"],
            "coumadin": ["vitamin_k", "leafy_greens", "spinach", "broccoli"],
            "ace_inhibitors": ["potassium_high", "salt_substitutes", "bananas"],
            "lisinopril": ["potassium_high", "salt_substitutes", "bananas"],
            "ramipril": ["potassium_high", "salt_substitutes"],
            "arbs": ["potassium_high", "salt_substitutes"],
            "losartan": ["potassium_high", "salt_substitutes"],
            "valsartan": ["potassium_high", "salt_substitutes"],
            "sglt2_inhibitors": ["very_low_carb", "keto", "alcohol"],
            "empagliflozin": ["very_low_carb", "keto", "alcohol"],
            "dapagliflozin": ["very_low_carb", "keto", "alcohol"],
            "jardiance": ["very_low_carb", "keto", "alcohol"],
            "glp1_ras": ["high_fat_meals", "large_portions"],
            "semaglutide": ["high_fat_meals", "large_portions"],
            "ozempic": ["high_fat_meals", "large_portions"],
            "beta_blockers": ["high_potassium", "salt_substitutes"],
            "metoprolol": ["high_potassium", "salt_substitutes"],
            "calcium_channel_blockers": ["grapefruit", "grapefruit_juice"],
            "amlodipine": ["grapefruit", "grapefruit_juice"],
            "diuretics": ["sodium_high", "licorice"],
            "furosemide": ["sodium_high", "licorice"],
            "lasix": ["sodium_high", "licorice"],
            "insulin": ["carbohydrates", "alcohol", "sugars"],
            "metformin": ["alcohol"],
            "digoxin": ["potassium_low", "high_fiber_meals"],
            "statins": ["grapefruit", "grapefruit_juice"],
            "atorvastatin": ["grapefruit", "grapefruit_juice"],
            "potassium_binders": ["oral_medications"],
            "lokelma": ["oral_medications"],
            "phosphate_binders": ["fasting_administration"],
            "sevelamer": ["fasting_administration"],
        }
    
    def _load_emergency_thresholds(self) -> Dict[str, Dict[str, float]]:
        """Load emergency thresholds requiring immediate attention"""
        return {
            "sodium_mg": {"critical": 3000, "emergency": 5000},
            "potassium_mg": {"critical_low": 2000, "critical_high": 6000},
            "blood_glucose_mg_dl": {"critical_low": 70, "critical_high": 400},
            "blood_pressure_systolic": {"critical_high": 180},
        }

    
    def validate_meal(
        self,
        meal_data: Dict[str, float],
        disease: str,
        user_medications: Optional[List[str]] = None,
        risk_level: str = "moderate"
    ) -> ValidationResult:
        """Validate a single meal against medical constraints"""
        constraints = self.guidelines.get_constraints(disease)
        violations = []
        warnings = []
        adjusted_values = meal_data.copy()
        
        # Apply risk-based adjustments
        risk_multipliers = {
            "low": 1.2,
            "moderate": 1.0,
            "high": 0.8
        }
        multiplier = risk_multipliers.get(risk_level, 1.0)
        
        # Check each constraint
        for nutrient, limits in constraints.items():
            current_value = meal_data.get(nutrient, 0)
            
            # Apply risk-based limit adjustment
            max_limit = limits.get("max", float('inf'))
            if max_limit != float('inf'):
                adjusted_max = max_limit * multiplier
            else:
                adjusted_max = max_limit
            
            min_limit = limits.get("min", 0)
            
            # Check maximum limits
            if "max" in limits and current_value > adjusted_max:
                severity = self._determine_severity(nutrient, current_value, limits, multiplier)
                violation = SafetyViolation(
                    constraint_type=nutrient,
                    current_value=current_value,
                    limit_value=adjusted_max,
                    severity=severity,
                    message=f"{nutrient} exceeds safe limit for {disease}",
                    recommendation=f"Reduce {nutrient} to {adjusted_max:.1f} {limits.get('unit', '')}"
                )
                violations.append(violation)
                adjusted_values[nutrient] = adjusted_max
            
            # Check minimum limits
            elif "min" in limits and current_value < min_limit:
                violation = SafetyViolation(
                    constraint_type=nutrient,
                    current_value=current_value,
                    limit_value=min_limit,
                    severity=SafetyLevel.WARNING,
                    message=f"{nutrient} below recommended minimum",
                    recommendation=f"Increase {nutrient} to {min_limit:.1f} {limits.get('unit', '')}"
                )
                violations.append(violation)
            
            # Check critical thresholds
            if "critical" in limits and current_value > limits["critical"]:
                critical_violation = SafetyViolation(
                    constraint_type=nutrient,
                    current_value=current_value,
                    limit_value=limits["critical"],
                    severity=SafetyLevel.CRITICAL,
                    message=f"{nutrient} exceeds critical safety threshold",
                    recommendation=f"IMMEDIATE: Reduce {nutrient} to {limits['critical']:.1f}"
                )
                violations.append(critical_violation)
        
        # Check medication interactions
        if user_medications:
            med_warnings = self._check_medication_interactions(meal_data, user_medications)
            warnings.extend(med_warnings)
        
        # Calculate safety score
        safety_score = self._calculate_safety_score(violations, warnings)
        
        return ValidationResult(
            is_safe=len([v for v in violations if v.severity in [SafetyLevel.HIGH_RISK, SafetyLevel.CRITICAL]]) == 0,
            violations=violations,
            warnings=warnings,
            adjusted_values=adjusted_values,
            safety_score=safety_score
        )
    
    def validate_daily_plan(
        self,
        daily_totals: Dict[str, float],
        disease: str,
        user_medications: Optional[List[str]] = None,
        risk_level: str = "moderate"
    ) -> ValidationResult:
        """Validate daily nutritional totals"""
        # For daily totals, we use slightly different thresholds
        constraints = self.guidelines.get_constraints(disease)
        violations = []
        warnings = []
        adjusted_values = daily_totals.copy()
        
        # Daily-specific adjustments
        daily_multipliers = {
            "low": 1.3,
            "moderate": 1.1,
            "high": 0.9
        }
        multiplier = daily_multipliers.get(risk_level, 1.1)
        
        for nutrient, limits in constraints.items():
            current_value = daily_totals.get(nutrient, 0)
            
            # Apply daily multiplier
            if "max" in limits:
                daily_max = limits.get("max", float('inf')) * multiplier
            else:
                daily_max = float('inf')
            
            daily_min = limits.get("min", 0)
            
            if "max" in limits and current_value > daily_max:
                severity = self._determine_severity(nutrient, current_value, limits, multiplier)
                violations.append(SafetyViolation(
                    constraint_type=nutrient,
                    current_value=current_value,
                    limit_value=daily_max,
                    severity=severity,
                    message=f"Daily {nutrient} exceeds safe limit",
                    recommendation=f"Reduce daily {nutrient} to {daily_max:.1f}"
                ))
                adjusted_values[nutrient] = daily_max
            
            if "min" in limits and current_value < daily_min:
                violations.append(SafetyViolation(
                    constraint_type=nutrient,
                    current_value=current_value,
                    limit_value=daily_min,
                    severity=SafetyLevel.WARNING,
                    message=f"Daily {nutrient} below recommended minimum",
                    recommendation=f"Increase daily {nutrient} to {daily_min:.1f}"
                ))
        
        safety_score = self._calculate_safety_score(violations, warnings)
        
        return ValidationResult(
            is_safe=len([v for v in violations if v.severity in [SafetyLevel.HIGH_RISK, SafetyLevel.CRITICAL]]) == 0,
            violations=violations,
            warnings=warnings,
            adjusted_values=adjusted_values,
            safety_score=safety_score
        )
    
    def _determine_severity(
        self,
        nutrient: str,
        current_value: float,
        limits: Dict[str, Any],
        multiplier: float
    ) -> SafetyLevel:
        """Determine severity level based on how much the limit is exceeded"""
        if "critical" in limits and current_value > limits["critical"]:
            return SafetyLevel.CRITICAL
        
        max_limit = limits.get("max", float('inf'))
        if max_limit == float('inf'):
            return SafetyLevel.WARNING
        
        adjusted_max = max_limit * multiplier
        excess_ratio = (current_value - adjusted_max) / adjusted_max if adjusted_max > 0 else 0
        
        if excess_ratio > 0.5:
            return SafetyLevel.HIGH_RISK
        elif excess_ratio > 0.25:
            return SafetyLevel.MODERATE_RISK
        else:
            return SafetyLevel.WARNING
    
    def _check_medication_interactions(
        self,
        meal_data: Dict[str, float],
        medications: List[str]
    ) -> List[str]:
        """Check for medication-food interactions"""
        warnings = []
        
        for medication in medications:
            if medication.lower() in self.medication_interactions:
                interactions = self.medication_interactions[medication.lower()]
                for interaction in interactions:
                    if "potassium" in interaction.lower():
                        potassium = meal_data.get("potassium_mg", 0)
                        if potassium > 500:  # High potassium food
                            warnings.append(
                                f"High potassium content may interact with {medication}. "
                                f"Monitor potassium intake closely."
                            )
                    elif "vitamin_k" in interaction.lower():
                        warnings.append(
                            f"Vitamin K rich foods may affect {medication} efficacy. "
                            f"Maintain consistent vitamin K intake."
                        )
                    elif "sodium" in interaction.lower():
                        sodium = meal_data.get("sodium_mg", 0)
                        if sodium > 400:  # High sodium food
                            warnings.append(
                                f"High sodium content may affect {medication}. "
                                f"Consider lower sodium alternatives."
                            )
        
        return warnings
    
    def _calculate_safety_score(self, violations: List[SafetyViolation], warnings: List[str]) -> float:
        """Calculate overall safety score (0.0 to 1.0)"""
        if not violations and not warnings:
            return 1.0
        
        # Start with perfect score
        score = 1.0
        
        # Deduct points for violations based on severity
        severity_penalties = {
            SafetyLevel.CRITICAL: 0.5,
            SafetyLevel.HIGH_RISK: 0.3,
            SafetyLevel.MODERATE_RISK: 0.15,
            SafetyLevel.WARNING: 0.05,
        }
        
        for violation in violations:
            score -= severity_penalties.get(violation.severity, 0.1)
        
        # Small deduction for warnings
        score -= len(warnings) * 0.02
        
        return max(0.0, score)
    
    def get_emergency_alerts(
        self,
        patient_data: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """Check for emergency conditions requiring immediate attention"""
        alerts = []
        
        for parameter, thresholds in self.emergency_thresholds.items():
            current_value = patient_data.get(parameter)
            if current_value is None:
                continue
            
            if "critical_high" in thresholds and current_value > thresholds["critical_high"]:
                alerts.append({
                    "level": "EMERGENCY",
                    "parameter": parameter,
                    "current_value": current_value,
                    "threshold": thresholds["critical_high"],
                    "message": f"CRITICAL: {parameter} exceeds emergency threshold"
                })
            elif "critical_low" in thresholds and current_value < thresholds["critical_low"]:
                alerts.append({
                    "level": "EMERGENCY",
                    "parameter": parameter,
                    "current_value": current_value,
                    "threshold": thresholds["critical_low"],
                    "message": f"CRITICAL: {parameter} below emergency threshold"
                })
        
        return alerts


# Global safety engine instance
safety_engine = SafetyEngine()