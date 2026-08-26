"""
Medical Knowledge Base and Guideline Integration
Provides structured access to medical guidelines, drug-food interactions, and clinical evidence
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from enum import Enum
import json
from pathlib import Path


class GuidelineSource(Enum):
    """Authoritative sources for medical guidelines"""
    KDIGO = "KDIGO"  # Kidney Disease: Improving Global Outcomes
    ADA = "ADA"  # American Diabetes Association
    AHA = "AHA"  # American Heart Association
    ACC = "ACC"  # American College of Cardiology
    ISPEN = "ISPEN"  # International Society for Parenteral and Enteral Nutrition
    ESPEN = "ESPEN"  # European Society for Parenteral and Enteral Nutrition
    WHO = "WHO"  # World Health Organization
    ICMR = "ICMR"  # Indian Council of Medical Research


class EvidenceLevel(Enum):
    """Levels of medical evidence"""
    STRONG = "strong"  # Multiple high-quality studies
    MODERATE = "moderate"  # Some evidence, but limitations
    LIMITED = "limited"  # Few studies or inconsistent results
    EXPERT_CONSENSUS = "expert_consensus"  # Expert opinion when evidence is lacking


class RecommendationStrength(Enum):
    """Strength of clinical recommendations"""
    STRONG = "strong"  # Should be followed in most cases
    MODERATE = "moderate"  # Reasonable to follow, but flexibility exists
    WEAK = "weak"  # May be considered, but not strongly recommended
    CONDITIONAL = "conditional"  # Depends on patient preferences or clinical context


@dataclass
class ClinicalGuideline:
    """Individual clinical guideline"""
    guideline_id: str
    source: GuidelineSource
    year: int
    disease: str
    condition: str
    recommendation: str
    evidence_level: EvidenceLevel
    recommendation_strength: RecommendationStrength
    target_population: str
    exceptions: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    last_updated: str = ""


@dataclass
class DrugFoodInteraction:
    """Drug-food interaction information"""
    interaction_id: str
    drug_name: str
    drug_category: str
    food_components: List[str]
    interaction_type: str  # "increase_effect", "decrease_effect", "adverse_reaction"
    severity: str  # "mild", "moderate", "severe"
    mechanism: str
    clinical_significance: str
    management: str
    alternatives: List[str] = field(default_factory=list)


@dataclass
class NutrientInteraction:
    """Nutrient-nutrient interaction information"""
    interaction_id: str
    primary_nutrient: str
    interacting_nutrients: List[str]
    interaction_type: str  # "antagonist", "synergist", "absorption_inhibitor"
    effect_description: str
    clinical_relevance: str
    timing_recommendation: str  # "separate_by_2hours", "take_together", etc.


@dataclass
class ClinicalEvidence:
    """Clinical evidence summary"""
    evidence_id: str
    research_question: str
    population: str
    intervention: str
    comparator: str
    outcomes: List[str]
    findings: str
    study_design: str
    sample_size: int
    confidence_interval: Optional[str] = None
    p_value: Optional[str] = None
    limitations: List[str] = field(default_factory=list)
    publication_year: int = 2020
    journal: str = ""


class MedicalKnowledgeBase:
    """Comprehensive medical knowledge base"""
    
    def __init__(self):
        self.guidelines: Dict[str, List[ClinicalGuideline]] = {}
        self.drug_interactions: Dict[str, List[DrugFoodInteraction]] = {}
        self.nutrient_interactions: Dict[str, List[NutrientInteraction]] = {}
        self.clinical_evidence: Dict[str, List[ClinicalEvidence]] = {}
        self._load_knowledge_base()
    
    def _load_knowledge_base(self):
        """Load all medical knowledge"""
        self._load_guidelines()
        self._load_drug_interactions()
        self._load_nutrient_interactions()
        self._load_clinical_evidence()
    
    def _load_guidelines(self):
        """Load clinical guidelines from authoritative sources"""
        
        # KDIGO 2023 CKD Guidelines
        ckd_guidelines = [
            ClinicalGuideline(
                guideline_id="KDIGO_CKD_SODIUM_2023",
                source=GuidelineSource.KDIGO,
                year=2023,
                disease="ckd",
                condition="sodium_intake",
                recommendation="Sodium intake should be limited to <2 g/day (<90 mmol) for CKD patients to control blood pressure and reduce cardiovascular risk",
                evidence_level=EvidenceLevel.MODERATE,
                recommendation_strength=RecommendationStrength.MODERATE,
                target_population="CKD stages 3-5",
                exceptions=["Patients on dialysis may require individualized sodium targets"],
                references=["KDIGO 2023 Clinical Practice Guideline for CKD"]
            ),
            ClinicalGuideline(
                guideline_id="KDIGO_CKD_PROTEIN_2023",
                source=GuidelineSource.KDIGO,
                year=2023,
                disease="ckd",
                condition="protein_intake",
                recommendation="Protein intake of 0.6-0.8 g/kg/day for CKD stages 3-5 not on dialysis",
                evidence_level=EvidenceLevel.MODERATE,
                recommendation_strength=RecommendationStrength.MODERATE,
                target_population="CKD stages 3-5 not on dialysis",
                exceptions=["Dialysis patients require higher protein intake (1.0-1.2 g/kg/day)"],
                references=["KDIGO 2023 Clinical Practice Guideline for CKD"]
            ),
            ClinicalGuideline(
                guideline_id="KDIGO_CKD_POTASSIUM_2023",
                source=GuidelineSource.KDIGO,
                year=2023,
                disease="ckd",
                condition="potassium_intake",
                recommendation="Potassium intake should be individualized based on serum potassium levels. For hyperkalemic patients, limit to <2 g/day",
                evidence_level=EvidenceLevel.LIMITED,
                recommendation_strength=RecommendationStrength.CONDITIONAL,
                target_population="CKD patients with hyperkalemia",
                exceptions=["Patients with normal potassium levels may not need restriction"],
                references=["KDIGO 2023 Clinical Practice Guideline for CKD"]
            ),
            ClinicalGuideline(
                guideline_id="KDIGO_CKD_PHOSPHORUS_2023",
                source=GuidelineSource.KDIGO,
                year=2023,
                disease="ckd",
                condition="phosphorus_intake",
                recommendation="Phosphorus intake should be limited to 800-1000 mg/day for CKD stages 3-5",
                evidence_level=EvidenceLevel.MODERATE,
                recommendation_strength=RecommendationStrength.MODERATE,
                target_population="CKD stages 3-5",
                exceptions=["Patients on phosphate binders may have slightly higher allowances"],
                references=["KDIGO 2023 Clinical Practice Guideline for CKD"]
            )
        ]
        
        # ADA 2024 Diabetes Guidelines
        diabetes_guidelines = [
            ClinicalGuideline(
                guideline_id="ADA_DIABETES_CARBS_2024",
                source=GuidelineSource.ADA,
                year=2024,
                disease="diabetes",
                condition="carbohydrate_intake",
                recommendation="Carbohydrate intake should be individualized, but generally 45-60g per meal for most adults with diabetes",
                evidence_level=EvidenceLevel.STRONG,
                recommendation_strength=RecommendationStrength.MODERATE,
                target_population="Adults with type 2 diabetes",
                exceptions=["Patients on intensive insulin therapy may require different targets"],
                references=["ADA Standards of Care 2024"]
            ),
            ClinicalGuideline(
                guideline_id="ADA_DIABETES_FIBER_2024",
                source=GuidelineSource.ADA,
                year=2024,
                disease="diabetes",
                condition="fiber_intake",
                recommendation="Fiber intake of 25-35g daily recommended for adults with diabetes",
                evidence_level=EvidenceLevel.MODERATE,
                recommendation_strength=RecommendationStrength.MODERATE,
                target_population="Adults with diabetes",
                exceptions=["Patients with gastrointestinal conditions may need adjustment"],
                references=["ADA Standards of Care 2024"]
            ),
            ClinicalGuideline(
                guideline_id="ADA_DIABETES_SUGAR_2024",
                source=GuidelineSource.ADA,
                year=2024,
                disease="diabetes",
                condition="added_sugar",
                recommendation="Limit added sugars to <10% of total daily calories",
                evidence_level=EvidenceLevel.MODERATE,
                recommendation_strength=RecommendationStrength.MODERATE,
                target_population="Adults with diabetes",
                exceptions=["Patients with hypoglycemia unawareness may need different approach"],
                references=["ADA Standards of Care 2024"]
            ),
            ClinicalGuideline(
                guideline_id="ADA_DIABETES_SODIUM_2024",
                source=GuidelineSource.ADA,
                year=2024,
                disease="diabetes",
                condition="sodium_intake",
                recommendation="Sodium intake should be limited to <2300 mg/day for cardiovascular risk reduction",
                evidence_level=EvidenceLevel.MODERATE,
                recommendation_strength=RecommendationStrength.MODERATE,
                target_population="Adults with diabetes and hypertension",
                exceptions=["Patients with heart failure may require stricter limits"],
                references=["ADA Standards of Care 2024"]
            )
        ]
        
        # AHA/ACC 2023 Hypertension Guidelines
        hypertension_guidelines = [
            ClinicalGuideline(
                guideline_id="AHA_HYPERTENSION_SODIUM_2023",
                source=GuidelineSource.AHA,
                year=2023,
                disease="hypertension",
                condition="sodium_intake",
                recommendation="Sodium intake should be limited to <1500 mg/day ideal, <2300 mg/day maximum for blood pressure control",
                evidence_level=EvidenceLevel.STRONG,
                recommendation_strength=RecommendationStrength.STRONG,
                target_population="Adults with hypertension",
                exceptions=["Patients with volume depletion may need different targets"],
                references=["AHA/ACC 2023 Guideline for Hypertension"]
            ),
            ClinicalGuideline(
                guideline_id="AHA_HYPERTENSION_POTASSIUM_2023",
                source=GuidelineSource.AHA,
                year=2023,
                disease="hypertension",
                condition="potassium_intake",
                recommendation="Increase potassium intake to 3500-4700 mg/day through food sources, unless contraindicated",
                evidence_level=EvidenceLevel.MODERATE,
                recommendation_strength=RecommendationStrength.MODERATE,
                target_population="Adults with hypertension",
                exceptions=["Patients with CKD or on potassium-sparing diuretics"],
                references=["AHA/ACC 2023 Guideline for Hypertension"]
            ),
            ClinicalGuideline(
                guideline_id="AHA_HYPERTENSION_DASH_2023",
                source=GuidelineSource.AHA,
                year=2023,
                disease="hypertension",
                condition="dietary_pattern",
                recommendation="DASH diet pattern recommended: rich in fruits, vegetables, low-fat dairy, whole grains, and reduced in saturated fat and sodium",
                evidence_level=EvidenceLevel.STRONG,
                recommendation_strength=RecommendationStrength.STRONG,
                target_population="Adults with hypertension",
                exceptions=["Patients with specific cultural dietary preferences may need adaptation"],
                references=["AHA/ACC 2023 Guideline for Hypertension"]
            )
        ]
        
        # ICMR Indian Guidelines
        indian_guidelines = [
            ClinicalGuideline(
                guideline_id="ICMR_DIABETES_INDIAN_2021",
                source=GuidelineSource.ICMR,
                year=2021,
                disease="diabetes",
                condition="indian_diet",
                recommendation="For Indian context, emphasize traditional foods like millets, legumes, and local vegetables with appropriate portion control",
                evidence_level=EvidenceLevel.EXPERT_CONSENSUS,
                recommendation_strength=RecommendationStrength.MODERATE,
                target_population="Indian adults with diabetes",
                exceptions=["Individual preferences and regional variations should be considered"],
                references=["ICMR Guidelines for Diabetes 2021"]
            ),
            ClinicalGuideline(
                guideline_id="ICMR_HYPERTENSION_INDIAN_2020",
                source=GuidelineSource.ICMR,
                year=2020,
                disease="hypertension",
                condition="indian_diet",
                recommendation="Reduce salt intake in traditional Indian cooking; limit pickles, papads, and processed foods",
                evidence_level=EvidenceLevel.EXPERT_CONSENSUS,
                recommendation_strength=RecommendationStrength.MODERATE,
                target_population="Indian adults with hypertension",
                exceptions=["Regional cooking variations may require specific approaches"],
                references=["ICMR Guidelines for Hypertension 2020"]
            )
        ]
        
        self.guidelines["ckd"] = ckd_guidelines
        self.guidelines["diabetes"] = diabetes_guidelines
        self.guidelines["hypertension"] = hypertension_guidelines
        self.guidelines["indian_context"] = indian_guidelines
    
    def _load_drug_interactions(self):
        """Load drug-food interaction data"""
        
        interactions = [
            DrugFoodInteraction(
                interaction_id="WARFARIN_VITAMIN_K",
                drug_name="Warfarin",
                drug_category="anticoagulant",
                food_components=["vitamin_k", "leafy_greens", "broccoli", "spinach", "kale"],
                interaction_type="decrease_effect",
                severity="moderate",
                mechanism="Vitamin K promotes clotting factor synthesis, antagonizing warfarin effect",
                clinical_significance="Sudden changes in vitamin K intake can significantly affect INR levels",
                management="Maintain consistent vitamin K intake; avoid major fluctuations in leafy green consumption",
                alternatives=["Other vegetables lower in vitamin K", "Consistent portion sizes"]
            ),
            DrugFoodInteraction(
                interaction_id="ACE_INHIBITORS_POTASSIUM",
                drug_name="ACE Inhibitors",
                drug_category="antihypertensive",
                food_components=["potassium_high", "bananas", "oranges", "potatoes", "tomatoes"],
                interaction_type="adverse_reaction",
                severity="severe",
                mechanism="ACE inhibitors reduce potassium excretion, leading to hyperkalemia",
                clinical_significance="High potassium intake can cause dangerous hyperkalemia",
                management="Monitor potassium levels; limit high-potassium foods if levels are elevated",
                alternatives=["Lower potassium fruits and vegetables", "Regular blood potassium monitoring"]
            ),
            DrugFoodInteraction(
                interaction_id="DIURETICS_SODIUM",
                drug_name="Diuretics",
                drug_category="antihypertensive",
                food_components=["sodium_high", "processed_foods", "canned_foods", "pickles"],
                interaction_type="decrease_effect",
                severity="moderate",
                mechanism="High sodium intake counteracts the fluid-reducing effects of diuretics",
                clinical_significance="High sodium can reduce medication effectiveness and worsen hypertension",
                management="Limit sodium intake to <1500 mg/day; avoid processed and high-sodium foods",
                alternatives=["Fresh foods", "Low-sodium alternatives", "Herbs and spices for flavor"]
            ),
            DrugFoodInteraction(
                interaction_id="INSULIN_CARBOHYDRATES",
                drug_name="Insulin",
                drug_category="antidiabetic",
                food_components=["carbohydrates", "sugars", "starches", "fruits", "grains"],
                interaction_type="increase_effect",
                severity="moderate",
                mechanism="Carbohydrates increase blood glucose, requiring insulin for metabolism",
                clinical_significance="Carbohydrate amount directly affects insulin dosing requirements",
                management="Match insulin dose to carbohydrate intake; consistent meal timing important",
                alternatives=["Consistent carbohydrate intake", "Carbohydrate counting", "Regular meal timing"]
            ),
            DrugFoodInteraction(
                interaction_id="METFORMIN_ALCOHOL",
                drug_name="Metformin",
                drug_category="antidiabetic",
                food_components=["alcohol"],
                interaction_type="adverse_reaction",
                severity="severe",
                mechanism="Alcohol increases risk of lactic acidosis when combined with metformin",
                clinical_significance="Rare but potentially fatal complication",
                management="Limit alcohol intake; avoid binge drinking; monitor for lactic acidosis symptoms",
                alternatives=["Non-alcoholic beverages", "Moderate alcohol consumption if approved by physician"]
            ),
            DrugFoodInteraction(
                interaction_id="DIGOXIN_POTASSIUM",
                drug_name="Digoxin",
                drug_category="cardiac_glycoside",
                food_components=["potassium_low", "diuretics", "vomiting", "diarrhea"],
                interaction_type="adverse_reaction",
                severity="severe",
                mechanism="Low potassium levels increase digoxin toxicity risk",
                clinical_significance="Hypokalemia can lead to life-threatening arrhythmias",
                management="Maintain normal potassium levels; monitor electrolytes regularly",
                alternatives=["Potassium supplements if prescribed", "Regular electrolyte monitoring"]
            ),
            DrugFoodInteraction(
                interaction_id="STATINS_GRAPEFRUIT",
                drug_name="Statins",
                drug_category="lipid_lowering",
                food_components=["grapefruit", "grapefruit_juice"],
                interaction_type="increase_effect",
                severity="moderate",
                mechanism="Grapefruit inhibits CYP3A4, increasing statin blood levels",
                clinical_significance="Increased risk of side effects including muscle damage",
                management="Avoid grapefruit and grapefruit juice while taking certain statins",
                alternatives=["Other fruits", "Check specific statin guidelines"]
            )
        ]
        
        # Organize by drug name
        for interaction in interactions:
            drug_lower = interaction.drug_name.lower()
            if drug_lower not in self.drug_interactions:
                self.drug_interactions[drug_lower] = []
            self.drug_interactions[drug_lower].append(interaction)
    
    def _load_nutrient_interactions(self):
        """Load nutrient-nutrient interaction data"""
        
        interactions = [
            NutrientInteraction(
                interaction_id="IRON_CALCIUM",
                primary_nutrient="iron",
                interacting_nutrients=["calcium"],
                interaction_type="absorption_inhibitor",
                effect_description="Calcium inhibits non-heme iron absorption",
                clinical_relevance="Significant for individuals with iron deficiency",
                timing_recommendation="Separate iron-rich foods from calcium-rich foods by 2 hours"
            ),
            NutrientInteraction(
                interaction_id="ZINC_COPPER",
                primary_nutrient="zinc",
                interacting_nutrients=["copper"],
                interaction_type="antagonist",
                effect_description="High zinc intake can interfere with copper absorption",
                clinical_relevance="Long-term high-dose zinc supplementation can lead to copper deficiency",
                timing_recommendation="Balance zinc and copper intake; avoid excessive zinc without copper"
            ),
            NutrientInteraction(
                interaction_id="VITAMIN_D_CALCIUM",
                primary_nutrient="vitamin_d",
                interacting_nutrients=["calcium"],
                interaction_type="synergist",
                effect_description="Vitamin D enhances calcium absorption",
                clinical_relevance="Important for bone health and calcium metabolism",
                timing_recommendation="Take vitamin D with calcium-containing meals"
            ),
            NutrientInteraction(
                interaction_id="VITAMIN_C_IRON",
                primary_nutrient="vitamin_c",
                interacting_nutrients=["iron"],
                interaction_type="synergist",
                effect_description="Vitamin C enhances non-heme iron absorption",
                clinical_relevance="Beneficial for individuals with iron deficiency",
                timing_recommendation="Consume vitamin C-rich foods with iron-rich plant foods"
            ),
            NutrientInteraction(
                interaction_id="MAGNESIUM_CALCIUM",
                primary_nutrient="magnesium",
                interacting_nutrients=["calcium"],
                interaction_type="antagonist",
                effect_description="High calcium intake can inhibit magnesium absorption",
                clinical_relevance="May affect magnesium status with high calcium supplementation",
                timing_recommendation="Balance calcium and magnesium intake; consider separate timing if supplementing"
            )
        ]
        
        # Organize by primary nutrient
        for interaction in interactions:
            nutrient_lower = interaction.primary_nutrient.lower()
            if nutrient_lower not in self.nutrient_interactions:
                self.nutrient_interactions[nutrient_lower] = []
            self.nutrient_interactions[nutrient_lower].append(interaction)
    
    def _load_clinical_evidence(self):
        """Load clinical evidence summaries"""
        
        evidence = [
            ClinicalEvidence(
                evidence_id="DASH_SBP_REDUCTION",
                research_question="Does DASH diet reduce systolic blood pressure?",
                population="Adults with prehypertension and stage 1 hypertension",
                intervention="DASH diet (rich in fruits, vegetables, low-fat dairy)",
                comparator="Control diet",
                outcomes=["Systolic blood pressure", "Diastolic blood pressure"],
                findings="DASH diet reduced systolic BP by 11.4 mmHg in hypertensive patients",
                study_design="Randomized controlled trial",
                sample_size=459,
                confidence_interval="95% CI: 7.2 to 15.6",
                p_value="<0.001",
                limitations=["Short follow-up period", "Limited generalizability to all populations"],
                publication_year=1997,
                journal="New England Journal of Medicine"
            ),
            ClinicalEvidence(
                evidence_id="MEDITERRANEAN_DIABETES",
                research_question="Does Mediterranean diet reduce diabetes risk?",
                population="Adults at high cardiovascular risk",
                intervention="Mediterranean diet supplemented with extra-virgin olive oil",
                comparator="Low-fat diet",
                outcomes=["Incidence of type 2 diabetes", "Cardiovascular events"],
                findings="Mediterranean diet reduced diabetes incidence by 52% over 4 years",
                study_design="Randomized controlled trial",
                sample_size=3541,
                confidence_interval="95% CI: 27 to 69",
                p_value="<0.001",
                limitations=["Predominantly Mediterranean population", "Self-reported dietary adherence"],
                publication_year=2014,
                journal="Annals of Internal Medicine"
            ),
            ClinicalEvidence(
                evidence_id="LOW_PROTEIN_CKD",
                research_question="Does low protein diet slow CKD progression?",
                population="CKD stages 3-4",
                intervention="Low protein diet (0.6-0.8 g/kg/day)",
                comparator="Normal protein diet (1.0+ g/kg/day)",
                outcomes=["GFR decline", "Time to dialysis", "Mortality"],
                findings="Low protein diet may slow GFR decline but evidence is mixed",
                study_design="Meta-analysis of randomized trials",
                sample_size=2245,  # pooled from multiple studies
                confidence_interval="Varies by study",
                p_value="Varies by study",
                limitations=["Heterogeneity between studies", "Compliance challenges", "Risk of malnutrition"],
                publication_year=2018,
                journal="Clinical Journal of the American Society of Nephrology"
            )
        ]
        
        # Organize by disease
        self.clinical_evidence["hypertension"] = [e for e in evidence if "blood pressure" in e.research_question.lower()]
        self.clinical_evidence["diabetes"] = [e for e in evidence if "diabetes" in e.research_question.lower()]
        self.clinical_evidence["ckd"] = [e for e in evidence if "ckd" in e.population.lower() or "kidney" in e.research_question.lower()]
    
    def get_guidelines(
        self,
        disease: str,
        condition: Optional[str] = None
    ) -> List[ClinicalGuideline]:
        """Get guidelines for a specific disease and condition"""
        disease_guidelines = self.guidelines.get(disease.lower(), [])
        
        if condition:
            return [
                guideline for guideline in disease_guidelines
                if condition.lower() in guideline.condition.lower()
            ]
        return disease_guidelines
    
    def get_drug_interactions(
        self,
        drug_name: str
    ) -> List[DrugFoodInteraction]:
        """Get drug-food interactions for a specific drug"""
        return self.drug_interactions.get(drug_name.lower(), [])
    
    def get_nutrient_interactions(
        self,
        nutrient: str
    ) -> List[NutrientInteraction]:
        """Get nutrient interactions for a specific nutrient"""
        return self.nutrient_interactions.get(nutrient.lower(), [])
    
    def get_clinical_evidence(
        self,
        disease: str
    ) -> List[ClinicalEvidence]:
        """Get clinical evidence for a specific disease"""
        return self.clinical_evidence.get(disease.lower(), [])
    
    def search_guidelines(
        self,
        query: str,
        disease: Optional[str] = None
    ) -> List[ClinicalGuideline]:
        """Search guidelines by query text"""
        query_lower = query.lower()
        results = []
        
        guidelines_to_search = []
        if disease:
            guidelines_to_search = self.guidelines.get(disease.lower(), [])
        else:
            for disease_guidelines in self.guidelines.values():
                guidelines_to_search.extend(disease_guidelines)
        
        for guideline in guidelines_to_search:
            if (query_lower in guideline.recommendation.lower() or
                query_lower in guideline.condition.lower() or
                query_lower in guideline.disease.lower()):
                results.append(guideline)
        
        return results
    
    def get_indian_context_guidelines(self) -> List[ClinicalGuideline]:
        """Get guidelines specific to Indian context"""
        return self.guidelines.get("indian_context", [])
    
    def get_guideline_summary(
        self,
        disease: str
    ) -> Dict[str, Any]:
        """Get summary of guidelines for a disease"""
        disease_guidelines = self.guidelines.get(disease.lower(), [])
        
        summary = {
            "disease": disease,
            "total_guidelines": len(disease_guidelines),
            "sources": list(set([g.source.value for g in disease_guidelines])),
            "conditions": list(set([g.condition for g in disease_guidelines])),
            "evidence_distribution": {},
            "recommendation_strength_distribution": {}
        }
        
        # Count evidence levels
        for guideline in disease_guidelines:
            evidence = guideline.evidence_level.value
            summary["evidence_distribution"][evidence] = summary["evidence_distribution"].get(evidence, 0) + 1
        
        # Count recommendation strengths
        for guideline in disease_guidelines:
            strength = guideline.recommendation_strength.value
            summary["recommendation_strength_distribution"][strength] = summary["recommendation_strength_distribution"].get(strength, 0) + 1
        
        return summary


# Global medical knowledge base instance
medical_knowledge_base = MedicalKnowledgeBase()