"""
Feedback and Learning System
Collects user feedback, tracks outcomes, and continuously improves recommendations
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
from datetime import datetime, timedelta
import json
from collections import defaultdict

from backend import db


class FeedbackType(Enum):
    """Types of user feedback"""
    MEAL_RATING = "meal_rating"
    SATISFACTION = "satisfaction"
    ADHERENCE = "adherence"
    SYMPTOM_REPORT = "symptom_report"
    SUGGESTION = "suggestion"
    COMPLAINT = "complaint"
    TECHNICAL_ISSUE = "technical_issue"


class FeedbackSource(Enum):
    """Sources of feedback"""
    USER_APP = "user_app"
    CAREGIVER_APP = "caregiver_app"
    CLINICIAN_PORTAL = "clinician_portal"
    AUTOMATED = "automated"
    SURVEY = "survey"


class OutcomeType(Enum):
    """Types of health outcomes to track"""
    WEIGHT_CHANGE = "weight_change"
    BLOOD_PRESSURE_CHANGE = "blood_pressure_change"
    BLOOD_GLUCOSE_CHANGE = "blood_glucose_change"
    KIDNEY_FUNCTION_CHANGE = "kidney_function_change"
    SYMPTOM_IMPROVEMENT = "symptom_improvement"
    HOSPITALIZATION = "hospitalization"
    MEDICATION_ADJUSTMENT = "medication_adjustment"
    QUALITY_OF_LIFE = "quality_of_life"


class LearningSignal(Enum):
    """Types of learning signals for system improvement"""
    POSITIVE_REINFORCEMENT = "positive_reinforcement"
    NEGATIVE_REINFORCEMENT = "negative_reinforcement"
    PATTERN_DETECTED = "pattern_detected"
    ANOMALY_DETECTED = "anomaly_detected"
    TREND_IDENTIFIED = "trend_identified"


@dataclass
class UserFeedback:
    """Individual user feedback entry"""
    feedback_id: str
    user_id: str
    feedback_type: FeedbackType
    source: FeedbackSource
    rating: Optional[int] = None  # 1-5 scale for ratings
    text_feedback: str = ""
    meal_id: Optional[str] = None
    recommendation_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    processed: bool = False


@dataclass
class HealthOutcome:
    """Health outcome measurement"""
    outcome_id: str
    user_id: str
    outcome_type: OutcomeType
    value: float
    unit: str
    baseline_value: Optional[float] = None
    change_from_baseline: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)
    measurement_context: Dict[str, Any] = field(default_factory=dict)
    clinical_significance: str = "unknown"


@dataclass
class LearningEvent:
    """Learning event for system improvement"""
    event_id: str
    signal_type: LearningSignal
    confidence: float  # 0.0 to 1.0
    description: str
    affected_components: List[str]
    suggested_actions: List[str]
    timestamp: datetime = field(default_factory=datetime.now)
    priority: int = 3  # 1-5 scale
    implemented: bool = False
    impact_assessment: Optional[str] = None


@dataclass
class RecommendationPerformance:
    """Performance tracking for recommendations"""
    recommendation_id: str
    user_id: str
    recommendation_type: str
    acceptance_rate: float
    adherence_rate: float
    satisfaction_score: float
    sample_size: int
    health_outcome_correlation: Optional[float] = None
    last_updated: datetime = field(default_factory=datetime.now)


class FeedbackCollector:
    """Collects and processes user feedback"""
    
    def __init__(self):
        self.feedback_history: Dict[str, List[UserFeedback]] = {}
        self.feedback_aggregates: Dict[str, Dict[str, Any]] = {}
    
    def collect_feedback(
        self,
        user_id: str,
        feedback_type: FeedbackType,
        source: FeedbackSource,
        rating: Optional[int] = None,
        text_feedback: str = "",
        meal_id: Optional[str] = None,
        recommendation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UserFeedback:
        """Collect user feedback"""
        
        feedback = UserFeedback(
            feedback_id=f"feedback_{datetime.now().timestamp()}",
            user_id=user_id,
            feedback_type=feedback_type,
            source=source,
            rating=rating,
            text_feedback=text_feedback,
            meal_id=meal_id,
            recommendation_id=recommendation_id,
            metadata=metadata or {}
        )
        
        # Store feedback
        if user_id not in self.feedback_history:
            self.feedback_history[user_id] = []
        self.feedback_history[user_id].append(feedback)

        try:
            db.insert_feedback_record(
                user_id=user_id,
                feedback_type=feedback.feedback_type.value,
                source=feedback.source.value,
                rating=feedback.rating,
                text_feedback=feedback.text_feedback,
                meal_id=feedback.meal_id,
                recommendation_id=feedback.recommendation_id,
                metadata=feedback.metadata,
            )
        except Exception:
            pass
        
        # Update aggregates
        self._update_aggregates(user_id, feedback)
        
        return feedback

    
    def _update_aggregates(self, user_id: str, feedback: UserFeedback):
        """Update feedback aggregates for a user"""
        if user_id not in self.feedback_aggregates:
            self.feedback_aggregates[user_id] = {
                "total_feedback": 0,
                "average_rating": 0.0,
                "feedback_by_type": defaultdict(int),
                "feedback_by_source": defaultdict(int),
                "recent_feedback": []
            }
        
        aggregates = self.feedback_aggregates[user_id]
        aggregates["total_feedback"] += 1
        aggregates["feedback_by_type"][feedback.feedback_type.value] += 1
        aggregates["feedback_by_source"][feedback.source.value] += 1
        
        # Update average rating
        if feedback.rating is not None:
            current_avg = aggregates["average_rating"]
            current_count = aggregates["total_feedback"]
            new_avg = ((current_avg * (current_count - 1)) + feedback.rating) / current_count
            aggregates["average_rating"] = new_avg
        
        # Keep recent feedback
        aggregates["recent_feedback"].append({
            "feedback_id": feedback.feedback_id,
            "type": feedback.feedback_type.value,
            "rating": feedback.rating,
            "timestamp": feedback.timestamp.isoformat()
        })
        
        # Keep only last 20 feedback entries
        if len(aggregates["recent_feedback"]) > 20:
            aggregates["recent_feedback"] = aggregates["recent_feedback"][-20:]
    
    def get_user_feedback_summary(
        self,
        user_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get feedback summary for a user"""
        if user_id not in self.feedback_history:
            return {
                "user_id": user_id,
                "total_feedback": 0,
                "average_rating": 0.0,
                "feedback_by_type": {},
                "feedback_by_source": {}
            }
        
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_feedback = [
            f for f in self.feedback_history[user_id]
            if f.timestamp >= cutoff_date
        ]
        
        if not recent_feedback:
            return {
                "user_id": user_id,
                "total_feedback": 0,
                "average_rating": 0.0,
                "feedback_by_type": {},
                "feedback_by_source": {}
            }
        
        # Calculate statistics
        ratings = [f.rating for f in recent_feedback if f.rating is not None]
        average_rating = sum(ratings) / len(ratings) if ratings else 0.0
        
        feedback_by_type = defaultdict(int)
        feedback_by_source = defaultdict(int)
        
        for feedback in recent_feedback:
            feedback_by_type[feedback.feedback_type.value] += 1
            feedback_by_source[feedback.source.value] += 1
        
        return {
            "user_id": user_id,
            "period_days": days,
            "total_feedback": len(recent_feedback),
            "average_rating": round(average_rating, 2),
            "feedback_by_type": dict(feedback_by_type),
            "feedback_by_source": dict(feedback_by_source),
            "satisfaction_trend": self._calculate_satisfaction_trend(recent_feedback)
        }
    
    def _calculate_satisfaction_trend(
        self,
        feedback_list: List[UserFeedback]
    ) -> str:
        """Calculate satisfaction trend from feedback"""
        if len(feedback_list) < 3:
            return "insufficient_data"
        
        # Sort by timestamp
        sorted_feedback = sorted(feedback_list, key=lambda f: f.timestamp)
        
        # Split into first half and second half
        mid_point = len(sorted_feedback) // 2
        first_half = sorted_feedback[:mid_point]
        second_half = sorted_feedback[mid_point:]
        
        # Calculate average ratings
        first_ratings = [f.rating for f in first_half if f.rating is not None]
        second_ratings = [f.rating for f in second_half if f.rating is not None]
        
        if not first_ratings or not second_ratings:
            return "insufficient_data"
        
        first_avg = sum(first_ratings) / len(first_ratings)
        second_avg = sum(second_ratings) / len(second_ratings)
        
        if second_avg > first_avg + 0.5:
            return "improving"
        elif second_avg < first_avg - 0.5:
            return "declining"
        else:
            return "stable"


class OutcomeTracker:
    """Tracks health outcomes and correlates with recommendations"""
    
    def __init__(self):
        self.outcome_history: Dict[str, List[HealthOutcome]] = {}
        self.baseline_values: Dict[str, Dict[str, float]] = {}
    
    def record_outcome(
        self,
        user_id: str,
        outcome_type: OutcomeType,
        value: float,
        unit: str,
        measurement_context: Optional[Dict[str, Any]] = None
    ) -> HealthOutcome:
        """Record a health outcome"""
        
        # Get baseline if not set
        if user_id not in self.baseline_values:
            self.baseline_values[user_id] = {}
        
        outcome_key = f"{outcome_type.value}_{unit}"
        if outcome_key not in self.baseline_values[user_id]:
            self.baseline_values[user_id][outcome_key] = value
            baseline_value = value
            change_from_baseline = 0.0
        else:
            baseline_value = self.baseline_values[user_id][outcome_key]
            change_from_baseline = value - baseline_value
        
        # Determine clinical significance
        clinical_significance = self._assess_clinical_significance(
            outcome_type, change_from_baseline, unit
        )
        
        outcome = HealthOutcome(
            outcome_id=f"outcome_{datetime.now().timestamp()}",
            user_id=user_id,
            outcome_type=outcome_type,
            value=value,
            unit=unit,
            baseline_value=baseline_value,
            change_from_baseline=change_from_baseline,
            measurement_context=measurement_context or {},
            clinical_significance=clinical_significance
        )
        
        # Store outcome
        if user_id not in self.outcome_history:
            self.outcome_history[user_id] = []
        self.outcome_history[user_id].append(outcome)

        try:
            db.insert_health_outcome(
                user_id=user_id,
                outcome_type=outcome.outcome_type.value,
                value=outcome.value,
                unit=outcome.unit,
                baseline_value=outcome.baseline_value,
                change_from_baseline=outcome.change_from_baseline,
                clinical_significance=outcome.clinical_significance,
                measurement_context=outcome.measurement_context,
            )
        except Exception:
            pass
        
        return outcome

    
    def _assess_clinical_significance(
        self,
        outcome_type: OutcomeType,
        change: float,
        unit: str
    ) -> str:
        """Assess clinical significance of outcome change"""
        
        # Define clinically significant thresholds
        significance_thresholds = {
            OutcomeType.WEIGHT_CHANGE: {
                "kg": 2.0,  # 2kg change is significant
                "lbs": 4.4
            },
            OutcomeType.BLOOD_PRESSURE_CHANGE: {
                "mmHg": 5.0  # 5mmHg change is significant
            },
            OutcomeType.BLOOD_GLUCOSE_CHANGE: {
                "mg_dl": 20.0,  # 20mg/dL change is significant
                "mmol_l": 1.1
            },
            OutcomeType.KIDNEY_FUNCTION_CHANGE: {
                "egfr": 5.0,  # 5 mL/min/1.73m² change is significant
                "creatinine": 0.2  # 0.2 mg/dL change is significant
            }
        }
        
        thresholds = significance_thresholds.get(outcome_type, {})
        threshold = thresholds.get(unit, float('inf'))
        
        if abs(change) >= threshold:
            if change > 0:
                return "significant_improvement" if outcome_type in [
                    OutcomeType.SYMPTOM_IMPROVEMENT, OutcomeType.QUALITY_OF_LIFE
                ] else "significant_deterioration"
            else:
                return "significant_improvement" if outcome_type not in [
                    OutcomeType.SYMPTOM_IMPROVEMENT, OutcomeType.QUALITY_OF_LIFE
                ] else "significant_deterioration"
        else:
            return "not_significant"
    
    def get_outcome_trends(
        self,
        user_id: str,
        outcome_type: Optional[OutcomeType] = None,
        days: int = 90
    ) -> Dict[str, Any]:
        """Get outcome trends for a user"""
        if user_id not in self.outcome_history:
            return {
                "user_id": user_id,
                "outcomes": [],
                "trends": {},
                "clinical_significance": "no_data"
            }
        
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_outcomes = [
            o for o in self.outcome_history[user_id]
            if o.timestamp >= cutoff_date and (outcome_type is None or o.outcome_type == outcome_type)
        ]
        
        if not recent_outcomes:
            return {
                "user_id": user_id,
                "outcomes": [],
                "trends": {},
                "clinical_significance": "no_data"
            }
        
        # Group by outcome type
        outcomes_by_type = defaultdict(list)
        for outcome in recent_outcomes:
            outcomes_by_type[outcome.outcome_type.value].append(outcome)
        
        # Calculate trends
        trends = {}
        for type_name, outcomes in outcomes_by_type.items():
            if len(outcomes) < 2:
                trends[type_name] = "insufficient_data"
                continue
            
            # Sort by timestamp
            sorted_outcomes = sorted(outcomes, key=lambda o: o.timestamp)
            
            # Calculate trend
            first_value = sorted_outcomes[0].value
            last_value = sorted_outcomes[-1].value
            change = last_value - first_value
            
            if change > 0:
                trends[type_name] = "improving" if type_name in [
                    "symptom_improvement", "quality_of_life"
                ] else "worsening"
            elif change < 0:
                trends[type_name] = "worsening" if type_name in [
                    "symptom_improvement", "quality_of_life"
                ] else "improving"
            else:
                trends[type_name] = "stable"
        
        # Determine overall clinical significance
        significant_changes = [
            o for o in recent_outcomes
            if o.clinical_significance in ["significant_improvement", "significant_deterioration"]
        ]
        
        if significant_changes:
            deteriorations = [o for o in significant_changes if o.clinical_significance == "significant_deterioration"]
            improvements = [o for o in significant_changes if o.clinical_significance == "significant_improvement"]
            
            if len(deteriorations) > len(improvements):
                overall_significance = "concerning"
            elif len(improvements) > len(deteriorations):
                overall_significance = "positive"
            else:
                overall_significance = "mixed"
        else:
            overall_significance = "stable"
        
        return {
            "user_id": user_id,
            "period_days": days,
            "outcome_count": len(recent_outcomes),
            "outcomes_by_type": {
                type_name: len(outcomes) for type_name, outcomes in outcomes_by_type.items()
            },
            "trends": trends,
            "clinical_significance": overall_significance,
            "significant_changes": [
                {
                    "type": o.outcome_type.value,
                    "change": o.change_from_baseline,
                    "significance": o.clinical_significance,
                    "timestamp": o.timestamp.isoformat()
                }
                for o in significant_changes[-5:]  # Last 5 significant changes
            ]
        }


class LearningEngine:
    """Learning engine for system improvement"""
    
    def __init__(self):
        self.learning_events: List[LearningEvent] = []
        self.recommendation_performance: Dict[str, RecommendationPerformance] = {}
        self.patterns_detected: Dict[str, List[Dict[str, Any]]] = {}
    
    def analyze_feedback_patterns(
        self,
        feedback_data: Dict[str, List[UserFeedback]]
    ) -> List[LearningEvent]:
        """Analyze feedback patterns to generate learning events"""
        learning_events = []
        
        for user_id, user_feedback_list in feedback_data.items():
            if len(user_feedback_list) < 5:
                continue
            
            # Analyze rating patterns
            ratings = [f.rating for f in user_feedback_list if f.rating is not None]
            if ratings:
                avg_rating = sum(ratings) / len(ratings)
                
                if avg_rating < 2.5:
                    learning_events.append(LearningEvent(
                        event_id=f"learning_{datetime.now().timestamp()}_{user_id}",
                        signal_type=LearningSignal.NEGATIVE_REINFORCEMENT,
                        confidence=0.7,
                        description=f"User {user_id} consistently provides low ratings (avg: {avg_rating:.2f})",
                        affected_components=["meal_recommendation", "user_interface"],
                        suggested_actions=[
                            "Review meal recommendations for this user",
                            "Consider adjusting recommendation algorithm",
                            "Reach out for detailed feedback"
                        ],
                        priority=4
                    ))
                elif avg_rating > 4.5:
                    learning_events.append(LearningEvent(
                        event_id=f"learning_{datetime.now().timestamp()}_{user_id}",
                        signal_type=LearningSignal.POSITIVE_REINFORCEMENT,
                        confidence=0.8,
                        description=f"User {user_id} consistently provides high ratings (avg: {avg_rating:.2f})",
                        affected_components=["meal_recommendation"],
                        suggested_actions=[
                            "Continue current recommendation strategy",
                            "Use as positive example for similar users"
                        ],
                        priority=2
                    ))
            
            # Analyze text feedback patterns
            text_feedback = [f.text_feedback.lower() for f in user_feedback_list if f.text_feedback]
            if text_feedback:
                # Look for common complaints
                complaint_keywords = ["bland", "boring", "same", "repetitive", "difficult", "time"]
                complaint_counts = defaultdict(int)
                
                for feedback_text in text_feedback:
                    for keyword in complaint_keywords:
                        if keyword in feedback_text:
                            complaint_counts[keyword] += 1
                
                for keyword, count in complaint_counts.items():
                    if count >= 2:
                        learning_events.append(LearningEvent(
                            event_id=f"learning_{datetime.now().timestamp()}_{keyword}_{user_id}",
                            signal_type=LearningSignal.PATTERN_DETECTED,
                            confidence=0.6,
                            description=f"User {user_id} repeatedly mentions '{keyword}' in feedback",
                            affected_components=["meal_variety", "recipe_complexity"],
                            suggested_actions=[
                                f"Increase variety in {keyword} aspect",
                                f"Adjust recommendations to address {keyword} concern"
                            ],
                            priority=3
                        ))
        
        return learning_events
    
    def correlate_outcomes_with_recommendations(
        self,
        outcome_data: Dict[str, List[HealthOutcome]],
        recommendation_data: Dict[str, List[str]]
    ) -> List[LearningEvent]:
        """Correlate health outcomes with recommendations"""
        learning_events = []
        
        for user_id, outcomes in outcome_data.items():
            if user_id not in recommendation_data:
                continue
            
            user_recommendations = recommendation_data[user_id]
            
            # Look for positive correlations
            positive_outcomes = [
                o for o in outcomes
                if o.clinical_significance == "significant_improvement"
            ]
            
            if len(positive_outcomes) >= 2:
                learning_events.append(LearningEvent(
                    event_id=f"learning_{datetime.now().timestamp()}_positive_{user_id}",
                    signal_type=LearningSignal.POSITIVE_REINFORCEMENT,
                    confidence=0.7,
                    description=f"User {user_id} showing positive health outcomes with current recommendations",
                    affected_components=["meal_recommendation", "diet_plan"],
                    suggested_actions=[
                        "Continue current recommendation strategy",
                        "Analyze successful patterns for broader application"
                    ],
                    priority=2
                ))
            
            # Look for negative correlations
            negative_outcomes = [
                o for o in outcomes
                if o.clinical_significance == "significant_deterioration"
            ]
            
            if len(negative_outcomes) >= 2:
                learning_events.append(LearningEvent(
                    event_id=f"learning_{datetime.now().timestamp()}_negative_{user_id}",
                    signal_type=LearningSignal.NEGATIVE_REINFORCEMENT,
                    confidence=0.8,
                    description=f"User {user_id} showing negative health outcomes - recommendation review needed",
                    affected_components=["meal_recommendation", "safety_checks"],
                    suggested_actions=[
                        "Immediate review of meal recommendations",
                        "Consider medical consultation",
                        "Review adherence and external factors"
                    ],
                    priority=5
                ))
        
        return learning_events
    
    def track_recommendation_performance(
        self,
        recommendation_id: str,
        user_id: str,
        recommendation_type: str,
        accepted: bool,
        adhered: bool,
        satisfaction: Optional[int] = None
    ):
        """Track performance of individual recommendations"""
        
        if recommendation_id not in self.recommendation_performance:
            self.recommendation_performance[recommendation_id] = RecommendationPerformance(
                recommendation_id=recommendation_id,
                user_id=user_id,
                recommendation_type=recommendation_type,
                acceptance_rate=0.0,
                adherence_rate=0.0,
                satisfaction_score=0.0,
                sample_size=0
            )
        
        perf = self.recommendation_performance[recommendation_id]
        perf.sample_size += 1
        
        # Update acceptance rate
        current_acceptance_rate = perf.acceptance_rate
        new_acceptance_rate = ((current_acceptance_rate * (perf.sample_size - 1)) + (1 if accepted else 0)) / perf.sample_size
        perf.acceptance_rate = new_acceptance_rate
        
        # Update adherence rate
        current_adherence_rate = perf.adherence_rate
        new_adherence_rate = ((current_adherence_rate * (perf.sample_size - 1)) + (1 if adhered else 0)) / perf.sample_size
        perf.adherence_rate = new_adherence_rate
        
        # Update satisfaction score
        if satisfaction is not None:
            current_satisfaction = perf.satisfaction_score
            new_satisfaction = ((current_satisfaction * (perf.sample_size - 1)) + satisfaction) / perf.sample_size
            perf.satisfaction_score = new_satisfaction
        
        perf.last_updated = datetime.now()
    
    def get_learning_summary(self) -> Dict[str, Any]:
        """Get summary of learning events and system performance"""
        
        # Count learning events by type
        events_by_type = defaultdict(int)
        for event in self.learning_events:
            events_by_type[event.signal_type.value] += 1
        
        # Count high-priority unimplemented events
        high_priority_unimplemented = [
            e for e in self.learning_events
            if e.priority >= 4 and not e.implemented
        ]
        
        # Calculate overall recommendation performance
        if self.recommendation_performance:
            avg_acceptance = sum(p.acceptance_rate for p in self.recommendation_performance.values()) / len(self.recommendation_performance)
            avg_adherence = sum(p.adherence_rate for p in self.recommendation_performance.values()) / len(self.recommendation_performance)
            avg_satisfaction = sum(p.satisfaction_score for p in self.recommendation_performance.values() if p.satisfaction_score > 0) / len([p for p in self.recommendation_performance.values() if p.satisfaction_score > 0]) if any(p.satisfaction_score > 0 for p in self.recommendation_performance.values()) else 0.0
        else:
            avg_acceptance = 0.0
            avg_adherence = 0.0
            avg_satisfaction = 0.0
        
        return {
            "total_learning_events": len(self.learning_events),
            "events_by_type": dict(events_by_type),
            "high_priority_unimplemented": len(high_priority_unimplemented),
            "total_recommendations_tracked": len(self.recommendation_performance),
            "average_acceptance_rate": round(avg_acceptance, 3),
            "average_adherence_rate": round(avg_adherence, 3),
            "average_satisfaction_score": round(avg_satisfaction, 3),
            "recent_learning_events": [
                {
                    "event_id": e.event_id,
                    "signal_type": e.signal_type.value,
                    "description": e.description,
                    "priority": e.priority,
                    "implemented": e.implemented,
                    "timestamp": e.timestamp.isoformat()
                }
                for e in self.learning_events[-10:]  # Last 10 events
            ]
        }
    
    def implement_learning_action(
        self,
        event_id: str,
        implementation_notes: str = ""
    ) -> bool:
        """Mark a learning event as implemented"""
        for event in self.learning_events:
            if event.event_id == event_id:
                event.implemented = True
                event.impact_assessment = implementation_notes
                return True
        return False


# Global feedback and learning system instances
feedback_collector = FeedbackCollector()
outcome_tracker = OutcomeTracker()
learning_engine = LearningEngine()