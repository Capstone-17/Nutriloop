"""
Real-Time Adaptation and Deviation Detection System
Monitors user behavior, detects deviations, and dynamically adjusts recommendations
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
from datetime import datetime

from backend import db


class DeviationSeverity(str, Enum):
    """Severity levels for meal deviations"""
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"

    def _rank(self) -> int:
        order = {"none": 0, "low": 1, "moderate": 2, "high": 3, "critical": 4}
        return order.get(self.value, 0)

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, DeviationSeverity):
            return self._rank() < other._rank()
        return NotImplemented

    def __le__(self, other: Any) -> bool:
        if isinstance(other, DeviationSeverity):
            return self._rank() <= other._rank()
        return NotImplemented

    def __gt__(self, other: Any) -> bool:
        if isinstance(other, DeviationSeverity):
            return self._rank() > other._rank()
        return NotImplemented

    def __ge__(self, other: Any) -> bool:
        if isinstance(other, DeviationSeverity):
            return self._rank() >= other._rank()
        return NotImplemented


class AdaptationTrigger(Enum):
    """Types of events that trigger adaptation"""
    MEAL_DEVIATION = "meal_deviation"
    SYMPTOM_CHANGE = "symptom_change"
    WEIGHT_CHANGE = "weight_change"
    ACTIVITY_CHANGE = "activity_change"
    MEDICATION_CHANGE = "medication_change"
    LAB_RESULT_CHANGE = "lab_result_change"
    USER_FEEDBACK = "user_feedback"
    SCHEDULE_CHANGE = "schedule_change"


@dataclass
class MealLog:
    """Individual meal log entry"""
    meal_id: str
    user_id: str
    meal_type: str
    planned_calories: int
    consumed_calories: int
    planned_nutrients: Dict[str, float]
    consumed_nutrients: Dict[str, float]
    timestamp: datetime
    deviation_detected: bool
    deviation_type: Optional[str] = None
    deviation_severity: DeviationSeverity = DeviationSeverity.NONE
    notes: str = ""


@dataclass
class DeviationAlert:
    """Deviation alert notification"""
    alert_id: str
    user_id: str
    deviation_type: str
    severity: DeviationSeverity
    message: str
    recommended_action: str
    timestamp: datetime
    acknowledged: bool = False
    resolved: bool = False


@dataclass
class AdaptationAction:
    """Adaptation action to be taken"""
    action_id: str
    trigger_type: AdaptationTrigger
    action_type: str  # "adjust_calories", "modify_nutrients", "change_meal_type", "alert_supervisor"
    parameters: Dict[str, Any]
    priority: int  # 1-5, with 5 being highest priority
    reason: str
    timestamp: datetime
    executed: bool = False
    result: Optional[str] = None


@dataclass
class UserPattern:
    """Learned user behavior pattern"""
    user_id: str
    pattern_type: str  # "meal_timing", "portion_size", "food_preferences", "adherence"
    pattern_data: Dict[str, Any]
    confidence: float  # 0.0 to 1.0
    last_updated: datetime
    sample_size: int


class DeviationDetector:
    """Detects deviations from planned meals and behavior patterns"""
    
    def __init__(self):
        self.deviation_thresholds = {
            "calorie_deviation_low": 0.15,  # 15% deviation
            "calorie_deviation_moderate": 0.25,  # 25% deviation
            "calorie_deviation_high": 0.40,  # 40% deviation
            "nutrient_deviation_low": 0.20,
            "nutrient_deviation_moderate": 0.35,
            "nutrient_deviation_high": 0.50,
            "timing_deviation_minutes": 30,  # 30 minutes deviation
            "consecutive_deviations": 3  # Number of consecutive deviations to trigger alert
        }
    
    def detect_calorie_deviation(
        self,
        planned_calories: int,
        consumed_calories: int
    ) -> Tuple[bool, DeviationSeverity, float]:
        """Detect calorie deviation from plan"""
        if planned_calories == 0:
            return False, DeviationSeverity.NONE, 0.0
        
        deviation_ratio = abs(consumed_calories - planned_calories) / planned_calories
        deviation_percent = deviation_ratio * 100
        
        if deviation_ratio >= self.deviation_thresholds["calorie_deviation_high"]:
            return True, DeviationSeverity.HIGH, deviation_percent
        elif deviation_ratio >= self.deviation_thresholds["calorie_deviation_moderate"]:
            return True, DeviationSeverity.MODERATE, deviation_percent
        elif deviation_ratio >= self.deviation_thresholds["calorie_deviation_low"]:
            return True, DeviationSeverity.LOW, deviation_percent
        else:
            return False, DeviationSeverity.NONE, deviation_percent
    
    def detect_nutrient_deviation(
        self,
        planned_nutrients: Dict[str, float],
        consumed_nutrients: Dict[str, float]
    ) -> List[Tuple[str, bool, DeviationSeverity, float]]:
        """Detect deviations in specific nutrients"""
        deviations = []
        
        for nutrient, planned_value in planned_nutrients.items():
            if planned_value == 0:
                continue
            
            consumed_value = consumed_nutrients.get(nutrient, 0)
            deviation_ratio = abs(consumed_value - planned_value) / planned_value
            deviation_percent = deviation_ratio * 100
            
            if deviation_ratio >= self.deviation_thresholds["nutrient_deviation_high"]:
                deviations.append((nutrient, True, DeviationSeverity.HIGH, deviation_percent))
            elif deviation_ratio >= self.deviation_thresholds["nutrient_deviation_moderate"]:
                deviations.append((nutrient, True, DeviationSeverity.MODERATE, deviation_percent))
            elif deviation_ratio >= self.deviation_thresholds["nutrient_deviation_low"]:
                deviations.append((nutrient, True, DeviationSeverity.LOW, deviation_percent))
            else:
                deviations.append((nutrient, False, DeviationSeverity.NONE, deviation_percent))
        
        return deviations
    
    def detect_timing_deviation(
        self,
        planned_time: datetime,
        actual_time: datetime
    ) -> Tuple[bool, DeviationSeverity, int]:
        """Detect timing deviation from planned meal time"""
        time_diff = abs((actual_time - planned_time).total_seconds() / 60)  # minutes
        
        if time_diff >= self.deviation_thresholds["timing_deviation_minutes"] * 2:
            return True, DeviationSeverity.MODERATE, int(time_diff)
        elif time_diff >= self.deviation_thresholds["timing_deviation_minutes"]:
            return True, DeviationSeverity.LOW, int(time_diff)
        else:
            return False, DeviationSeverity.NONE, int(time_diff)
    
    def analyze_consecutive_deviations(
        self,
        recent_meals: List[MealLog]
    ) -> Tuple[bool, DeviationSeverity]:
        """Analyze pattern of consecutive deviations"""
        if len(recent_meals) < self.deviation_thresholds["consecutive_deviations"]:
            return False, DeviationSeverity.NONE
        
        recent_deviations = [
            meal for meal in recent_meals 
            if meal.deviation_detected and 
            meal.deviation_severity != DeviationSeverity.NONE
        ]
        
        if len(recent_deviations) >= self.deviation_thresholds["consecutive_deviations"]:
            # Check severity of consecutive deviations
            high_severity_count = sum(
                1 for meal in recent_deviations 
                if meal.deviation_severity in [DeviationSeverity.HIGH, DeviationSeverity.CRITICAL]
            )
            
            if high_severity_count >= 2:
                return True, DeviationSeverity.HIGH
            else:
                return True, DeviationSeverity.MODERATE
        
        return False, DeviationSeverity.NONE


class AdaptationEngine:
    """Main adaptation engine for dynamic recommendation adjustment"""
    
    def __init__(self):
        self.deviation_detector = DeviationDetector()
        self.user_patterns: Dict[str, List[UserPattern]] = {}
        self.active_adaptations: Dict[str, List[AdaptationAction]] = {}
        self.meal_history: Dict[str, List[MealLog]] = {}
        self.alert_history: Dict[str, List[DeviationAlert]] = {}
    
    def log_meal(
        self,
        user_id: str,
        meal_type: str,
        planned_calories: int,
        consumed_calories: int,
        planned_nutrients: Dict[str, float],
        consumed_nutrients: Dict[str, float],
        planned_time: Optional[datetime] = None,
        actual_time: Optional[datetime] = None,
        notes: str = ""
    ) -> MealLog:
        """Log a meal and detect deviations"""
        
        # Detect calorie deviation
        calorie_deviation, severity, calorie_percent = self.deviation_detector.detect_calorie_deviation(
            planned_calories, consumed_calories
        )
        
        # Detect nutrient deviations
        nutrient_deviations = self.deviation_detector.detect_nutrient_deviation(
            planned_nutrients, consumed_nutrients
        )
        
        # Detect timing deviation if times provided
        timing_deviation = False
        timing_severity = DeviationSeverity.NONE
        timing_minutes = 0
        
        if planned_time and actual_time:
            timing_deviation, timing_severity, timing_minutes = self.deviation_detector.detect_timing_deviation(
                planned_time, actual_time
            )
        
        # Determine overall deviation
        overall_deviation = calorie_deviation or timing_deviation or any(
            dev[1] for dev in nutrient_deviations
        )
        
        # Determine overall severity (highest among all deviations)
        all_severities = [severity] + [dev[2] for dev in nutrient_deviations]
        if timing_deviation:
            all_severities.append(timing_severity)
        
        overall_severity = max(all_severities) if all_severities else DeviationSeverity.NONE
        
        # Create meal log
        meal_log = MealLog(
            meal_id=f"meal_{datetime.now().timestamp()}",
            user_id=user_id,
            meal_type=meal_type,
            planned_calories=planned_calories,
            consumed_calories=consumed_calories,
            planned_nutrients=planned_nutrients,
            consumed_nutrients=consumed_nutrients,
            timestamp=actual_time or datetime.now(),
            deviation_detected=overall_deviation,
            deviation_type=self._determine_deviation_type(
                calorie_deviation, timing_deviation, nutrient_deviations
            ),
            deviation_severity=overall_severity,
            notes=notes
        )
        
        # Store meal log in memory and DB
        if user_id not in self.meal_history:
            self.meal_history[user_id] = []
        self.meal_history[user_id].append(meal_log)
        
        try:
            db.insert_meal_log(
                user_id=user_id,
                planned_calories=planned_calories,
                consumed_calories=consumed_calories,
                deviation_flag=overall_deviation,
                deviation_percent=calorie_percent,
                notes=notes,
            )
        except Exception:
            pass
        
        # Analyze consecutive deviations
        recent_meals = self.meal_history[user_id][-10:]  # Last 10 meals
        consecutive_pattern, consecutive_severity = self.deviation_detector.analyze_consecutive_deviations(
            recent_meals
        )
        
        # Generate adaptation actions if needed
        if overall_deviation or consecutive_pattern:
            adaptation_actions = self._generate_adaptation_actions(
                meal_log, consecutive_pattern, consecutive_severity
            )
            
            if user_id not in self.active_adaptations:
                self.active_adaptations[user_id] = []
            self.active_adaptations[user_id].extend(adaptation_actions)

            for act in adaptation_actions:
                try:
                    db.insert_adaptation_action(
                        user_id=user_id,
                        action_id=act.action_id,
                        trigger_type=act.trigger_type,
                        action_type=act.action_type,
                        parameters=act.parameters,
                        priority=act.priority,
                        reason=act.reason,
                        executed=act.executed,
                        result=act.result,
                    )
                except Exception:
                    pass
        
        # Generate alerts if needed
        if overall_severity in [DeviationSeverity.HIGH, DeviationSeverity.CRITICAL] or consecutive_pattern:
            alert = self._generate_deviation_alert(
                meal_log, consecutive_pattern, consecutive_severity
            )
            
            if user_id not in self.alert_history:
                self.alert_history[user_id] = []
            self.alert_history[user_id].append(alert)

            try:
                db.insert_alert(user_id=user_id, severity=alert.severity.value, message=alert.message)
            except Exception:
                pass
        
        return meal_log

    
    def _determine_deviation_type(
        self,
        calorie_deviation: bool,
        timing_deviation: bool,
        nutrient_deviations: List[Tuple[str, bool, DeviationSeverity, float]]
    ) -> str:
        """Determine the primary type of deviation"""
        if calorie_deviation and timing_deviation:
            return "combined_calorie_timing"
        elif calorie_deviation:
            return "calorie"
        elif timing_deviation:
            return "timing"
        elif nutrient_deviations:
            return "nutrient"
        else:
            return "unknown"
    
    def _generate_adaptation_actions(
        self,
        meal_log: MealLog,
        consecutive_pattern: bool,
        consecutive_severity: DeviationSeverity
    ) -> List[AdaptationAction]:
        """Generate adaptation actions based on deviations"""
        actions = []
        
        # Calorie-based adaptations
        if meal_log.deviation_type in ["calorie", "combined_calorie_timing"]:
            if meal_log.consumed_calories > meal_log.planned_calories:
                # User consistently overeats
                actions.append(AdaptationAction(
                    action_id=f"adapt_{datetime.now().timestamp()}_1",
                    trigger_type=AdaptationTrigger.MEAL_DEVIATION,
                    action_type="adjust_calories",
                    parameters={
                        "adjustment_type": "decrease",
                        "percentage": 0.10,  # 10% reduction
                        "meal_types": [meal_log.meal_type]
                    },
                    priority=3,
                    reason=f"User consistently exceeds calorie targets in {meal_log.meal_type}",
                    timestamp=datetime.now()
                ))
            else:
                # User consistently undereats
                actions.append(AdaptationAction(
                    action_id=f"adapt_{datetime.now().timestamp()}_2",
                    trigger_type=AdaptationTrigger.MEAL_DEVIATION,
                    action_type="adjust_calories",
                    parameters={
                        "adjustment_type": "increase",
                        "percentage": 0.10,  # 10% increase
                        "meal_types": [meal_log.meal_type]
                    },
                    priority=2,
                    reason=f"User consistently under-consumes calories in {meal_log.meal_type}",
                    timestamp=datetime.now()
                ))
        
        # Nutrient-based adaptations
        nutrient_deviations = self.deviation_detector.detect_nutrient_deviation(
            meal_log.planned_nutrients,
            meal_log.consumed_nutrients
        )
        
        for nutrient, deviated, severity, percent in nutrient_deviations:
            if deviated and severity in [DeviationSeverity.MODERATE, DeviationSeverity.HIGH]:
                if meal_log.consumed_nutrients.get(nutrient, 0) > meal_log.planned_nutrients.get(nutrient, 0):
                    actions.append(AdaptationAction(
                        action_id=f"adapt_{datetime.now().timestamp()}_3_{nutrient}",
                        trigger_type=AdaptationTrigger.MEAL_DEVIATION,
                        action_type="modify_nutrients",
                        parameters={
                            "nutrient": nutrient,
                            "adjustment_type": "decrease",
                            "percentage": 0.15
                        },
                        priority=4 if severity == DeviationSeverity.HIGH else 3,
                        reason=f"User consistently exceeds {nutrient} targets",
                        timestamp=datetime.now()
                    ))
        
        # Consecutive deviation adaptations
        if consecutive_pattern:
            if consecutive_severity == DeviationSeverity.HIGH:
                actions.append(AdaptationAction(
                    action_id=f"adapt_{datetime.now().timestamp()}_4",
                    trigger_type=AdaptationTrigger.MEAL_DEVIATION,
                    action_type="alert_supervisor",
                    parameters={
                        "reason": "consecutive_high_severity_deviations",
                        "deviation_count": len([
                            m for m in self.meal_history.get(meal_log.user_id, [])
                            if m.deviation_detected
                        ])
                    },
                    priority=5,
                    reason="User showing pattern of high-severity deviations - supervisor alert recommended",
                    timestamp=datetime.now()
                ))
            else:
                actions.append(AdaptationAction(
                    action_id=f"adapt_{datetime.now().timestamp()}_5",
                    trigger_type=AdaptationTrigger.MEAL_DEVIATION,
                    action_type="modify_nutrients",
                    parameters={
                        "adjustment_type": "conservative",
                        "percentage": 0.05
                    },
                    priority=3,
                    reason="User showing pattern of deviations - applying conservative adjustments",
                    timestamp=datetime.now()
                ))
        
        return actions
    
    def _generate_deviation_alert(
        self,
        meal_log: MealLog,
        consecutive_pattern: bool,
        consecutive_severity: DeviationSeverity
    ) -> DeviationAlert:
        """Generate deviation alert for user/supervisor"""
        
        if consecutive_pattern and consecutive_severity == DeviationSeverity.HIGH:
            message = f"CRITICAL: Pattern of high-severity deviations detected in {meal_log.meal_type}. User has exceeded targets in multiple recent meals."
            recommended_action = "Immediate supervisor review recommended. Consider adjusting meal plan or providing additional support."
            severity = DeviationSeverity.CRITICAL
        elif meal_log.deviation_severity == DeviationSeverity.HIGH:
            message = f"High-severity deviation detected in {meal_log.meal_type}: {meal_log.consumed_calories} calories consumed vs {meal_log.planned_calories} planned."
            recommended_action = "Monitor next few meals closely. Consider if meal plan needs adjustment."
            severity = DeviationSeverity.HIGH
        elif consecutive_pattern:
            message = f"Pattern of deviations detected in recent meals. User consistently deviates from {meal_log.meal_type} targets."
            recommended_action = "Review meal plan and consider adjustments. Monitor adherence."
            severity = DeviationSeverity.MODERATE
        else:
            message = f"Deviation detected in {meal_log.meal_type}: {meal_log.consumed_calories} calories consumed vs {meal_log.planned_calories} planned."
            recommended_action = "Continue monitoring. Provide encouragement for adherence."
            severity = meal_log.deviation_severity
        
        return DeviationAlert(
            alert_id=f"alert_{datetime.now().timestamp()}",
            user_id=meal_log.user_id,
            deviation_type=meal_log.deviation_type or "general",
            severity=severity,
            message=message,
            recommended_action=recommended_action,
            timestamp=datetime.now()
        )
    
    def get_user_adaptations(
        self,
        user_id: str,
        active_only: bool = True
    ) -> List[AdaptationAction]:
        """Get adaptation actions for a user"""
        if user_id not in self.active_adaptations:
            return []
        
        if active_only:
            return [action for action in self.active_adaptations[user_id] if not action.executed]
        else:
            return self.active_adaptations[user_id]
    
    def execute_adaptation(
        self,
        action_id: str,
        user_id: str
    ) -> bool:
        """Execute an adaptation action"""
        if user_id not in self.active_adaptations:
            return False
        
        for action in self.active_adaptations[user_id]:
            if action.action_id == action_id and not action.executed:
                # Mark as executed
                action.executed = True
                action.result = f"Executed at {datetime.now().isoformat()}"
                return True
        
        return False
    
    def get_user_alerts(
        self,
        user_id: str,
        unresolved_only: bool = True
    ) -> List[DeviationAlert]:
        """Get alerts for a user"""
        if user_id not in self.alert_history:
            return []
        
        if unresolved_only:
            return [alert for alert in self.alert_history[user_id] if not alert.resolved]
        else:
            return self.alert_history[user_id]
    
    def acknowledge_alert(
        self,
        alert_id: str,
        user_id: str
    ) -> bool:
        """Acknowledge an alert"""
        if user_id not in self.alert_history:
            return False
        
        for alert in self.alert_history[user_id]:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                return True
        
        return False
    
    def resolve_alert(
        self,
        alert_id: str,
        user_id: str,
        resolution_note: str = ""
    ) -> bool:
        """Resolve an alert"""
        if user_id not in self.alert_history:
            return False
        
        for alert in self.alert_history[user_id]:
            if alert.alert_id == alert_id:
                alert.resolved = True
                return True
        
        return False
    
    def learn_user_patterns(
        self,
        user_id: str
    ) -> List[UserPattern]:
        """Learn and update user behavior patterns"""
        if user_id not in self.meal_history or len(self.meal_history[user_id]) < 5:
            return []
        
        user_meals = self.meal_history[user_id]
        patterns = []
        
        # Learn meal timing patterns
        timing_pattern = self._learn_timing_pattern(user_meals)
        if timing_pattern:
            patterns.append(timing_pattern)
        
        # Learn portion size patterns
        portion_pattern = self._learn_portion_pattern(user_meals)
        if portion_pattern:
            patterns.append(portion_pattern)
        
        # Learn adherence patterns
        adherence_pattern = self._learn_adherence_pattern(user_meals)
        if adherence_pattern:
            patterns.append(adherence_pattern)
        
        # Store patterns
        if user_id not in self.user_patterns:
            self.user_patterns[user_id] = []
        self.user_patterns[user_id].extend(patterns)

        for pat in patterns:
            try:
                db.upsert_user_pattern(
                    user_id=user_id,
                    pattern_type=pat.pattern_type,
                    pattern_data=pat.pattern_data,
                    confidence=pat.confidence,
                    sample_size=pat.sample_size,
                )
            except Exception:
                pass
        
        return patterns

    
    def _learn_timing_pattern(
        self,
        meals: List[MealLog]
    ) -> Optional[UserPattern]:
        """Learn user's meal timing patterns"""
        if len(meals) < 5:
            return None
        
        # Group by meal type
        meal_times = {}
        for meal in meals:
            if meal.meal_type not in meal_times:
                meal_times[meal.meal_type] = []
            meal_times[meal.meal_type].append(meal.timestamp.hour)
        
        # Calculate average times
        pattern_data = {}
        for meal_type, times in meal_times.items():
            if len(times) >= 3:
                avg_time = sum(times) / len(times)
                pattern_data[meal_type] = {
                    "average_hour": int(avg_time),
                    "range_minutes": 60,  # Default 1-hour window
                    "consistency": 0.8  # Placeholder for actual consistency calculation
                }
        
        if pattern_data:
            return UserPattern(
                user_id=meals[0].user_id,
                pattern_type="meal_timing",
                pattern_data=pattern_data,
                confidence=0.7,
                last_updated=datetime.now(),
                sample_size=len(meals)
            )
        return None
    
    def _learn_portion_pattern(
        self,
        meals: List[MealLog]
    ) -> Optional[UserPattern]:
        """Learn user's portion size patterns"""
        if len(meals) < 5:
            return None
        
        # Calculate average deviation ratios
        deviation_ratios = []
        for meal in meals:
            if meal.planned_calories > 0:
                ratio = meal.consumed_calories / meal.planned_calories
                deviation_ratios.append(ratio)
        
        if not deviation_ratios:
            return None
        
        avg_ratio = sum(deviation_ratios) / len(deviation_ratios)
        
        pattern_data = {
            "average_consumption_ratio": round(avg_ratio, 2),
            "tendency": "over" if avg_ratio > 1.05 else "under" if avg_ratio < 0.95 else "accurate",
            "variability": 0.15  # Placeholder for actual variability calculation
        }
        
        return UserPattern(
            user_id=meals[0].user_id,
            pattern_type="portion_size",
            pattern_data=pattern_data,
            confidence=0.6,
            last_updated=datetime.now(),
            sample_size=len(meals)
        )
    
    def _learn_adherence_pattern(
        self,
        meals: List[MealLog]
    ) -> Optional[UserPattern]:
        """Learn user's adherence patterns"""
        if len(meals) < 5:
            return None
        
        adherent_meals = sum(1 for meal in meals if not meal.deviation_detected)
        adherence_rate = adherent_meals / len(meals)
        
        pattern_data = {
            "adherence_rate": round(adherence_rate, 2),
            "trend": "improving" if adherence_rate > 0.7 else "declining" if adherence_rate < 0.5 else "stable",
            "problem_meal_types": self._identify_problem_meal_types(meals)
        }
        
        return UserPattern(
            user_id=meals[0].user_id,
            pattern_type="adherence",
            pattern_data=pattern_data,
            confidence=0.8,
            last_updated=datetime.now(),
            sample_size=len(meals)
        )
    
    def _identify_problem_meal_types(
        self,
        meals: List[MealLog]
    ) -> List[str]:
        """Identify which meal types have most deviations"""
        meal_type_deviations = {}
        for meal in meals:
            if meal.deviation_detected:
                if meal.meal_type not in meal_type_deviations:
                    meal_type_deviations[meal.meal_type] = 0
                meal_type_deviations[meal.meal_type] += 1
        
        # Sort by deviation count
        sorted_types = sorted(
            meal_type_deviations.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [meal_type for meal_type, count in sorted_types[:2]]  # Top 2 problem types
    
    def get_adaptation_summary(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """Get summary of adaptation status for a user"""
        active_actions = self.get_user_adaptations(user_id, active_only=True)
        unresolved_alerts = self.get_user_alerts(user_id, unresolved_only=True)
        user_patterns = self.user_patterns.get(user_id, [])
        recent_meals = self.meal_history.get(user_id, [])[-10:]  # Last 10 meals
        
        return {
            "user_id": user_id,
            "active_adaptations": len(active_actions),
            "pending_adaptations": [
                {
                    "action_id": action.action_id,
                    "action_type": action.action_type,
                    "priority": action.priority,
                    "reason": action.reason
                }
                for action in active_actions[:5]  # Top 5 priority actions
            ],
            "unresolved_alerts": len(unresolved_alerts),
            "recent_alerts": [
                {
                    "alert_id": alert.alert_id,
                    "severity": alert.severity.value,
                    "message": alert.message,
                    "timestamp": alert.timestamp.isoformat()
                }
                for alert in unresolved_alerts[-3:]  # Last 3 alerts
            ],
            "learned_patterns": len(user_patterns),
            "pattern_summary": [
                {
                    "pattern_type": pattern.pattern_type,
                    "confidence": pattern.confidence,
                    "last_updated": pattern.last_updated.isoformat()
                }
                for pattern in user_patterns[-3:]  # Last 3 patterns
            ],
            "recent_meal_count": len(recent_meals),
            "adherence_rate": sum(1 for meal in recent_meals if not meal.deviation_detected) / len(recent_meals) if recent_meals else 0.0
        }


# Global adaptation engine instance
adaptation_engine = AdaptationEngine()