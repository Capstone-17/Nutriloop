"""
Agentic AI Engine for Meal Planning and Recommendations
Implements LLM-based agent for personalized meal synthesis and conversational assistance
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
from datetime import datetime, timedelta
import random


class AgentIntent(Enum):
    """Types of user intents the agent can handle"""
    MEAL_PLAN_REQUEST = "meal_plan_request"
    RECIPE_SUGGESTION = "recipe_suggestion"
    NUTRITION_QUERY = "nutrition_query"
    DIETARY_ADVICE = "dietary_advice"
    MEAL_SUBSTITUTION = "meal_substitution"
    SYMPTOM_CHECK = "symptom_check"
    GENERAL_CHAT = "general_chat"


class MealType(Enum):
    """Types of meals"""
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"


@dataclass
class UserProfile:
    """User profile for personalization"""
    user_id: str
    disease: str
    risk_level: str
    dietary_preferences: List[str] = field(default_factory=list)
    allergies: List[str] = field(default_factory=list)
    medications: List[str] = field(default_factory=list)
    calorie_target: int = 2000
    cultural_preferences: List[str] = field(default_factory=list)
    cooking_skill: str = "intermediate"  # beginner, intermediate, advanced
    time_constraints: str = "moderate"  # low, moderate, high


@dataclass
class MealPlan:
    """Generated meal plan"""
    meal_type: MealType
    meal_name: str
    ingredients: List[Dict[str, Any]]
    instructions: List[str]
    nutritional_info: Dict[str, float]
    preparation_time: int  # minutes
    difficulty: str
    safety_score: float
    medical_compliance: Dict[str, str]
    substitutions: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class AgentResponse:
    """Agent response structure"""
    intent: AgentIntent
    content: str
    meal_plans: List[MealPlan] = field(default_factory=list)
    safety_alerts: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    follow_up_questions: List[str] = field(default_factory=list)
    confidence: float = 0.0
    requires_medical_supervision: bool = False


class MedicalKnowledgeBase:
    """Medical knowledge base for dietary guidelines"""
    
    DISEASE_SPECIFIC_GUIDANCE = {
        "ckd": {
            "general_advice": [
                "Focus on controlling sodium, potassium, and phosphorus intake",
                "Choose lower protein portions to reduce kidney workload",
                "Prefer fresh foods over processed to control sodium",
                "Monitor fluid intake if advised by your nephrologist"
            ],
            "food_recommendations": [
                "White bread and rice over whole grains (lower phosphorus)",
                "Apples, berries, and grapes (lower potassium fruits)",
                "Egg whites (high quality protein, lower phosphorus)",
                "Cauliflower, cabbage, and green beans (lower potassium vegetables)"
            ],
            "food_avoid": [
                "Processed meats (high sodium and phosphorus)",
                "Bananas, oranges, and avocados (high potassium)",
                "Dairy products (high phosphorus and potassium)",
                "Nuts and seeds (high phosphorus and potassium)"
            ],
            "cooking_tips": [
                "Rinse canned foods to reduce sodium",
                "Use herbs and spices instead of salt for flavor",
                "Leach potatoes to reduce potassium content",
                "Portion control is essential for all foods"
            ]
        },
        "diabetes": {
            "general_advice": [
                "Focus on consistent carbohydrate intake throughout the day",
                "Choose complex carbohydrates with fiber over simple sugars",
                "Monitor blood glucose levels regularly",
                "Time meals appropriately with medication schedules"
            ],
            "food_recommendations": [
                "Whole grains, legumes, and vegetables (complex carbs)",
                "Lean proteins and healthy fats",
                "Foods with low glycemic index",
                "High fiber foods to help control blood sugar"
            ],
            "food_avoid": [
                "Sugary beverages and sweets",
                "Refined carbohydrates and white flour products",
                "High glycemic index fruits in large quantities",
                "Processed foods with hidden sugars"
            ],
            "cooking_tips": [
                "Use smaller portions of carbohydrate foods",
                "Pair carbohydrates with protein and healthy fats",
                "Choose cooking methods that don't add extra sugar",
                "Read food labels for hidden carbohydrates and sugars"
            ]
        },
        "hypertension": {
            "general_advice": [
                "Strict sodium control is essential for blood pressure management",
                "Increase potassium intake through fruits and vegetables",
                "Maintain healthy weight through calorie control",
                "Limit alcohol and caffeine intake"
            ],
            "food_recommendations": [
                "Fresh fruits and vegetables (high potassium, low sodium)",
                "Whole grains and legumes",
                "Lean proteins and low-fat dairy",
                "Foods rich in magnesium and calcium"
            ],
            "food_avoid": [
                "Processed and packaged foods (high sodium)",
                "Canned soups and processed meats",
                "Restaurant and fast foods",
                "Pickled and salted foods"
            ],
            "cooking_tips": [
                "Cook from scratch to control sodium",
                "Use lemon juice, herbs, and spices for flavor",
                "Rinse canned foods to reduce sodium",
                "Choose fresh or frozen vegetables over canned"
            ]
        }
    }
    
    INDIAN_FOOD_SUBSTITUTIONS = {
        "high_sodium": {
            "pickles": ["fresh chutneys", "yogurt-based dips"],
            "papad": ["roasted nuts", "vegetable sticks"],
            "processed_snacks": ["homemade popcorn", "roasted chickpeas"]
        },
        "high_potassium": {
            "potatoes": ["cauliflower", "cabbage", "rice"],
            "bananas": ["apples", "berries", "grapes"],
            "tomatoes": ["cucumber", "bell peppers (in moderation)"]
        },
        "high_phosphorus": {
            "dairy": ["plant-based milk alternatives", "small portions of hard cheese"],
            "nuts": ["seeds in moderation", "small portions of preferred nuts"],
            "whole_grains": ["refined grains in moderation", "portion control"]
        }
    }


class AgenticMealPlanner:
    """Main agentic AI engine for meal planning"""
    
    def __init__(self):
        self.knowledge_base = MedicalKnowledgeBase()
        self.conversation_history: Dict[str, List[Dict]] = {}
        self.user_profiles: Dict[str, UserProfile] = {}
        self.learning_data: Dict[str, List[Dict]] = {}
    
    def analyze_intent(self, user_message: str, user_id: str) -> AgentIntent:
        """Analyze user message to determine intent"""
        message_lower = user_message.lower()
        
        # Meal plan related keywords
        if any(word in message_lower for word in ["meal plan", "what should i eat", "suggest meal", "diet plan"]):
            return AgentIntent.MEAL_PLAN_REQUEST
        
        # Recipe related keywords
        elif any(word in message_lower for word in ["recipe", "how to make", "cook", "prepare"]):
            return AgentIntent.RECIPE_SUGGESTION
        
        # Nutrition query keywords
        elif any(word in message_lower for word in ["nutrition", "calories", "protein", "carbs", "vitamins"]):
            return AgentIntent.NUTRITION_QUERY
        
        # Dietary advice keywords
        elif any(word in message_lower for word in ["advice", "recommend", "should i eat", "good for"]):
            return AgentIntent.DIETARY_ADVICE
        
        # Substitution keywords
        elif any(word in message_lower for word in ["substitute", "alternative", "instead of", "replace"]):
            return AgentIntent.MEAL_SUBSTITUTION
        
        # Symptom check keywords
        elif any(word in message_lower for word in ["symptom", "feeling", "pain", "discomfort"]):
            return AgentIntent.SYMPTOM_CHECK
        
        else:
            return AgentIntent.GENERAL_CHAT
    
    def generate_meal_plan(
        self,
        user_profile: UserProfile,
        meal_type: MealType,
        constraints: Dict[str, Any],
        preferences: Optional[Dict[str, Any]] = None
    ) -> MealPlan:
        """Generate a personalized meal plan using agentic reasoning"""
        
        # Get disease-specific guidance
        disease_guidance = self.knowledge_base.DISEASE_SPECIFIC_GUIDANCE.get(
            user_profile.disease.lower(), {}
        )
        
        # Select appropriate ingredients based on constraints
        ingredients = self._select_ingredients(
            user_profile, 
            constraints, 
            disease_guidance
        )
        
        # Generate instructions based on cooking skill
        instructions = self._generate_instructions(
            ingredients, 
            user_profile.cooking_skill,
            user_profile.time_constraints
        )
        
        # Calculate nutritional information
        nutritional_info = self._calculate_nutrition(ingredients, constraints)
        
        # Determine meal name
        meal_name = self._generate_meal_name(
            meal_type, 
            ingredients, 
            user_profile.cultural_preferences
        )
        
        # Calculate preparation time and difficulty
        prep_time, difficulty = self._estimate_prep_difficulty(
            ingredients, 
            user_profile.cooking_skill,
            user_profile.time_constraints
        )
        
        # Generate substitutions
        substitutions = self._generate_substitutions(
            ingredients, 
            user_profile.disease,
            user_profile.allergies
        )
        
        # Check medical compliance
        medical_compliance = self._check_medical_compliance(
            nutritional_info, 
            constraints,
            user_profile.disease
        )
        
        # Calculate safety score
        safety_score = self._calculate_safety_score(
            nutritional_info, 
            constraints,
            medical_compliance
        )
        
        return MealPlan(
            meal_type=meal_type,
            meal_name=meal_name,
            ingredients=ingredients,
            instructions=instructions,
            nutritional_info=nutritional_info,
            preparation_time=prep_time,
            difficulty=difficulty,
            safety_score=safety_score,
            medical_compliance=medical_compliance,
            substitutions=substitutions
        )
    
    def _select_ingredients(
        self,
        user_profile: UserProfile,
        constraints: Dict[str, Any],
        disease_guidance: Dict[str, List[str]]
    ) -> List[Dict[str, Any]]:
        """Select ingredients based on constraints and disease guidance"""
        recommended_foods = disease_guidance.get("food_recommendations", [])
        avoid_foods = disease_guidance.get("food_avoid", [])
        
        # Base ingredient selection
        ingredients = []
        
        # Add protein source
        if user_profile.disease.lower() == "ckd":
            if "egg whites" not in [a for a in user_profile.allergies if "egg" in a.lower()]:
                ingredients.append({
                    "name": "Egg whites",
                    "amount": "2 large",
                    "protein_g": 7.0,
                    "reason": "High quality protein, lower phosphorus"
                })
            else:
                ingredients.append({
                    "name": "Tofu",
                    "amount": "100g",
                    "protein_g": 8.0,
                    "reason": "Plant-based protein, kidney-friendly"
                })
        else:
            ingredients.append({
                "name": "Chicken breast",
                "amount": "100g",
                "protein_g": 23.0,
                "reason": "Lean protein source"
            })
        
        # Add vegetables based on disease
        if user_profile.disease.lower() == "ckd":
            vegetables = ["Cauliflower", "Cabbage", "Green beans"]
        elif user_profile.disease.lower() == "diabetes":
            vegetables = ["Broccoli", "Spinach", "Bell peppers"]
        else:  # hypertension
            vegetables = ["Carrots", "Spinach", "Tomatoes"]
        
        for veg in vegetables[:2]:  # Add 2 vegetables
            ingredients.append({
                "name": veg,
                "amount": "1 cup",
                "fiber_g": 2.5,
                "reason": "Low sodium, nutrient-dense vegetable"
            })
        
        # Add carbohydrate source
        if user_profile.disease.lower() == "ckd":
            ingredients.append({
                "name": "White rice",
                "amount": "1/2 cup cooked",
                "carbs_g": 25.0,
                "reason": "Lower phosphorus grain option"
            })
        elif user_profile.disease.lower() == "diabetes":
            ingredients.append({
                "name": "Brown rice",
                "amount": "1/3 cup cooked",
                "carbs_g": 20.0,
                "reason": "Complex carbohydrate with fiber"
            })
        else:
            ingredients.append({
                "name": "Quinoa",
                "amount": "1/2 cup cooked",
                "carbs_g": 20.0,
                "reason": "High fiber, nutrient-dense grain"
            })
        
        # Add healthy fat
        ingredients.append({
            "name": "Olive oil",
            "amount": "1 tbsp",
            "fat_g": 14.0,
            "reason": "Heart-healthy fat source"
        })
        
        return ingredients
    
    def _generate_instructions(
        self,
        ingredients: List[Dict[str, Any]],
        cooking_skill: str,
        time_constraints: str
    ) -> List[str]:
        """Generate cooking instructions based on skill level and time"""
        
        if time_constraints == "high":
            # Quick preparation
            instructions = [
                "Prepare all ingredients by washing and chopping vegetables.",
                "Heat olive oil in a large pan over medium-high heat.",
                "Add protein source and cook for 3-4 minutes until done.",
                "Add vegetables and stir-fry for 2-3 minutes.",
                "Add cooked grains and toss everything together.",
                "Season with herbs and spices instead of salt.",
                "Serve immediately while hot."
            ]
        elif cooking_skill == "beginner":
            # Detailed instructions
            instructions = [
                "Start by washing all vegetables thoroughly.",
                "Chop vegetables into bite-sized pieces.",
                "Heat olive oil in a large pan over medium heat.",
                "Add protein source and cook for 5-7 minutes until fully cooked.",
                "Add vegetables one at a time, starting with harder ones.",
                "Cook vegetables for 5-7 minutes until tender-crisp.",
                "Add cooked grains and mix well.",
                "Season with herbs, spices, and a squeeze of lemon.",
                "Taste and adjust seasoning if needed.",
                "Serve hot and enjoy!"
            ]
        else:  # intermediate or advanced
            instructions = [
                "Prepare a mise en place with all ingredients chopped and measured.",
                "Heat olive oil in a wok or large skillet over high heat.",
                "Add protein source and sear for 2-3 minutes.",
                "Add aromatics (garlic, ginger) if using.",
                "Add vegetables in order of cooking time, starting with densest.",
                "Stir-fry for 3-4 minutes over high heat.",
                "Add cooked grains and toss to combine.",
                "Finish with fresh herbs and a splash of acid.",
                "Adjust seasoning and serve immediately."
            ]
        
        return instructions
    
    def _calculate_nutrition(
        self,
        ingredients: List[Dict[str, Any]],
        constraints: Dict[str, Any]
    ) -> Dict[str, float]:
        """Calculate nutritional information for the meal"""
        nutrition = {
            "calories": 0.0,
            "protein_g": 0.0,
            "carbs_g": 0.0,
            "fat_g": 0.0,
            "fiber_g": 0.0,
            "sodium_mg": 0.0,
            "potassium_mg": 0.0,
            "phosphorus_mg": 0.0
        }
        
        for ingredient in ingredients:
            nutrition["calories"] += ingredient.get("calories", 0)
            nutrition["protein_g"] += ingredient.get("protein_g", 0)
            nutrition["carbs_g"] += ingredient.get("carbs_g", 0)
            nutrition["fat_g"] += ingredient.get("fat_g", 0)
            nutrition["fiber_g"] += ingredient.get("fiber_g", 0)
            nutrition["sodium_mg"] += ingredient.get("sodium_mg", 0)
            nutrition["potassium_mg"] += ingredient.get("potassium_mg", 0)
            nutrition["phosphorus_mg"] += ingredient.get("phosphorus_mg", 0)
        
        # Add base sodium for seasoning (minimal)
        nutrition["sodium_mg"] += 100  # Minimal salt for seasoning
        
        return nutrition
    
    def _generate_meal_name(
        self,
        meal_type: MealType,
        ingredients: List[Dict[str, Any]],
        cultural_preferences: List[str]
    ) -> str:
        """Generate an appealing meal name"""
        main_ingredient = ingredients[0]["name"] if ingredients else "Mixed"
        
        if "indian" in cultural_preferences:
            cultural_names = {
                MealType.BREAKFAST: "Indian-Style Healthy Breakfast Bowl",
                MealType.LUNCH: "Balanced Indian Thali",
                MealType.DINNER: "Light Indian Dinner Plate",
                MealType.SNACK: "Healthy Indian Snack Mix"
            }
            return cultural_names.get(meal_type, f"Healthy {meal_type.value} with {main_ingredient}")
        else:
            return f"Healthy {meal_type.value.capitalize()} with {main_ingredient}"
    
    def _estimate_prep_difficulty(
        self,
        ingredients: List[Dict[str, Any]],
        cooking_skill: str,
        time_constraints: str
    ) -> Tuple[int, str]:
        """Estimate preparation time and difficulty level"""
        base_time = 15  # Base preparation time
        
        # Add time for each ingredient
        for ingredient in ingredients:
            if "vegetable" in ingredient["name"].lower():
                base_time += 3
            elif "protein" in ingredient["name"].lower():
                base_time += 5
        
        # Adjust for time constraints
        if time_constraints == "high":
            base_time = int(base_time * 0.7)
        
        # Determine difficulty
        if cooking_skill == "beginner":
            difficulty = "Easy"
        elif cooking_skill == "intermediate":
            difficulty = "Medium"
        else:
            difficulty = "Medium-Hard"
        
        return base_time, difficulty
    
    def _generate_substitutions(
        self,
        ingredients: List[Dict[str, Any]],
        disease: str,
        allergies: List[str]
    ) -> List[Dict[str, str]]:
        """Generate ingredient substitutions based on disease and allergies"""
        substitutions = []
        
        disease_lower = disease.lower()
        
        for ingredient in ingredients:
            ingredient_name = ingredient["name"].lower()
            
            # Check for allergy substitutions
            for allergy in allergies:
                if allergy.lower() in ingredient_name:
                    if "dairy" in allergy.lower():
                        substitutions.append({
                            "original": ingredient["name"],
                            "substitute": "Plant-based milk alternative",
                            "reason": f"Allergy: {allergy}"
                        })
                    elif "gluten" in allergy.lower():
                        substitutions.append({
                            "original": ingredient["name"],
                            "substitute": "Gluten-free alternative",
                            "reason": f"Allergy: {allergy}"
                        })
            
            # Disease-specific substitutions
            if disease_lower == "ckd":
                if "potato" in ingredient_name:
                    substitutions.append({
                        "original": ingredient["name"],
                        "substitute": "Cauliflower or rice",
                        "reason": "Lower potassium alternative for CKD"
                    })
                elif "banana" in ingredient_name:
                    substitutions.append({
                        "original": ingredient["name"],
                        "substitute": "Apples or berries",
                        "reason": "Lower potassium fruit for CKD"
                    })
        
        return substitutions
    
    def _check_medical_compliance(
        self,
        nutritional_info: Dict[str, float],
        constraints: Dict[str, Any],
        disease: str
    ) -> Dict[str, str]:
        """Check compliance with medical constraints"""
        compliance = {}
        
        # Check sodium
        sodium_limit = constraints.get("sodium_limit_mg", 2000)
        if nutritional_info["sodium_mg"] <= sodium_limit * 0.3:  # Per meal limit (30% of daily)
            compliance["sodium"] = "COMPLIANT"
        else:
            compliance["sodium"] = "EXCEEDS_LIMIT"
        
        # Check potassium for CKD
        if disease.lower() == "ckd":
            potassium_limit = constraints.get("potassium_limit_mg", 2000)
            if nutritional_info["potassium_mg"] <= potassium_limit * 0.3:
                compliance["potassium"] = "COMPLIANT"
            else:
                compliance["potassium"] = "EXCEEDS_LIMIT"
        
        # Check phosphorus for CKD
        if disease.lower() == "ckd":
            phosphorus_limit = constraints.get("phosphorus_limit_mg", 800)
            if nutritional_info["phosphorus_mg"] <= phosphorus_limit * 0.3:
                compliance["phosphorus"] = "COMPLIANT"
            else:
                compliance["phosphorus"] = "EXCEEDS_LIMIT"
        
        # Check carbs for diabetes
        if disease.lower() == "diabetes":
            carbs_limit = constraints.get("carb_target_g", 45)  # Per meal
            if nutritional_info["carbs_g"] <= carbs_limit:
                compliance["carbohydrates"] = "COMPLIANT"
            else:
                compliance["carbohydrates"] = "EXCEEDS_LIMIT"
        
        return compliance
    
    def _calculate_safety_score(
        self,
        nutritional_info: Dict[str, float],
        constraints: Dict[str, Any],
        medical_compliance: Dict[str, str]
    ) -> float:
        """Calculate overall safety score for the meal"""
        score = 1.0
        
        # Deduct for non-compliant constraints
        for constraint, status in medical_compliance.items():
            if status == "EXCEEDS_LIMIT":
                score -= 0.2
        
        return max(0.0, score)
    
    def process_user_query(
        self,
        user_message: str,
        user_id: str,
        user_profile: UserProfile
    ) -> AgentResponse:
        """Process user query and generate appropriate response"""
        
        # Store conversation history
        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = []
        
        self.conversation_history[user_id].append({
            "timestamp": datetime.now().isoformat(),
            "message": user_message,
            "intent": None  # Will be filled after analysis
        })
        
        # Analyze intent
        intent = self.analyze_intent(user_message, user_id)
        self.conversation_history[user_id][-1]["intent"] = intent.value
        
        # Generate response based on intent
        if intent == AgentIntent.MEAL_PLAN_REQUEST:
            return self._handle_meal_plan_request(user_message, user_profile)
        elif intent == AgentIntent.RECIPE_SUGGESTION:
            return self._handle_recipe_suggestion(user_message, user_profile)
        elif intent == AgentIntent.NUTRITION_QUERY:
            return self._handle_nutrition_query(user_message, user_profile)
        elif intent == AgentIntent.DIETARY_ADVICE:
            return self._handle_dietary_advice(user_message, user_profile)
        elif intent == AgentIntent.MEAL_SUBSTITUTION:
            return self._handle_meal_substitution(user_message, user_profile)
        elif intent == AgentIntent.SYMPTOM_CHECK:
            return self._handle_symptom_check(user_message, user_profile)
        else:
            return self._handle_general_chat(user_message, user_profile)
    
    def _handle_meal_plan_request(
        self,
        user_message: str,
        user_profile: UserProfile
    ) -> AgentResponse:
        """Handle meal plan request"""
        
        # Determine meal type from message
        meal_type = self._extract_meal_type(user_message)
        
        # Get constraints from user profile
        constraints = {
            "calories_target": user_profile.calorie_target,
            "sodium_limit_mg": 1500 if user_profile.disease.lower() == "hypertension" else 2000,
            "potassium_limit_mg": 2000 if user_profile.disease.lower() == "ckd" else 3500,
            "phosphorus_limit_mg": 800 if user_profile.disease.lower() == "ckd" else 1200,
            "carb_target_g": 45 if user_profile.disease.lower() == "diabetes" else 60
        }
        
        # Generate meal plan
        meal_plan = self.generate_meal_plan(
            user_profile, 
            meal_type, 
            constraints
        )
        
        # Generate response content
        disease_guidance = self.knowledge_base.DISEASE_SPECIFIC_GUIDANCE.get(
            user_profile.disease.lower(), {}
        )
        
        content = f"""
Based on your {user_profile.disease} condition and {user_profile.risk_level} risk level, 
I've prepared a {meal_type.value} meal plan that's tailored to your needs.

**Meal: {meal_plan.meal_name}**
- Preparation time: {meal_plan.preparation_time} minutes
- Difficulty: {meal_plan.difficulty}
- Safety Score: {meal_plan.safety_score:.1%}

**Ingredients:**
"""
        for ingredient in meal_plan.ingredients:
            content += f"- {ingredient['amount']} {ingredient['name']} ({ingredient.get('reason', '')})\n"
        
        content += f"""
**Nutritional Information:**
- Calories: {meal_plan.nutritional_info['calories']:.0f} kcal
- Protein: {meal_plan.nutritional_info['protein_g']:.1f}g
- Carbohydrates: {meal_plan.nutritional_info['carbs_g']:.1f}g
- Fat: {meal_plan.nutritional_info['fat_g']:.1f}g
- Fiber: {meal_plan.nutritional_info['fiber_g']:.1f}g
- Sodium: {meal_plan.nutritional_info['sodium_mg']:.0f}mg

**Medical Compliance:**
"""
        for constraint, status in meal_plan.medical_compliance.items():
            content += f"- {constraint.capitalize()}: {status}\n"
        
        if meal_plan.substitutions:
            content += "\n**Substitutions Available:**\n"
            for sub in meal_plan.substitutions:
                content += f"- {sub['original']} → {sub['substitute']} ({sub['reason']})\n"
        
        content += f"""
**Instructions:**
"""
        for i, instruction in enumerate(meal_plan.instructions, 1):
            content += f"{i}. {instruction}\n"
        
        # Add safety alerts if any
        safety_alerts = []
        if meal_plan.safety_score < 0.8:
            safety_alerts.append("This meal has a lower safety score. Please consult with your healthcare provider.")
        
        if user_profile.risk_level == "high":
            safety_alerts.append("Given your high risk level, please monitor your response to this meal carefully.")
        
        return AgentResponse(
            intent=AgentIntent.MEAL_PLAN_REQUEST,
            content=content,
            meal_plans=[meal_plan],
            safety_alerts=safety_alerts,
            recommendations=disease_guidance.get("general_advice", [])[:2],
            follow_up_questions=[
                "Would you like me to adjust the portion sizes?",
                "Do you need substitutions for any ingredients?",
                "Would you like a different meal type?"
            ],
            confidence=0.85,
            requires_medical_supervision=user_profile.risk_level == "high"
        )
    
    def _extract_meal_type(self, message: str) -> MealType:
        """Extract meal type from user message"""
        message_lower = message.lower()
        
        if "breakfast" in message_lower or "morning" in message_lower:
            return MealType.BREAKFAST
        elif "lunch" in message_lower or "afternoon" in message_lower:
            return MealType.LUNCH
        elif "dinner" in message_lower or "evening" in message_lower or "night" in message_lower:
            return MealType.DINNER
        elif "snack" in message_lower:
            return MealType.SNACK
        else:
            # Default based on current time
            current_hour = datetime.now().hour
            if 6 <= current_hour < 11:
                return MealType.BREAKFAST
            elif 11 <= current_hour < 15:
                return MealType.LUNCH
            elif 15 <= current_hour < 21:
                return MealType.DINNER
            else:
                return MealType.SNACK
    
    def _handle_recipe_suggestion(
        self,
        user_message: str,
        user_profile: UserProfile
    ) -> AgentResponse:
        """Handle recipe suggestion request"""
        disease_guidance = self.knowledge_base.DISEASE_SPECIFIC_GUIDANCE.get(
            user_profile.disease.lower(), {}
        )
        
        content = f"""
I'd be happy to help you with recipe suggestions for {user_profile.disease}!

**Cooking Tips for {user_profile.disease}:**
"""
        for tip in disease_guidance.get("cooking_tips", []):
            content += f"- {tip}\n"
        
        content += f"""
**Recommended Foods:**
"""
        for food in disease_guidance.get("food_recommendations", []):
            content += f"- {food}\n"
        
        content += """
**Foods to Limit or Avoid:**
"""
        for food in disease_guidance.get("food_avoid", []):
            content += f"- {food}\n"
        
        return AgentResponse(
            intent=AgentIntent.RECIPE_SUGGESTION,
            content=content,
            recommendations=[
                "Try cooking from scratch to control ingredients",
                "Use herbs and spices for flavor instead of salt",
                "Experiment with different cooking methods"
            ],
            follow_up_questions=[
                "Would you like a specific meal plan?",
                "Do you have ingredients you'd like to use?",
                "Need help with meal prep for the week?"
            ],
            confidence=0.80
        )
    
    def _handle_nutrition_query(
        self,
        user_message: str,
        user_profile: UserProfile
    ) -> AgentResponse:
        """Handle nutrition query"""
        content = f"""
I can help you understand nutrition for {user_profile.disease} management.

**Key Nutrients to Monitor:**
"""
        
        if user_profile.disease.lower() == "ckd":
            content += """
- **Sodium**: Limit to 2,000mg/day to control blood pressure and fluid retention
- **Potassium**: Monitor intake, especially if you have advanced CKD
- **Phosphorus**: Limit to 800-1,000mg/day to protect bones and heart
- **Protein**: Moderate intake (0.6-0.8g/kg body weight) to reduce kidney workload
"""
        elif user_profile.disease.lower() == "diabetes":
            content += """
- **Carbohydrates**: Focus on complex carbs and consistent timing
- **Fiber**: Aim for 25-35g daily to help control blood sugar
- **Sodium**: Limit to 2,300mg/day for heart health
- **Saturated Fat**: Limit to 13g/day for heart health
"""
        else:  # hypertension
            content += """
- **Sodium**: Limit to 1,500mg/day ideal, 2,300mg maximum
- **Potassium**: Aim for 3,500-4,700mg daily to help lower blood pressure
- **Fiber**: Aim for 25-30g daily for heart health
- **Magnesium and Calcium**: Important for blood pressure regulation
"""
        
        return AgentResponse(
            intent=AgentIntent.NUTRITION_QUERY,
            content=content,
            follow_up_questions=[
                "Would you like specific food recommendations?",
                "Need help reading food labels?",
                "Want to know about meal timing?"
            ],
            confidence=0.75
        )
    
    def _handle_dietary_advice(
        self,
        user_message: str,
        user_profile: UserProfile
    ) -> AgentResponse:
        """Handle dietary advice request"""
        disease_guidance = self.knowledge_base.DISEASE_SPECIFIC_GUIDANCE.get(
            user_profile.disease.lower(), {}
        )
        
        content = f"""
Here's dietary advice for managing {user_profile.disease}:

**General Guidelines:**
"""
        for advice in disease_guidance.get("general_advice", []):
            content += f"- {advice}\n"
        
        return AgentResponse(
            intent=AgentIntent.DIETARY_ADVICE,
            content=content,
            recommendations=disease_guidance.get("general_advice", []),
            follow_up_questions=[
                "Would you like a personalized meal plan?",
                "Need help with grocery shopping?",
                "Want tips for eating out?"
            ],
            confidence=0.85
        )
    
    def _handle_meal_substitution(
        self,
        user_message: str,
        user_profile: UserProfile
    ) -> AgentResponse:
        """Handle meal substitution request"""
        substitutions = self.knowledge_base.INDIAN_FOOD_SUBSTITUTIONS
        
        content = """
Here are some healthy substitutions you can make:

**High Sodium Foods:**
"""
        for original, alternatives in substitutions["high_sodium"].items():
            content += f"- {original.capitalize()} → {', '.join(alternatives)}\n"
        
        content += """
**High Potassium Foods (for CKD):**
"""
        for original, alternatives in substitutions["high_potassium"].items():
            content += f"- {original.capitalize()} → {', '.join(alternatives)}\n"
        
        content += """
**High Phosphorus Foods (for CKD):**
"""
        for original, alternatives in substitutions["high_phosphorus"].items():
            content += f"- {original.capitalize()} → {', '.join(alternatives)}\n"
        
        return AgentResponse(
            intent=AgentIntent.MEAL_SUBSTITUTION,
            content=content,
            follow_up_questions=[
                "Need substitutions for a specific ingredient?",
                "Would you like help modifying a recipe?",
                "Want to learn about portion control?"
            ],
            confidence=0.80
        )
    
    def _handle_symptom_check(
        self,
        user_message: str,
        user_profile: UserProfile
    ) -> AgentResponse:
        """Handle symptom check - with medical disclaimer"""
        content = f"""
I understand you're experiencing some symptoms. However, I'm an AI assistant and cannot provide medical diagnosis.

**Important: If you're experiencing severe symptoms, please contact your healthcare provider immediately or seek emergency care.**

For {user_profile.disease} management, it's important to:
- Monitor your symptoms regularly
- Keep track of any changes in your condition
- Report concerning symptoms to your healthcare provider
- Follow your prescribed treatment plan

**Common reasons to contact your doctor:**
- Sudden changes in symptoms
- Symptoms that don't improve with usual management
- New or unusual symptoms
- Side effects from medications

Would you like me to help you prepare questions to discuss with your healthcare provider?
"""
        
        return AgentResponse(
            intent=AgentIntent.SYMPTOM_CHECK,
            content=content,
            safety_alerts=["This query requires medical supervision - please consult your healthcare provider"],
            recommendations=[
                "Contact your healthcare provider for symptom evaluation",
                "Keep a symptom diary to share with your doctor",
                "Don't adjust medications without medical supervision"
            ],
            follow_up_questions=[
                "Would you like help preparing questions for your doctor?",
                "Need help tracking your symptoms?",
                "Want information about when to seek emergency care?"
            ],
            confidence=0.60,
            requires_medical_supervision=True
        )
    
    def _handle_general_chat(
        self,
        user_message: str,
        user_profile: UserProfile
    ) -> AgentResponse:
        """Handle general chat"""
        content = f"""
Hello! I'm your personal diet assistant for {user_profile.disease} management.

I can help you with:
- **Meal Planning**: Get personalized meal suggestions
- **Recipe Ideas**: Learn cooking techniques and recipes
- **Nutrition Information**: Understand nutrients and their impact
- **Dietary Advice**: Get guidance specific to your condition
- **Food Substitutions**: Find healthier alternatives
- **General Questions**: Answer your diet-related questions

What would you like help with today?
"""
        
        return AgentResponse(
            intent=AgentIntent.GENERAL_CHAT,
            content=content,
            follow_up_questions=[
                "Would you like a meal plan for your next meal?",
                "Need nutrition information?",
                "Want cooking tips for your condition?"
            ],
            confidence=0.70
        )


# Global agent instance
agent_engine = AgenticMealPlanner()