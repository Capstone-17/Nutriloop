# A Deep Learning and Generative AI-Driven Diet Recommendation System for Personalized Chronic Disease Management

> **Production Release: Version 2.0 (Clinical CDS Platform)**  
> **Repository:** `capstone_repo` | **Target OS:** Windows / Linux / macOS  
> **Focus Diseases:** Chronic Kidney Disease (CKD), Essential Hypertension (HTN), Type 2 Diabetes Mellitus (T2DM), and Multi-Morbid Cohorts.  
> **Clinical Standards Grounding:** KDOQI / KDIGO (Renal), DASH / AHA / ACC (Cardiovascular), ADA 2024 (Endocrine), ICMR-NIN (Culinary Nutrition).  
> **Regulatory Architecture:** Non-Device Clinical Decision Support (CDS) compliant with FDA Jan 2026 Guidance & Llama Acceptable Use Policy.

---

## Table of Contents

1. [Executive Summary & System Identity](#1-executive-summary--system-identity)
2. [End-to-End System Architecture](#2-end-to-end-system-architecture)
3. [Clinical Intelligence & Comorbidity Conflict Resolution](#3-clinical-intelligence--comorbidity-conflict-resolution)
   - [3.1 The KDOQI vs. DASH Paradox](#31-the-kdoqi-vs-dash-paradox)
   - [3.2 Mathematical Formulation of Comorbidity Bounds](#32-mathematical-formulation-of-comorbidity-bounds)
   - [3.3 Expanded 18+ Medication Pharmacopeia](#33-expanded-18-medication-pharmacopeia)
4. [Machine Learning Modeling & Population Benchmarks](#4-machine-learning-modeling--population-benchmarks)
   - [4.1 Population-Scale Training Cohorts ($N=1,224,788$)](#41-population-scale-training-cohorts-n1224788)
   - [4.2 Non-Linear Pathophysiological Feature Engineering](#42-non-linear-pathophysiological-feature-engineering)
   - [4.3 Model Selection & Platt Probability Calibration](#43-model-selection--platt-probability-calibration)
   - [4.4 Empirical Benchmark Performance Matrix](#44-empirical-benchmark-performance-matrix)
5. [Dynamic Imputation & Adaptive Questionnaire Engine](#5-dynamic-imputation--adaptive-questionnaire-engine)
6. [Unified Food Knowledge Base & Regional Fuzzy Retrieval](#6-unified-food-knowledge-base--regional-fuzzy-retrieval)
7. [Longitudinal Adaptation, Behavioral Habits & Outcomes Tracker](#7-longitudinal-adaptation-behavioral-habits--outcomes-tracker)
8. [Database Persistence & High-Concurrency Architecture](#8-database-persistence--high-concurrency-architecture)
9. [Zero-Downtime Conversational AI & Clinical Chatbot](#9-zero-downtime-conversational-ai--clinical-chatbot)
10. [Comprehensive REST API Reference (21 Endpoints)](#10-comprehensive-rest-api-reference-21-endpoints)
11. [Interactive CLI Tool & Demonstration Payloads](#11-interactive-cli-tool--demonstration-payloads)
12. [Complete File-by-File Repository Map](#12-complete-file-by-file-repository-map)
13. [Installation, Verification & Quick Start](#13-installation-verification--quick-start)
14. [Regulatory Compliance & Medical Disclaimer](#14-regulatory-compliance--medical-disclaimer)

---

## 1. Executive Summary & System Identity

Chronic diseases—specifically **Chronic Kidney Disease (CKD)**, **Essential Hypertension (HTN)**, and **Type 2 Diabetes Mellitus (T2DM)**—are the primary drivers of global morbidity, mortality, and healthcare expenditure. When these conditions co-exist within the same individual (multi-morbidity, such as Diabetic Nephropathy complicated by Hypertension), standard single-disease dietary recommendations frequently contradict one another, exposing patients to severe clinical dangers such as hyperkalemic cardiac arrest, volume overload, or acute hypoglycemic shock.

This platform bridges clinical nutrition, calibrated machine learning, and generative agentic reasoning into a unified, enterprise-grade clinical decision support system:
* **Evidence-Based Grounding:** Every nutrient limit and meal score is mathematically anchored in peer-reviewed clinical guidelines (KDIGO, KDOQI, DASH, ADA, ICMR-NIN).
* **Calibrated Machine Learning Risk Scoring:** Trained on **$1,224,788$ population-scale patient records** across multi-cohort examination data with rigorous Platt sigmoid calibration to deliver well-calibrated posterior probabilities.
* **Comorbidity Conflict Resolution:** Solves the **KDOQI vs. DASH Paradox**, enforcing renal electrolyte safety precedence over cardiovascular potassium loading.
* **18+ Drug Pharmacopeia:** Cross-references active chronic disease drugs (SGLT2 inhibitors, GLP-1 receptor agonists, ACE inhibitors, ARBs, CCBs, Beta-blockers, Diuretics, Binders) against meal components to prevent fatal adverse food-drug interactions.
* **Continuous State Persistence:** Thread-safe SQLite database configured in Write-Ahead Logging (`WAL`) mode with 11 relational tables tracking longitudinal meal deviations, habit evolution, and clinical biomarker trajectories.
* **Zero-Downtime Conversational Agent:** A 3-layer clinical chatbot with hard-coded pre-LLM regex escalation, ReAct tool execution over 7,110 food items with regional culinary synonyms, and deterministic graceful degradation if local LLMs are unreachable.

---

## 2. End-to-End System Architecture

The platform operates across four decoupled, modular layers: the Presentation/Client Tier, the FastAPI Service Gateway, the Core Clinical Logic & ML Ingestion Tier, and the Relational Persistence Layer.

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                            CLIENTS & CONSUMERS                                                   │
│                 Interactive Terminal CLI                 REST API Consumers (Swagger / Mobile UI)                │
└────────────────────────────────────────────────────────┬─────────────────────────────────────────────────────────┘
                                                         │ HTTP / JSON
                                                         ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       FASTAPI SERVICE GATEWAY (backend/app.py)                                   │
│  Lifespan Management • Pydantic v2 Validation • 21 Endpoints • Subsystem Routing • CORS • Structured Exceptions  │
├─────────────────────────┬──────────────────────────────┬───────────────────────────────┬─────────────────────────┤
│    Health & Risk APIs   │   Medical Safety Engine      │   Adaptation & Learning       │   Hybrid Chatbot Agent  │
│  • Direct Pre-scaled    │  • Comorbidity Bounds        │  • Longitudinal Dev Tracker   │  • Pre-LLM Regex Guard  │
│  • Raw Questionnaire    │  • 18+ Drug Pharmacopeia     │  • Behavioral Habit Learner   │  • ReAct Tool Dispatch  │
│  • Dynamic Imputation   │  • Meal & Plan Safety Check  │  • Biomarker Trends (BP/eGFR) │  • Offline CDS Fallback │
└───────────┬─────────────┴──────────────┬───────────────┴───────────────┬───────────────┴────────────┬────────────┘
            │                            │                               │                            │
            ▼                            ▼                               ▼                            ▼
┌──────────────────────────┐ ┌───────────────────────────┐ ┌───────────────────────────┐ ┌──────────────────────┐
│  TRAINED ML ARTIFACTS    │ │   CLINICAL RULES ENGINE   │ │     FOOD KNOWLEDGE BASE   │ │ SQLITE WAL DATABASE  │
│ • CKD HistGradientBoost  │ │ • KDOQI vs DASH Solver    │ │ • 7,110 Curated Food Items│ │ (app_data.db)        │
│ • HTN HistGradientBoost  │ │ • ADA Glycemic Regulation │ │ • 28 Standardized Nutrient│ │ • 11 Relational Tab. │
│ • T2DM HistGradientBoost │ │ • Strictness Multipliers  │ │ • Regional Culinary Synon.│ │ • WAL Concurrency    │
│ • Sigmoid Platt Calibr.  │ │ • Macro/Micro Targets     │ │ • Fuzzy Matching (difflib)│ │ • 30s Busy Timeout   │
│ • Population Medians     │ │ • Deviation Thresholding  │ │ • Multi-Criteria Scoring  │ │ • Context Managers   │
└──────────────────────────┘ └───────────────────────────┘ └───────────────────────────┘ └──────────────────────┘
```

---

## 3. Clinical Intelligence & Comorbidity Conflict Resolution

### 3.1 The KDOQI vs. DASH Paradox
In isolated clinical scenarios:
* **Hypertension Guidelines (DASH / AHA / ACC):** Mandate high potassium intake ($3,500\text{--}4,700\,\text{mg/day}$) to induce natriuresis, reduce vascular peripheral resistance, and lower systolic blood pressure.
* **Chronic Kidney Disease Guidelines (KDOQI / KDIGO):** Patients with impaired glomerular filtration rate ($\text{eGFR} < 60\,\text{mL/min/1.73m}^2$) have diminished renal excretion of potassium. High dietary potassium triggers life-threatening **hyperkalemia**, manifesting as cardiac dysrhythmias and cardiac arrest.

When a patient presents with **both CKD and Hypertension**, applying both guidelines naively causes a direct clinical paradox. 

Our Constraint Intersection Solver in [backend/rules.py](file:///d:/College/Capstone/Sem_7/capstone_repo/backend/rules.py) resolves this via an **Electrolyte Safety Precedence Rule**:
1. **Renal Potassium Safety strictly overrides DASH:** Daily dietary potassium is capped at $\le 2,000\,\text{mg/day}$ ($\le 1,800\,\text{mg/day}$ in high-risk decompensated CKD).
2. **DASH Sodium Restriction is Retained:** Daily sodium is clamped to the strictest bound ($\le 1,500\,\text{mg/day}$), providing robust blood pressure suppression without risking hyperkalemia.

```
                              ┌───────────────────────────────────────────────┐
                              │  Multi-Morbid Profile: CKD + HTN + Diabetes   │
                              └──────────────────────┬────────────────────────┘
                                                     │
                             ┌───────────────────────┴───────────────────────┐
                             ▼                                               ▼
               ┌───────────────────────────┐                   ┌───────────────────────────┐
               │      KDOQI PRECEDENCE     │                   │      DASH PRECEDENCE      │
               │   Renal Potassium Safety  │                   │     Sodium Restriction    │
               │  Potassium <= 2,000 mg/d  │                   │    Sodium <= 1,500 mg/d   │
               └─────────────┬─────────────┘                   └─────────────┬─────────────┘
                             └───────────────────────┬───────────────────────┘
                                                     ▼
                                     ┌───────────────────────────────┐
                                     │         ADA REGULATION        │
                                     │    Free Sugars <= 20 g/d      │
                                     │    Carbohydrates <= 40%       │
                                     │    Dietary Fiber >= 35 g/d    │
                                     └───────────────────────────────┘
```

### 3.2 Mathematical Formulation of Comorbidity Bounds
For a patient profile characterized by disease set $\mathcal{D} \subseteq \{\text{CKD}, \text{HTN}, \text{T2DM}\}$ with composite risk status $\mathcal{R} \in \{\text{low}, \text{moderate}, \text{high}\}$:

$$\text{Sodium Limit (mg/d)} = \begin{cases} 
1500 & \text{if } \text{HTN} \in \mathcal{D} \land \mathcal{R} \in \{\text{moderate}, \text{high}\} \\
1800 & \text{if } \text{HTN} \in \mathcal{D} \land \mathcal{R} = \text{low} \\
1800 & \text{if } \text{CKD} \in \mathcal{D} \land \mathcal{R} \in \{\text{moderate}, \text{high}\} \\
2000 & \text{otherwise}
\end{cases}$$

$$\text{Potassium Limit (mg/d)} = \begin{cases}
1800 & \text{if } \text{CKD} \in \mathcal{D} \land \mathcal{R} = \text{high} \\
2000 & \text{if } \text{CKD} \in \mathcal{D} \land \mathcal{R} \in \{\text{low}, \text{moderate}\} \\
3500 & \text{if } \text{HTN} \in \mathcal{D} \land \text{CKD} \notin \mathcal{D} \\
3000 & \text{otherwise}
\end{cases}$$

$$\text{Phosphorus Limit (mg/d)} = \begin{cases}
800 & \text{if } \text{CKD} \in \mathcal{D} \land \mathcal{R} = \text{high} \\
1000 & \text{if } \text{CKD} \in \mathcal{D} \land \mathcal{R} \in \{\text{low}, \text{moderate}\} \\
\text{Unrestricted} & \text{if } \text{CKD} \notin \mathcal{D}
\end{cases}$$

$$\text{Free Sugars Limit (g/d)} = \begin{cases}
20 & \text{if } \text{T2DM} \in \mathcal{D} \land \mathcal{R} = \text{high} \\
30 & \text{if } \text{T2DM} \in \mathcal{D} \land \mathcal{R} \in \{\text{low}, \text{moderate}\} \\
40 & \text{otherwise}
\end{cases}$$

### 3.3 Expanded 18+ Medication Pharmacopeia
The system inspects patient medications via [backend/medical_knowledge.py](file:///d:/College/Capstone/Sem_7/capstone_repo/backend/medical_knowledge.py) and [backend/safety_engine.py](file:///d:/College/Capstone/Sem_7/capstone_repo/backend/safety_engine.py), mapping generic and proprietary brand names to detect nutrient contraindications:

| Drug Class | Exemplar Agents & Brand Aliases | Mechanism & Critical Dietary Contraindication |
| :--- | :--- | :--- |
| **SGLT2 Inhibitors** | *Empagliflozin (Jardiance), Dapagliflozin (Farxiga), Canagliflozin* | Promotes renal glucosuria. Concomitant severe carbohydrate restriction ($<100\,\text{g/d}$ or ketogenic diet) shifts fuel utilization to fatty acids, triggering life-threatening **Euglycemic Diabetic Ketoacidosis (euDKA)**. Demands hydration monitoring. |
| **GLP-1 Receptor Agonists** | *Semaglutide (Ozempic, Rybelsus), Liraglutide, Tirzepatide (Mounjaro)* | Potentiates insulin secretion and significantly delays gastric emptying. High-fat, greasy, or ultra-processed meals trigger severe nausea, gastroparesis, and vomiting. |
| **ACE Inhibitors** | *Lisinopril, Ramipril, Enalapril, Captopril* | Suppresses angiotensin II and aldosterone production, impairing renal potassium excretion. Potassium-enriched salt substitutes ($\text{KCl}$) or excessive dietary potassium cause severe hyperkalemia. |
| **Angiotensin Receptor Blockers (ARBs)** | *Losartan, Valsartan, Telmisartan, Candesartan* | Directly blocks $\text{AT}_1$ receptors, dampening aldosterone secretion. Strict contraindication against potassium-based salt alternatives. |
| **Calcium Channel Blockers (CCBs)** | *Amlodipine (Norvasc), Nifedipine, Diltiazem* | Grapefruit and Seville oranges contain furanocoumarins that irreversibly inhibit intestinal CYP3A4, causing massive serum drug bioavailability spikes, profound hypotension, and peripheral edema. |
| **Beta-Blockers** | *Metoprolol, Atenolol, Carvedilol, Bisoprolol* | Blunts sympathetic tone; completely masks early adrenergic warning signs of hypoglycemia (tremors, palpitations, tachycardia). |
| **Loop & Thiazide Diuretics** | *Furosemide (Lasix), Hydrochlorothiazide, Torsemide* | Excessive dietary sodium directly counteracts natriuresis and worsens fluid retention. Real licorice (glycyrrhizin) exacerbates hypokalemia. |
| **Potassium Binders** | *Patiromer (Veltassa), Sodium Zirconium Cyclosilicate (Lokelma)* | Non-selective cation exchange resins bind oral medications in the digestive lumen. Must be spaced by $\ge 2\text{--}3\,\text{hours}$ from all other maintenance drugs. |
| **Phosphate Binders** | *Sevelamer (Renvela), Calcium Acetate (PhosLo)* | Binds dietary phosphorus in the intestinal lumen to prevent systemic absorption. Ineffective if taken on an empty stomach; must be taken with the first bite of meals. |
| **Statins (HMG-CoA Reductase Inhibitors)** | *Atorvastatin (Lipitor), Simvastatin* | CYP3A4 substrate inhibition by grapefruit raises systemic exposure, elevating the incidence of myopathy and rhabdomyolysis. |
| **Biguanides** | *Metformin (Glucophage)* | Inhibits mitochondrial complex I and hepatic gluconeogenesis. Alcohol consumption during fasting potentiates lactic acidosis. |
| **Exogenous Insulin** | *Basal / Bolus Analogues* | Carbohydrate-to-insulin mismatch precipitates fatal neuroglycopenic hypoglycemia or severe hyperosmolar hyperglycemia. |
| **Cardiac Glycosides** | *Digoxin (Lanoxin)* | Hypokalemia sensitizes myocardial $\text{Na}^+/\text{K}^+$ ATPase, triggering lethal digitalis toxicity and arrhythmias. |
| **Vitamin K Antagonists** | *Warfarin (Coumadin)* | Dietary fluctuations in vitamin K (dark leafy greens) alter prothrombin complex synthesis, causing erratic INR fluctuations. |

---

## 4. Machine Learning Modeling & Population Benchmarks

### 4.1 Population-Scale Training Cohorts ($N=1,224,788$)
The platform models three distinct chronic conditions using population-scale epidemiological and examination data:
1. **Chronic Kidney Disease ($N=489,322$):** Grounded in the UCI Clinical Laboratory panel. Incorporates continuous biomarkers: serum creatinine, blood urea, specific gravity, albuminuria, serum sodium, potassium, and hemoglobin.
2. **Hypertension ($N=399,741$):** Fused from the Framingham Heart Study, NHANES 2017–2018 physical examination records, and CDC BRFSS. Contains physical multi-reading blood pressure, resting heart rate, total cholesterol, BMI, and smoking history.
3. **Type 2 Diabetes ($N=335,725$):** Fused from Pima Indians Diabetes, NHANES 2017–2018 laboratory oral glucose tolerance tests, fasting plasma glucose, fasting insulin, HbA1c, and BRFSS cohorts.

### 4.2 Non-Linear Pathophysiological Feature Engineering
In [scripts/preprocess_data.py](file:///d:/College/Capstone/Sem_7/capstone_repo/scripts/preprocess_data.py), continuous physiological variables undergo transformation to capture non-linear metabolic risk dynamics:
* **HOMA-IR Proxy (Homeostatic Model Assessment for Insulin Resistance):**
  $$\text{HOMA-IR} = \frac{\text{Fasting Glucose (mg/dL)} \times \text{Fasting Insulin (\mu IU/mL)}}{405.0}$$
* **Metabolic Burden Index:**
  $$\text{Metabolic Burden} = \left(\frac{\text{Glucose}}{100.0}\right)^2 \times \left(\frac{\text{BMI}}{25.0}\right)$$
* **Age-Glycemic Interaction:**
  $$\text{Age-Glucose Interaction} = \frac{\text{Age} \times \text{Glucose}}{100.0}$$
* **Logarithmic Insulin-Glucose Interaction:**
  $$\text{Log Insulin-Glucose} = \ln(1 + \text{Insulin}) \times \ln(1 + \text{Glucose})$$
* **Hemodynamic Mean Arterial Pressure (MAP) & Pulse Pressure:**
  $$\text{MAP} = \text{diaBP} + \frac{\text{sysBP} - \text{diaBP}}{3.0}, \quad \text{Pulse Pressure} = \text{sysBP} - \text{diaBP}$$
* **Creatinine-to-Urea Ratio:**
  $$\text{Creatinine-Urea Ratio} = \frac{\text{Serum Creatinine}}{\text{Blood Urea} + 10^{-5}}$$

### 4.3 Model Selection & Platt Probability Calibration
* In [scripts/train_and_optimize.py](file:///d:/College/Capstone/Sem_7/capstone_repo/scripts/train_and_optimize.py), eight candidate classifier families were evaluated under 5-fold Stratified Cross-Validation (`HistGradientBoosting`, `RandomForest`, `StackingEnsemble`, `XGBoost`, `SVC`, `KNeighbors`, `LogisticRegression`, `GaussianNB`).
* `HistGradientBoostingClassifier` was selected as the superior architecture due to its $O(N)$ histogram binning (256 discrete bins), native handling of missing clinical lab data, and high inference speed.
* **Platt Sigmoid Calibration:** Raw classifier margins are fitted via `CalibratedClassifierCV(method='sigmoid', cv=3)` to output true clinical posterior probabilities:
  $$P(Y=1 \mid X) = \frac{1}{1 + \exp(A \cdot f(X) + B)}$$
  delivering well-calibrated confidence scores with low Brier score calibration error ($\le 0.1068$).

### 4.4 Empirical Benchmark Performance Matrix
Metrics evaluated against held-out clinical test splits via [scripts/benchmark_models.py](file:///d:/College/Capstone/Sem_7/capstone_repo/scripts/benchmark_models.py):

| Disease | Best Model Architecture | Decision Threshold | Test Accuracy | Macro F1 | Recall (+) | Precision (+) | Specificity | PR-AUC | ROC-AUC | Brier Score |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Chronic Kidney Disease (CKD)** | `HistGradientBoostingClassifier` | 0.50 | **85.73%** | **0.8572** | **83.75%** | **87.18%** | **87.70%** | **0.9239** | **0.9207** | **0.1068** |
| **Essential Hypertension (HTN)** | `HistGradientBoostingClassifier` | 0.50 | **93.99%** | **0.9398** | **94.07%** | **94.33%** | **93.91%** | **0.9430** | **0.9537** | **0.0535** |
| **Type 2 Diabetes (T2DM)** | `HistGradientBoostingClassifier` | 0.51 | **90.50%** | **0.9041** | **87.91%** | **91.05%** | **92.69%** | **0.9066** | **0.9276** | **0.0810** |

---

## 5. Dynamic Imputation & Adaptive Questionnaire Engine

Real-world clinical workflows rarely present complete laboratory panels. In [backend/raw_input.py](file:///d:/College/Capstone/Sem_7/capstone_repo/backend/raw_input.py):
* The platform accepts patient questionnaire answers alongside optional clinical labs (serum creatinine, blood urea, urine dipstick, HbA1c, fasting insulin, lipid profile).
* When a patient leaves an advanced biomarker blank, the system dynamically imputes the value using the empirical training cohort median from [artifacts/population_medians.json](file:///d:/College/Capstone/Sem_7/capstone_repo/artifacts/population_medians.json).
* Validates biological plausibility with Pydantic v2 schemas:

```python
# Exemplar Pydantic Schema from backend/schemas.py
class CKDRawInput(BaseModel):
    age_years: int = Field(ge=18, le=100)
    sex: Literal["male", "female"]
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
```

---

## 6. Unified Food Knowledge Base & Regional Fuzzy Retrieval

The dietary engine indexes **7,110 curated food items** in [datasets/unified_food_kb.csv](file:///d:/College/Capstone/Sem_7/capstone_repo/datasets/unified_food_kb.csv), harmonized across the Indian Food Composition Tables (IFCT 2017, ICMR-NIN), OpenFoodFacts, and global databases across 40 distinct attributes (energy, macronutrients, sodium, potassium, phosphorus, calcium, iron, zinc, fiber, free sugars, fatty acid breakdown, and data completeness).

### Regional Culinary Synonyms & Fuzzy Search
Standard exact substring queries often fail on regional naming conventions (e.g., searching "dal" failed to match "lentil" or "sambhar"). In [backend/chatbot/tools.py](file:///d:/College/Capstone/Sem_7/capstone_repo/backend/chatbot/tools.py):
* **`CULINARY_SYNONYMS` Dictionary:** Maps colloquial Indian culinary terms to clinical food entries:
  * `daal` / `dal` $\rightarrow$ `["lentil", "pulse", "sambhar"]`
  * `roti` / `chapati` $\rightarrow$ `["phulka", "flatbread", "wheat"]`
  * `paneer` $\rightarrow$ `["cottage cheese", "cheese"]`
  * `sabzi` / `subji` $\rightarrow$ `["vegetable", "mixed vegetable", "curry"]`
  * `dahi` $\rightarrow$ `["curd", "yogurt"]`
  * `chawal` $\rightarrow$ `["rice", "boiled rice"]`
  * `khichdi` $\rightarrow$ `["rice", "lentil", "khichri"]`
* **Fuzzy Match Fallback:** When a query yields zero exact or synonym matches, `difflib.get_close_matches(cutoff=0.5)` identifies closest phonetic/textual neighbors, ensuring zero search drop-off.

### Multi-Criteria Disease Scoring Algorithm
In [backend/reporting.py](file:///d:/College/Capstone/Sem_7/capstone_repo/backend/reporting.py) (`_score_foods`), candidate foods are evaluated against the patient's calibrated nutritional targets:

$$\text{Food Score} = \sum_{k \in \text{Nutrients}} w_k \cdot \left[ 1 - \frac{\text{Nutrient}_k}{\text{Cap}_k} \right]^+ + w_{\text{fiber}} \cdot \left[ \frac{\text{Fiber}}{\text{Target}_{\text{fiber}}} \right] + w_{\text{comp}} \cdot \text{Completeness}$$

---

## 7. Longitudinal Adaptation, Behavioral Habits & Outcomes Tracker

In [backend/adaptation_engine.py](file:///d:/College/Capstone/Sem_7/capstone_repo/backend/adaptation_engine.py) and [backend/feedback_learning.py](file:///d:/College/Capstone/Sem_7/capstone_repo/backend/feedback_learning.py), the platform moves beyond static meal recommendations to continuous, longitudinal learning:
* **Deviation Detection:** Every logged meal is compared against the target meal plan. Calorie and nutrient deviations are graded into severity tiers:
  * `LOW` ($\ge 15\%$ deviation)
  * `MODERATE` ($\ge 25\%$ deviation)
  * `HIGH` ($\ge 40\%$ deviation)
* **Consecutive Pattern Analysis:** When $\ge 3$ consecutive deviations are detected in a specific meal type (e.g., breakfast), an automated `AdaptationAction` is registered:
  * Consistent over-consumption $\rightarrow$ automatic $10\%$ downward calorie adjustment on subsequent plans.
  * Consecutive high-severity deviations $\rightarrow$ automatic supervisor alert dispatch.
* **Habit Learning:** Analyzes rolling windows of $\ge 5$ meals to compute:
  * `meal_timing` patterns (identifying habitual eating windows).
  * `portion_size` ratios (quantifying individual portion over/under tendencies).
  * `adherence` trends (`improving`, `stable`, or `declining`).
* **Clinical Biomarker Outcome Correlation:** Ingests serial health measurements (blood pressure, fasting glucose, HbA1c, eGFR, weight) and computes clinical trends (`significant_improvement`, `stable`, or `concerning`).

---

## 8. Database Persistence & High-Concurrency Architecture

Application state is persisted to [app_data.db](file:///d:/College/Capstone/Sem_7/capstone_repo/app_data.db) via [backend/db.py](file:///d:/College/Capstone/Sem_7/capstone_repo/backend/db.py) with enterprise concurrency guarantees:
* **Write-Ahead Logging (`PRAGMA journal_mode=WAL;`):** Readers do not block writers, and writers do not block readers. Permits scaling to multi-worker server configurations (`uvicorn --workers 4`).
* **30-Second Busy Timeout (`PRAGMA busy_timeout=30000;`):** Eliminates `sqlite3.OperationalError: database is locked` errors during concurrent operations.
* **Thread-Safe Context Manager (`with get_db_conn() as conn:`):** Ensures automatic transaction commit on clean execution and automatic rollback on unhandled exceptions.

### Relational Schema (11 Tables)
1. `risk_profile`: Historical machine learning inference runs, risk scores, and predicted binary classes.
2. `diet_plan`: Calibrated caloric, macronutrient, and electrolyte targets generated for users.
3. `meal_log`: Consumed vs. planned calories, percentage deviation, and food notes.
4. `alert`: Open and resolved clinical safety alerts with severity classifications.
5. `risk_explanation_log`: Complete audit trail containing raw inputs, transformed features, top permutation factors, and clinical narrative text.
6. `adaptation_action`: Corrective adaptation actions triggered by meal deviation events.
7. `user_pattern`: Learned behavioral habits (timing windows, portion ratios, adherence metrics).
8. `feedback_record`: Patient subjective satisfaction ratings (1–5) and qualitative feedback.
9. `health_outcome`: Serial clinical biomarkers (blood pressure, HbA1c, eGFR, weight change) with clinical significance assessments.
10. `agent_session`: Multi-turn conversational histories and serialized user profiles.
11. `sqlite_sequence`: Internal SQLite autoincrement sequence tracker.

---

## 9. Zero-Downtime Conversational AI & Clinical Chatbot

The conversational agent in [backend/chatbot/agent.py](file:///d:/College/Capstone/Sem_7/capstone_repo/backend/chatbot/agent.py) operates across a resilient 3-layer architecture:

```
                                  Incoming User Message
                                            │
                                            ▼
                    ┌───────────────────────────────────────────────┐
                    │       LAYER 1: Pre-LLM Regex Escalation       │
                    │   Checks for medications, dosing, symptoms,   │
                    │   or diagnostic inquiries                     │
                    └───────┬───────────────────────────────┬───────┘
                            │ Matched                       │ No Match
                            ▼                               ▼
               ┌─────────────────────────┐     ┌─────────────────────────┐
               │ Return Immediate Fixed  │     │   LAYER 2: ReAct Loop   │
               │ Clinical Escalation Msg │     │   Queries Local LLM     │
               └─────────────────────────┘     │   (Ollama / llama3.2)   │
                                               └────────────┬────────────┘
                                                            │ LLM Offline / Socket Refused
                                                            ▼
                                               ┌─────────────────────────┐
                                               │   LAYER 3: Fallback     │
                                               │   Degrades to Determin. │
                                               │   AgenticMealPlanner    │
                                               └─────────────────────────┘
```

1. **Layer 1 — Pre-LLM Regex Escalation:** Before querying the language model, incoming text is scanned against `ESCALATION_PATTERNS`. Queries touching medication dosages, acute clinical symptoms (chest pain, shortness of breath), or diagnostic requests immediately receive an authoritative non-device escalation response directing them to emergency services or their physician.
2. **Layer 2 — ReAct Tool Execution:** When safe, the agent reasons over schema-bound tools:
   * `get_risk_profile`: Retrieves calibrated ML scores (prohibits the LLM from hallucinating risk numbers).
   * `get_diet_plan`: Retrieves active macronutrient and electrolyte targets.
   * `search_food_kb`: RAG lookup against the 7,110-item knowledge base with synonym expansion and fuzzy matching.
   * `log_meal`: Grounds user portion sizes to exact food KB nutritional density.
   * `log_interaction`: Writes full turn audits to `risk_explanation_log`.
3. **Layer 3 — Zero-Downtime Degradation:** If the local LLM daemon (Ollama) is offline or unreachable, the system catches the connection error and auto-degrades to the deterministic [AgenticMealPlanner](file:///d:/College/Capstone/Sem_7/capstone_repo/backend/agent_engine.py#L182-L1022). The user receives clinically valid meal guidance without server errors.

---

## 10. Comprehensive REST API Reference (21 Endpoints)

FastAPI serves 21 endpoints documented via Swagger UI (`/docs`) and ReDoc (`/redoc`):

### Health, Models & Risk Inference
| Method | Route | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Verifies server health status, list of loaded models, and count of open alerts. |
| `GET` | `/implementation-progress` | Model benchmark metrics, generated audit volume, and comparison summary. |
| `GET` | `/raw-input-template/{disease}` | Questionnaire fields schema, data types, and default clinical values. |
| `POST` | `/predict-risk` | Predicts risk probability and band from pre-normalized feature dictionaries. |
| `POST` | `/predict-risk-raw` | Full inference pipeline from raw questionnaire answers with dynamic median imputation. |
| `POST` | `/risk-explanation-raw` | Generates clinical narrative explanation and lists top permutation risk factors. |
| `POST` | `/risk-report` | Full diagnostic report with diet plan targets and food recommendations from pre-scaled inputs. |
| `POST` | `/risk-report-raw` | Full diagnostic report, diet plan, and food recommendations from raw questionnaire answers. |
| `POST` | `/recommend-plan` | Solves single-condition or multi-disease comorbidity plans applying precedence rules. |
| `POST` | `/log-meal` | Records meal calories and issues immediate deviation alerts if $\ge 15\%$ off target. |
| `GET` | `/risk-explanations` | Paginated query interface for historical audit records with user and disease filters. |

### Medical Safety & Guidelines
| Method | Route | Description |
| :--- | :--- | :--- |
| `GET` | `/medical/guidelines` | Evidence-based guideline summaries across KDIGO, KDOQI, DASH, ADA, and ICMR. |
| `GET` | `/medical/drug-interactions/{drug}` | Food and nutrient interaction warnings across 18+ chronic disease medications. |
| `POST` | `/safety/validate` | Validates meals or daily totals against patient comorbidity constraints and active drugs. |

### Adaptation & Continuous Learning
| Method | Route | Description |
| :--- | :--- | :--- |
| `POST` | `/adaptation/log-meal` | Detailed meal logging with nutrient-level deviation tracking and adaptation triggers. |
| `GET` | `/adaptation/summary/{user_id}` | Retrieves active adaptations, unresolved alerts, learned habits, and adherence rates. |
| `POST` | `/feedback/submit` | Records subjective patient satisfaction ratings (1–5) and qualitative feedback. |
| `POST` | `/outcomes/record` | Ingests serial clinical biomarkers (blood pressure, glucose, eGFR, weight) and computes trends. |
| `GET` | `/learning/summary` | Global cohort learning metrics, recommendation acceptance rates, and system trends. |

### Conversational & Multi-Agent AI
| Method | Route | Description |
| :--- | :--- | :--- |
| `POST` | `/chatbot/chat` | Clinical safety-first chatbot with ReAct tool-calling and zero-downtime offline fallback. |
| `POST` | `/agent/chat` | Multi-agent dietary goal planner, recipe builder, and cultural nutrition assistant. |

---

## 11. Interactive CLI Tool & Demonstration Payloads

The platform includes a CLI interface in [scripts/predict_cli.py](file:///d:/College/Capstone/Sem_7/capstone_repo/scripts/predict_cli.py):

### Interactive Wizard
```powershell
# Launches terminal questionnaire wizard with validation
python scripts/predict_cli.py --interactive
```

### Scripted Evaluation on Demo Payloads
```powershell
# Evaluate clinical test profiles in demo_inputs/
python scripts/predict_cli.py demo_inputs/comorbid_ckd_htn.json
python scripts/predict_cli.py demo_inputs/diabetes_with_labs.json
python scripts/predict_cli.py demo_inputs/hypertension_with_lipids.json
python scripts/predict_cli.py demo_inputs/healthy_baseline.json
```

### Demo Input Profiles ([demo_inputs/](file:///d:/College/Capstone/Sem_7/capstone_repo/demo_inputs))
* [comorbid_ckd_htn.json](file:///d:/College/Capstone/Sem_7/capstone_repo/demo_inputs/comorbid_ckd_htn.json): Multi-morbid Stage 3 CKD with diabetic nephropathy and hypertension.
* [diabetes_with_labs.json](file:///d:/College/Capstone/Sem_7/capstone_repo/demo_inputs/diabetes_with_labs.json): High-risk T2DM with full laboratory panel (HbA1c $7.2\%$, fasting insulin $140\,\mu\text{IU/mL}$).
* [diabetes_sample.json](file:///d:/College/Capstone/Sem_7/capstone_repo/demo_inputs/diabetes_sample.json): Standard survey-based diabetes profile with optional labs omitted.
* [hypertension_with_lipids.json](file:///d:/College/Capstone/Sem_7/capstone_repo/demo_inputs/hypertension_with_lipids.json): Stage 2 hypertension with complete lipid panel (total cholesterol $245\,\text{mg/dL}$).
* [hypertension_sample.json](file:///d:/College/Capstone/Sem_7/capstone_repo/demo_inputs/hypertension_sample.json): Moderate hypertension profile without lab panels.
* [early_stage_ckd.json](file:///d:/College/Capstone/Sem_7/capstone_repo/demo_inputs/early_stage_ckd.json): Stage 2 early renal impairment with microalbuminuria.
* [ckd_sample.json](file:///d:/College/Capstone/Sem_7/capstone_repo/demo_inputs/ckd_sample.json): Standard questionnaire-based CKD profile.
* [healthy_baseline.json](file:///d:/College/Capstone/Sem_7/capstone_repo/demo_inputs/healthy_baseline.json): Healthy normotensive young adult control (Low Risk baseline).

---

## 12. Complete File-by-File Repository Map

```
capstone_repo/
├── .gitignore                         # Configures repository exclusions: ignores temporary artifacts,
│                                      # SQLite runtimes, bytecodes, and large datasets (preprocessed/ & raw/)
│                                      # while explicitly retaining unified_food_kb.csv.
├── app_data.db                        # Production SQLite database configured in WAL mode containing 11 tables.
├── README.md                          # Definitive, exhaustive platform technical documentation.
├── requirements.txt                   # Pinned production dependencies (FastAPI, Scikit-Learn, Pandas, etc.).
│
├── artifacts/
│   ├── ckd_features.json              # 30 ordered feature names for CKD model inputs.
│   ├── ckd_model.joblib               # Calibrated HistGradientBoosting model for CKD risk prediction.
│   ├── diabetes_features.json         # 17 ordered feature names (including interaction features) for T2DM.
│   ├── diabetes_model.joblib          # Calibrated HistGradientBoosting model for T2DM risk prediction.
│   ├── hypertension_features.json     # 19 ordered feature names for Hypertension risk prediction.
│   ├── hypertension_model.joblib      # Calibrated HistGradientBoosting model for Hypertension risk prediction.
│   ├── nutrient_calibration_rules.json# Scoring weights, dietary guideline targets, and distribution percentiles.
│   ├── population_medians.json        # Empirical training cohort medians used for dynamic lab imputation.
│   └── risk_thresholds_and_factors.json# Calibrated thresholds, test metrics, and permutation feature importances.
│
├── backend/
│   ├── __init__.py                    # Backend package initializer.
│   ├── adaptation_engine.py           # Longitudinal meal deviation detection, alert generation, and habit learning.
│   ├── agent_engine.py                # AgenticMealPlanner for recipe synthesis, personalization, and fallback advice.
│   ├── app.py                         # Core FastAPI application defining lifespan context and 21 REST endpoints.
│   ├── db.py                          # Concurrency-safe SQLite WAL persistence, context managers, and CRUD APIs.
│   ├── feedback_learning.py           # Patient satisfaction tracking, longitudinal biomarker trends, and outcomes.
│   ├── medical_knowledge.py           # 18+ medication pharmacopeia, clinical guideline evidence, and drug interactions.
│   ├── model_registry.py              # Singleton registry loading joblib models and executing calibrated predictions.
│   ├── raw_input.py                   # Conversational questionnaire mapper, dynamic imputer, and feature scaler.
│   ├── reporting.py                   # Food KB ranking engine (_score_foods) and clinical narrative builder.
│   ├── rules.py                       # Comorbidity constraint solver resolving the KDOQI vs. DASH potassium paradox.
│   ├── safety_engine.py               # Multi-tier safety boundary checker and active drug cross-referencing.
│   ├── schemas.py                     # Strict Pydantic v2 schemas for request/response validation.
│   └── chatbot/
│       ├── __init__.py                # Chatbot package initializer.
│       ├── agent.py                   # ReAct conversational loop with pre-LLM regex escalation & offline fallback.
│       ├── system_prompt.py           # Clinical safety guardrail prompt and regex escalation patterns.
│       └── tools.py                   # 5 grounded tools with culinary synonym dictionary and fuzzy search.
│
├── datasets/
│   ├── unified_food_kb.csv            # 7,110 curated Indian and global food items with 40 attributes.
│   └── preprocessed/                  # 1,224,788 population-scale clinical records across 9 train/test splits.
│
├── demo_inputs/                       # 8 JSON test profiles representing diverse clinical and control scenarios.
│
└── scripts/
    ├── benchmark_models.py            # Evaluates trained models against held-out test splits and reports metrics.
    ├── calibrate_nutrition.py         # Generates nutrient calibration rules from the unified food knowledge base.
    ├── predict_cli.py                 # Interactive terminal wizard and batch JSON file prediction tool.
    ├── preprocess_data.py             # Feature engineering, scaling, splitting, and SMOTE balancing pipeline.
    ├── smoke_test.py                  # Automated 21-endpoint regression test suite and comorbidity validator.
    └── train_and_optimize.py          # 5-fold CV tournament, Platt calibration, and artifact export pipeline.
```

---

## 13. Installation, Verification & Quick Start

### 1. Environment Setup
```powershell
# Clone the repository and navigate to root
cd capstone_repo

# Create and activate a Python virtual environment (Python 3.10+)
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install lean production dependencies
pip install -r requirements.txt
```

### 2. Verify Pipeline & Run Benchmarks
All model weights and feature manifests are pre-built in `artifacts/`. You can immediately benchmark the models or run smoke tests:
```powershell
# Run the comprehensive 21-endpoint smoke test suite
python scripts/smoke_test.py

# Run diagnostic model benchmarks across held-out test cohorts
python scripts/benchmark_models.py
```

### 3. Launch the REST API Server
```powershell
# Launch FastAPI with multi-worker scaling
uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
```
API Documentation will be live at:
* **Interactive Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **ReDoc Documentation:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

### 4. Optional: Big Dataset Retraining Pipeline
To retrain and recalibrate all models from raw datasets:
```powershell
# 1. Ingest, engineer features, scale, and split datasets
python scripts/preprocess_data.py

# 2. Execute 5-fold CV candidate tournament, Platt calibration, and export artifacts
python scripts/train_and_optimize.py

# 3. Calibrate food knowledge base nutrient scoring rules
python scripts/calibrate_nutrition.py
```

---

## 14. Regulatory Compliance & Medical Disclaimer

### Non-Device Clinical Decision Support (CDS) Regulatory Architecture
This platform has been engineered to comply with the **FDA Final Guidance on Clinical Decision Support Software (January 2026)** to operate outside the regulatory classification of Software as a Medical Device (SaMD):
1. **Independent Reviewability:** The software provides complete traceability for every recommendation, exposing the underlying clinical guidelines (KDOQI, DASH, ADA), the machine learning probability score, the decision threshold used, and the top contributing risk factors.
2. **Healthcare Professional Oversight:** The system is explicitly framed as an informational decision-support and patient wellness tool, designed to augment rather than replace professional clinical judgment.
3. **No Autonomous Clinical Action:** The platform does not alter drug dosages, diagnose medical conditions, or provide acute medical intervention recommendations.
4. **Hard Safety Guardrails:** All user queries referencing medication changes, drug adjustments, or acute medical symptoms are intercepted prior to language model reasoning by deterministic regex filters, returning a standardized clinical escalation referral.

### Medical Disclaimer
> **IMPORTANT MEDICAL NOTICE:**  
> This software is intended solely for academic research, health education, and nutritional decision support. It is not an FDA-cleared diagnostic device, clinical monitoring tool, or medical treatment system. The dietary plans, nutrient limits, and risk probabilities provided by this system do not constitute medical advice or establish a physician-patient relationship. Users must consult a licensed physician, registered dietitian, or nephrologist before initiating dietary changes, modifying physical activity, or adjusting prescribed medications. In the event of acute clinical symptoms or a medical emergency, immediately contact local emergency services.
