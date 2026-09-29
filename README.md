# NutriMed AI (Nutriloop)
### Precision Clinical Nutrition & Multi-Disease Risk Intelligence Platform

[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PyWebView](https://img.shields.io/badge/Desktop-PyWebView%20%2B%20Edge%20WebView2-blue?logo=windows&logoColor=white)](https://pywebview.flowrl.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Clinical Guidelines](https://img.shields.io/badge/Clinical%20Standards-KDIGO%202024%20%7C%20KDOQI%202020%20%7C%20ADA%202024%20%7C%20DASH-critical)](https://kdigo.org)

**NutriMed AI (Nutriloop)** is an enterprise-grade clinical decision support and personalized medical nutrition therapy (MNT) platform. Engineered for patients managing chronic conditions—specifically **Chronic Kidney Disease (CKD)**, **Essential Hypertension (HTN)**, and **Type 2 Diabetes Mellitus (T2DM)**—the system bridges calibrated machine-learning risk intelligence with guideline-adherent dietary synthesis.

---

## Table of Contents
1. [Core Architectural Pillars](#1-core-architectural-pillars)
2. [Clinical Target Derivation & Priority Hierarchy](#2-clinical-target-derivation--priority-hierarchy)
3. [7-Day / 5-Interval Cultural Meal Engine](#3-7-day--5-interval-cultural-meal-engine)
4. [Pharmacopeia & Drug-Nutrient Safety Guardrails](#4-pharmacopeia--drug-nutrient-safety-guardrails)
5. [Multi-Tier Conversational AI Assistant & Clinical Agent](#5-multi-tier-conversational-ai-assistant--clinical-agent)
6. [Datasets & Population Cohort Scale](#6-datasets--population-cohort-scale)
7. [System Architecture & Data Flow](#7-system-architecture--data-flow)
8. [Directory Structure](#8-directory-structure)
9. [Installation & Setup](#9-installation--setup)
10. [Desktop Application & Standalone Build](#10-desktop-application--standalone-build)
11. [REST API Documentation](#11-rest-api-documentation)
12. [Verification & Automated Test Suites](#12-verification--automated-test-suites)
13. [Ethical & Regulatory Compliance](#13-ethical--regulatory-compliance)

---

## 1. Core Architectural Pillars

```
+-------------------------------------------------------------------------------+
|                               NutriMed AI Platform                            |
+------------------------------------+------------------------------------------+
|  1. Diagnostic Risk Intelligence   |  2. Precision Nutrition Synthesis        |
|  - Calibrated ML (RF, LGBM, XGB)   |  - Mifflin-St Jeor TDEE Derivation       |
|  - CKD-EPI 2021 eGFR Calculation   |  - Dynamic Calorie & Portion Scaler      |
|  - Multimorbid Comorbidity Engine  |  - 155+ Regional Dish Catalog (5 Regions)|
|  - SHAP Factor Attribution         |  - Biomarker-Responsive Dish Prioritizer |
+------------------------------------+------------------------------------------+
|  3. Clinical Safety Guardrails     |  4. Multi-Tier AI Clinical Assistant     |
|  - 31 Drug-Nutrient Cross-Checks   |  - Cloud LLMs (Gemini Flash, GPT-4o-mini)|
|  - Daily Schedule Plan Validation  |  - Local ReAct LLM (Ollama)              |
|  - SGLT2i euDKA Carb Floor         |  - Deep Generative Clinical Synthesizer  |
|  - ACC/AHA DASH Sodium Ceiling     |  - Live Meal Plan Natural Language Swap  |
+------------------------------------+------------------------------------------+
```

1. **Dual In-Process / Client-Server Runtime**: Runs either as a 100% offline desktop application with native Edge WebView2 or as a headless REST microservice.
2. **Zero Bytecode Clutter**: Configured with `PYTHONDONTWRITEBYTECODE=1` and `sys.dont_write_bytecode = True` across all entry points, guaranteeing zero `__pycache__` footprint.
3. **Rigorous Clinical Grounding**: Follows KDIGO 2024, KDOQI 2020, ADA 2024, and ACC/AHA DASH clinical guidelines.
4. **Local-First Privacy**: Patient records, lab values, and chat logs are stored in a dedicated local directory (`Nutriloop_Data/app_data.db`), ensuring HIPAA-aligned data sovereignty.

---

## 2. Clinical Target Derivation & Priority Hierarchy

When managing multi-morbid patients (e.g. CKD Stage 3 + Stage 2 HTN + T2DM), standard dietary guidelines often present conflicting advice. NutriMed AI resolves these conflicts through a strict **Clinical Precedence Protocol**:

```
+--------------------------------------------------------------------------+
|                   CLINICAL CONFLICT RESOLUTION MATRIX                    |
+--------------------------------------------------------------------------+
| Condition Conflict       | Clinically Enforced Rule                      |
+--------------------------+-----------------------------------------------+
| DASH Potassium Loading   | KDIGO/KDOQI Renal Priority:                   |
| (>= 4700 mg/day) vs.     | When eGFR < 60 mL/min or Serum K+ >= 5.0,     |
| Renal Hyperkalemia Risk  | potassium is capped at <= 2000 mg/day.        |
+--------------------------+-----------------------------------------------+
| Overweight / Obese       | KDOQI 2020 Adjusted Body Weight (aBW):        |
| High Protein Intake      | aBW = IBW + 0.25 * (Actual - IBW)             |
| vs. Renal Hyperfiltration| Prevents glomerular overloading in CKD.       |
+--------------------------+-----------------------------------------------+
| Ketogenic / Low Carb     | ADA 2024 Carbohydrate Floor:                  |
| vs. SGLT2i Therapy       | Enforces >= 130 g/day carbs to prevent        |
| (Empagliflozin/Jardiance)| fatal Euglycemic Ketoacidosis (euDKA).        |
+--------------------------+-----------------------------------------------+
| Stage 2 Hypertension     | ACC/AHA DASH Sodium Ceiling:                  |
| Fluid Retention          | Enforces <= 1500 mg/day sodium.               |
+--------------------------+-----------------------------------------------+
```

### Automated eGFR Calculation (CKD-EPI 2021)
If a laboratory panel omits eGFR, the engine computes it using the race-free CKD-EPI 2021 formula:
$$\text{eGFR} = 142 \times \min\left(\frac{S_{cr}}{\kappa}, 1\right)^\alpha \times \max\left(\frac{S_{cr}}{\kappa}, 1\right)^{-1.200} \times 0.9938^{\text{Age}} \times [1.012 \text{ if Female}]$$
*(where $\kappa = 0.7$ for females, $0.9$ for males; $\alpha = -0.241$ for females, $-0.302$ for males).*

---

## 3. 7-Day / 5-Interval Cultural Meal Engine

The diet recommendation component generates an authentic, nutritionally balanced 7-day plan with **5 daily intervals**:
1. **Breakfast** (25% daily calories) — 08:00–09:00
2. **Mid-Morning Snack** (10% daily calories) — 11:00–11:30
3. **Lunch** (35% daily calories) — 13:00–14:00
4. **Evening Snack** (10% daily calories) — 16:30–17:30
5. **Dinner** (20% daily calories) — 19:30–20:30

### Dynamic Portion Scaling & Caloric Precision
Unlike basic recipe assemblers that underfeed patients by ~40%, NutriMed AI uses a two-tier dynamic portion scaler:
- **`scale_dish_items`**: Calculates $R = \text{interval\_target\_kcal} / \text{base\_dish\_kcal}$ (clamped safely between $0.50\times$ and $2.40\times$). Scales calories, proteins, carbohydrates, healthy fats, sodium, and potassium proportionately.
- **`scale_portion_string`**: Dynamically adjusts human-readable portion strings (`2 idlis` $\to$ `3 idlis`, `1 cup` $\to$ `1.4 cups`, `150 g` $\to$ `210 g`, `2 rotis` $\to$ `3 rotis`) so patient instructions reflect the exact calculated calories.
- **Caloric Target Adherence**: Consistently achieves **$\pm 0.5\%$** of target calories across all 5 regional cuisines.

### Condition-Scored Dish Prioritization & Biomarker Responsiveness
Rather than rotating through static menus irrespective of clinical reports, the meal engine actively evaluates patient diagnostic biomarkers and scores available regional recipes:
- **Type 2 Diabetes & Prediabetes**: Penalizes high-GI refined flours (maida, polished white rice) by up to -80 points; promotes low-GI complex grains (ragi, steel-cut oats, bajra, foxtail millet, besan) and soluble-fiber-rich legumes by +30 to +50 points. Automatically sets a high fiber floor ($\ge 35$ g/day) and reduces carbohydrate load by 15–25%.
- **Stage 2 Hypertension**: Prioritizes natriuretic low-sodium meals (bottle gourd, zucchini, ridge gourd, ivy gourd) seasoned with garlic and coriander, enforcing the ACC/AHA DASH limit ($\le 1500$ mg/day sodium).
- **Chronic Kidney Disease (CKD)**: Restricts high-potassium ingredients (raw spinach, bananas, tender coconut water) to protect against hyperkalemic cardiotoxicity, prioritizing renal-safe vegetables (lauki, snake gourd kootu).
- **Personalized Clinical Justifications**: Every single meal in the 7-day schedule provides an individualized clinical rationale citing the patient's actual diagnostic lab values (e.g. `[Diabetic MNT: Low-GI complex grain (<55 GI) paired with 11.8g soluble fiber to control postprandial glucose spike (FBS 220 mg/dL, HbA1c 9.8%)]`).
- **User Preference Matching**: Requested food likes (e.g. rasam, chaas) are prioritized within clinical safety bounds and highlighted with a `[⭐ Preferred Choice]` badge.

### 5 Cultural Regions (155+ Catalog Dishes)
Zero duplicate days—every region has at least 7 unique breakfasts, 5 mid-morning snacks, 7 unique lunches, 5 evening snacks, and 7 unique dinners:
- 🌴 **South Indian**: Idli with Sambar, Ragi Koozh, Moong Dal Pesarattu, Brown Rice Vegetable Sambar Sadam, Foxtail Millet Khichdi.
- 🌾 **North Indian**: Methi Thepla, Daliya Khichdi, Besan Chilla, Whole Wheat Roti with Bhindi Masala, Palak Tofu/Paneer with Multigrain Roti.
- 🌊 **Western Indian**: Jowar Bhakri with Baingan Bharta, Khaman Dhokla, Handvo, Dal Baati (Modified Low GI), Sprouts Usal with Ragi Bhakri.
- 🌿 **Eastern Indian**: Sattu Paratha with Baingan Chokha, Panta Bhat, Steamed Ilish/Machher Jhol or Chana Dal, Shukto with Rice, Ghugni with Roti.
- 🥗 **Continental**: Steel-cut Oatmeal with Chia Seeds, Quinoa Power Bowl with Steamed Broccoli, Grilled Chicken/Tofu with Asparagus, Lentil Minestrone Soup.

### Dietary Philosophies & Allergen Elimination
- **Supported Dietary Types**: `Vegetarian`, `Non-Vegetarian`, `Vegan`, `Eggetarian`, `Jain`.
- **Strict Jain Compliance**: 0 onion, 0 garlic, 0 root vegetables (no potatoes, carrots, beets, or radishes).
- **Allergen Filtration**: Hard elimination of peanuts, gluten, dairy, tree nuts, shellfish, or user dislikes across all ingredients.

### Smart Craving Strategy
Permits one structured, scheduled indulgence per week (e.g. Saturday evening snack) while rebalancing surrounding intervals and enforcing strict zero-sugar adherence on Days 1–6.

### Categorized Grocery Checklist
Groceries are organized into 5 structured supermarket aisles:
- 🥬 **Fresh Produce & Vegetables**
- 🌾 **Whole Grains & Pulses**
- 🥛 **Dairy, Eggs & Proteins**
- 🌰 **Nuts, Seeds & Spices**
- 🫒 **Oils & Condiments**

---

## 4. Pharmacopeia & Drug-Nutrient Safety Guardrails

The integrated [safety_engine.py](backend/safety_engine.py) screens active patient medications against 31 clinical drug monographs:

| Drug Class | Examples | Dietary Contraindications & Monitoring |
| :--- | :--- | :--- |
| **ACE Inhibitors** | Lisinopril, Ramipril, Enalapril | Avoid potassium chloride salt substitutes; monitor high-potassium foods (bananas, coconut water). |
| **ARBs** | Losartan, Telmisartan, Valsartan | Restrict salt substitutes; risk of additive hyperkalemia. |
| **SGLT2 Inhibitors** | Empagliflozin, Dapagliflozin | **Strict carbohydrate floor ($\ge 130$ g/day)**; ketogenic diets strictly contraindicated due to euDKA risk. Ensure adequate hydration. |
| **Calcium Channel Blockers** | Amlodipine, Diltiazem | **Strict ban on grapefruit and Seville oranges** (CYP3A4 inhibition). |
| **Statins** | Atorvastatin, Rosuvastatin | Avoid grapefruit products; monitor for myopathy. |
| **Loop Diuretics** | Furosemide, Torsemide | Monitor for hypokalemia, hypomagnesemia, and volume depletion. |
| **K-Sparing Diuretics** | Spironolactone, Eplerenone | Strict cap on potassium intake ($\le 2000$ mg/day); avoid salt substitutes. |
| **Biguanides** | Metformin | Take with meals to reduce GI distress; screen for B12 deficiency; avoid heavy alcohol (lactic acidosis). |
| **Sulfonylureas** | Glimepiride, Glipizide | Enforce consistent meal timing; avoid skipping meals (hypoglycemia risk). |

---

## 5. Multi-Tier Conversational AI Assistant & Clinical Agent

Nutriloop features a multi-tier conversational medical AI architecture designed to deliver real-time, frontier clinical intelligence while guaranteeing 100% offline functionality, privacy, and clinical safety:

```
[User Chat Consultation / Query]
               |
               v
+-------------------------------------------------------+
|  Tier 0: Pre-LLM Acute Emergency Guardrail            | ---> Immediate Emergency Escalation
|  (Interprets acute chest pain, dyspnea, ketoacidosis) |      (Zero LLM Latency, 911/112 referral)
+--------------------------+----------------------------+
                           | Passed safety screening
                           v
+-------------------------------------------------------+
|  Tier 1: Google Gemini 1.5 Flash (Cloud API)          | ---> High-speed, frontier medical reasoning
+--------------------------+----------------------------+
                           | If key absent / offline
                           v
+-------------------------------------------------------+
|  Tier 2: OpenAI GPT-4o-mini (Cloud API)               | ---> Enterprise frontier conversational AI
+--------------------------+----------------------------+
                           | If key absent / offline
                           v
+-------------------------------------------------------+
|  Tier 3: Local Ollama Model (llama3.2:3b / mistral)   | ---> 100% local, zero-telemetry neural weights
+--------------------------+----------------------------+
                           | If Ollama runtime uninstalled
                           v
+-------------------------------------------------------+
|  Tier 4: Deep Clinical Reasoning Synthesizer          | ---> Instant generative biochemical & MNT reasoning
|  (Biomarker-grounded rules, foods & drug safety)      |      citing patient FBS, HbA1c, BP, and eGFR
+-------------------------------------------------------+
```

### Key Capabilities

1. **Frontier Cloud Intelligence with In-App Switcher**:
   - Tab 3 (Chat) includes a native **AI Engine & API Key Toolbar**.
   - Supports **Google Gemini 1.5 Flash** (recommended, free tier available via [Google AI Studio](https://aistudio.google.com/app/apikey)) and **OpenAI GPT-4o-mini**.
   - API keys are persisted securely in the local SQLite `app_settings` table.

2. **Patient Medical Dossier Grounding**:
   - Every agent invocation dynamically constructs and injects the patient's full diagnostic panel (age, sex, BMI, BP, Fasting Glucose, HbA1c, Serum Creatinine, eGFR, Potassium, Sodium), active medications, and the complete active 7-Day Regional Meal Plan into the system prompt.

3. **Generative Deep Clinical Synthesizer (Zero-Key Offline Mode)**:
   - When offline without an API key, Dr. Nutriloop does **not** rely on canned or predefined one-liners. Instead, it runs an in-depth clinical reasoning synthesizer:
     - **Specific Food Evaluations**: Detailed glycemic, renal, and cardiovascular analysis for regional and common foods (e.g. *Pepper-Cumin Rasam*, *Instant Noodles / Maggi* with clinical whole-wheat atta recipe adaptations, *Sunday Biryani craving management*, *85%+ dark chocolate vs milk chocolate*, *curd/chaas probiotics*, *paneer vs tofu protein titration*, and *banana potassium restrictions in CKD*).
     - **Biomarker Pathophysiology**: Thorough explanations of HbA1c, fasting glucose, serum creatinine, and eGFR renal filtration dynamics.
     - **Pharmacopeia & Drug-Nutrient Rules**: Alerts on SGLT2i carbohydrate floors ($\ge 130$ g/day) to prevent euglycemic DKA, Metformin meal timing, ACEi potassium sparing, and Amlodipine CYP3A4 grapefruit juice contraindications.

4. **Live Natural Language Meal Alterations**:
   - Patients can request meal swaps directly in chat (e.g., *"Replace Tuesday dinner with vegetable soup"*). The agent parses the request, executes `TOOL_REGISTRY["alter_diet_plan_meal"]`, updates the active 7-day schedule in SQLite, and refreshes Tab 2 live.

5. **Rich Markdown Chat UI**:
   - Chat bubbles render clean GitHub-flavored markdown including headings, bold emphasis, structured lists, and code blocks for a modern conversational experience.

---

## 6. Datasets & Population Cohort Scale

NutriMed AI is trained and calibrated on large-scale population health cohorts and an exhaustive clinical food knowledge base totaling **691.57 MB** across **1,231,898 total records**:

```
+---------------------------------------------------------------------------------------------------------+
|                                    NUTRILOOP DATASET ARCHITECTURE                                       |
+------------------------------+---------+------------+----------+----------------------------------------+
| Dataset Component            | Format  | Size (MB)  | Records  | Clinical Attributes & Target Features  |
+------------------------------+---------+------------+----------+----------------------------------------+
| Unified Food Knowledge Base  | CSV     | 2.53 MB    | 7,110    | 40 nutritional, glycemic & renal attrs |
| CKD Preprocessed Cohort      | CSV     | 139.87 MB  | 489,322  | 29 biomarkers (eGFR, Cr, BP, Urea, Na) |
|   ├── Train Split (SMOTE)    | CSV     | 111.90 MB  | 391,457  | Class-balanced training subset         |
|   └── Held-out Test Split    | CSV     | 27.96 MB   | 97,865   | Unseen validation cohort               |
| Diabetes Preprocessed Cohort | CSV     | 103.08 MB  | 335,725  | 18 biomarkers (HbA1c, FBS, BMI, Age)   |
|   ├── Train Split (SMOTE)    | CSV     | 82.46 MB   | 268,580  | Class-balanced training subset         |
|   └── Held-out Test Split    | CSV     | 20.61 MB   | 67,145   | Unseen validation cohort               |
| Hypertension Cohort          | CSV     | 101.58 MB  | 399,741  | 20 hemodynamic indicators (SBP, DBP)   |
|   ├── Train Split (SMOTE)    | CSV     | 81.26 MB   | 319,792  | Class-balanced training subset         |
|   └── Held-out Test Split    | CSV     | 20.32 MB   | 79,949   | Unseen validation cohort               |
+------------------------------+---------+------------+----------+----------------------------------------+
| Total Repository Data Scale  | --      | 691.57 MB  | 1,231,898| Multi-disease & MNT clinical footprint |
+------------------------------+---------+------------+----------+----------------------------------------+
```

### 1. Unified Food Knowledge Base (`datasets/unified_food_kb.csv`)
- **Total Scale**: **7,110 items** (2.53 MB).
- **Attribute Coverage**: 40 distinct chemical, macro/micronutrient, and culinary features per item.
- **Attributes Tracked**: Calories (kcal), protein (g), total carbohydrates (g), dietary fiber (g), soluble fiber (g), free sugars (g), total fats (g), saturated fats (g), monounsaturated fats (MUFA), polyunsaturated fats (PUFA), sodium (mg), potassium (mg), phosphorus (mg), calcium (mg), magnesium (mg), iron (mg), glycemic index (GI), glycemic load (GL), culinary region (South Indian, North Indian, Western Indian, Eastern Indian, Continental), and dietary classifications (`vegetarian`, `vegan`, `jain`, `eggetarian`, `non-vegetarian`).

### 2. Multi-Disease Clinical Training & Validation Splits (`datasets/preprocessed/`)
Encompasses **1,224,788 population-scale clinical records** (~689 MB) split into rigorous 80/20 train/test partitions with Synthetic Minority Over-sampling Technique (SMOTE) class balancing applied strictly to training partitions to prevent data leakage:
- **Chronic Kidney Disease (CKD)**: 489,322 total records (29 attributes including serum creatinine, eGFR, serum potassium, blood urea nitrogen, urine albumin, systolic/diastolic BP, diabetes comorbidity, and cardiovascular history).
- **Type 2 Diabetes Mellitus (T2DM)**: 335,725 total records (18 attributes including HbA1c, fasting plasma glucose, BMI, physical activity index, lipid profile, and age).
- **Essential Hypertension (HTN)**: 399,741 total records (20 attributes including systolic BP, diastolic BP, heart rate, sodium intake index, smoking status, and BMI).

### 3. Methodological Rigor & Leakage Prevention
To guarantee publication-grade validity and clinical peer-review compliance, all training and preprocessing pipelines adhere to strict methodological safeguards:
- **Target Leakage Remediation**: Resolved target leakage in the NHANES hypertension cohort by decoupling `BPMeds` from the outcome label `BPQ020` ("Ever told had high blood pressure") and re-mapping it strictly to `BPQ050A` ("Currently taking prescribed medication").
- **Indeterminate Code Isolation**: Built `map_nhanes_yes_no()` to strictly isolate binary responses (`1.0` -> 1, `2.0` -> 0), ensuring borderline codes (`3.0`) and non-responses (`7.0`, `9.0`) are treated as missing (`NaN`) rather than falsely counted as disease-free negatives.
- **Out-of-Fold Threshold Locking**: Decision thresholds (`moderate` and `high`) are derived strictly on training splits using `out_of_fold_probabilities()` across 5-fold cross-validation, locking decision boundaries before evaluating untouched held-out test splits.
- **Safe Process Isolation**: Ollama background process management uses targeted PID termination (`taskkill /PID <pid>`), guaranteeing that user-managed system-wide Ollama instances are never terminated.

---

## 7. System Architecture & Data Flow

```
                      +-----------------------------+
                      |   PyWebView Native Window   |
                      |   (HTML5 / CSS3 / VanillaJS)|
                      +--------------+--------------+
                                     |  pywebview.api
                                     v
                      +-----------------------------+
                      |       desktop_api.py        |
                      +--------------+--------------+
                                     |
        +----------------------------+----------------------------+
        |                            |                            |
        v                            v                            v
+---------------+            +---------------+            +---------------+
|  ML Registry  |            | Weekly Engine |            | Ollama Agent  |
| (RF/LGBM/XGB) |            | (Portion/MNT) |            | (ReAct Tools) |
+-------+-------+            +-------+-------+            +-------+-------+
        |                            |                            |
        +----------------------------+----------------------------+
                                     |
                                     v
                      +-----------------------------+
                      |      SQLite app_data.db     |
                      |  (Logs, Meals, Plans, Hist) |
                      +-----------------------------+
```

---

## 8. Directory Structure

```
Nutriloop/
├── .gitignore                        # Git exclusion rules
├── app_desktop.py                    # Standalone desktop executable launcher (Edge WebView2)
├── desktop_api.py                    # Python-JavaScript in-process bridge for PyWebView
├── Nutriloop.spec                    # PyInstaller standalone build configuration
├── requirements.txt                  # Python package dependencies
├── artifacts/                        # Trained ML models, scalers, and clinical thresholds
│   ├── ckd_best_model.pkl
│   ├── hypertension_best_model.pkl
│   ├── diabetes_best_model.pkl
│   └── risk_thresholds_and_factors.json
├── backend/                          # Core business logic & clinical engines
│   ├── __init__.py                   # Global bytecode write suppression
│   ├── app.py                        # FastAPI application (22 endpoints)
│   ├── db.py                         # SQLite schema & persistence helpers (app_settings, tests)
│   ├── model_registry.py             # Model loader & inference wrapper
│   ├── ollama_manager.py             # Ollama discovery, health, & download manager
│   ├── raw_input.py                  # Clinical survey mapping & imputation
│   ├── reporting.py                  # Clinical report formatting & text generation
│   ├── rules.py                      # eGFR CKD-EPI, KDIGO, KDOQI, DASH logic
│   ├── safety_engine.py              # 31-drug interaction & meal validation engine
│   ├── schemas.py                    # Pydantic v2 data models & validators
│   ├── weekly_diet_engine.py         # Precision 7-day MNT & portion scaler engine
│   └── chatbot/                      # Multi-tier conversational AI subsystem
│       ├── agent.py                  # Multi-tier dispatch (Gemini, OpenAI, Ollama, Synthesizer)
│       ├── system_prompt.py          # Clinical prompt engineering & safety guardrails
│       └── tools.py                  # Guidelines, drug interaction, & plan alteration tools
├── bin/                              # Bundled platform binaries (e.g. Ollama for Windows)
├── datasets/                         # Medical nutrition & clinical cohorts (~691.57 MB)
│   ├── unified_food_kb.csv           # 7,110 items with 40 nutritional attributes (2.53 MB)
│   └── preprocessed/                 # 1,224,788 clinical records across 9 splits (689.04 MB)
│       ├── ckd_preprocessed.csv      # 489,322 patient records (139.87 MB)
│       ├── ckd_train_smote.csv       # 391,457 balanced training records (111.90 MB)
│       ├── ckd_test.csv              # 97,865 held-out validation records (27.96 MB)
│       ├── diabetes_preprocessed.csv # 335,725 patient records (103.08 MB)
│       ├── diabetes_train_smote.csv  # 268,580 balanced training records (82.46 MB)
│       ├── diabetes_test.csv         # 67,145 held-out validation records (20.61 MB)
│       ├── hypertension_preprocessed.csv # 399,741 patient records (101.58 MB)
│       ├── hypertension_train_smote.csv  # 319,792 balanced training records (81.26 MB)
│       └── hypertension_test.csv     # 79,949 held-out validation records (20.32 MB)
├── gui/                              # Modern dark-mode UI
│   ├── index.html                    # Single-page interface with Tab 3 AI Engine Toolbar
│   ├── style.css                     # Responsive CSS design system with Markdown styling
│   └── app.js                        # Client state, PyWebView bridge, Markdown parser, & chart rendering
├── Nutriloop_Data/                   # Auto-created runtime patient directory (app_data.db, reports)
└── scripts/                          # Verification, preprocessing & benchmarking tools
    ├── benchmark_models.py           # Model evaluation suite (F1, PR-AUC, Brier score)
    ├── evaluate_public_cohorts.py    # Leakage-free benchmark evaluator across 10 ML algorithms
    ├── predict_cli.py                # Command-line prediction tool
    ├── preprocess_data.py            # Multi-cohort feature engineering & leakage-free mapper
    ├── smoke_test.py                 # 22-endpoint REST API smoke test suite
    ├── test_diet_accuracy.py         # Precision clinical diet accuracy test suite
    └── train_and_optimize.py         # Out-of-fold threshold tuning & model serializer
```

---

## 9. Installation & Setup

### Prerequisites
- **Python**: 3.10, 3.11, or 3.12 (64-bit)
- **Operating System**: Windows 10/11, macOS, or Linux
- **AI Models** *(Optional)*: Google Gemini API Key, OpenAI API Key, or local [Ollama](https://ollama.ai)

### 1. Clone Repository & Create Virtual Environment
```bash
git clone https://github.com/your-org/nutriloop.git
cd nutriloop

python -m venv venv
# Windows:
.\venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Launch Desktop Application
```bash
python app_desktop.py
```

### 4. Launch FastAPI REST Service (Alternative)
```bash
uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
```
Navigate to `http://127.0.0.1:8000/docs` for the interactive Swagger documentation.

---

## 10. Desktop Application & Standalone Build

NutriMed AI (Nutriloop) packages into a single, standalone Windows `.exe` (~189 MB) with zero external runtime dependencies:

```powershell
# Build standalone Windows executable with bytecode write suppression
$env:PYTHONDONTWRITEBYTECODE="1"
pyinstaller --noconfirm Nutriloop.spec
```
The output executable is generated at:
```
dist/Nutriloop.exe
```

### Self-Contained Runtime Behavior
- **Bundled Assets**: Embeds all GUI HTML/CSS/JS assets, scikit-learn models, scalers, food knowledge base, and platform binaries directly into the single executable.
- **Isolated Data Sovereignty**: Upon first launch (or when moved to a new directory), the executable automatically creates a dedicated `Nutriloop_Data/` folder alongside itself containing `app_data.db`, audit logs, and exported patient reports, completely isolated from user profile system noise.

---

## 11. REST API Documentation

The platform exposes **22 REST endpoints**:

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Service health status. |
| `GET` | `/implementation-progress` | Model training and deployment metadata. |
| `GET` | `/raw-input-template/{disease}` | Questionnaire template for disease input. |
| `POST` | `/predict-risk-raw` | Multi-disease risk evaluation from raw clinical inputs. |
| `POST` | `/risk-explanation-raw` | SHAP factor attributions and clinical explanations. |
| `POST` | `/risk-report-raw` | Comprehensive multi-page clinical risk report. |
| `POST` | `/recommend-plan` | Single-meal nutrition therapy recommendation. |
| `POST` | `/recommend-weekly-plan` | **7-day / 5-interval personalized regional weekly diet plan**. |
| `POST` | `/safety/validate` | Real-time meal nutrient and drug interaction safety check. |
| `GET` | `/medical/drug-interactions/{med}` | Drug-nutrient interaction monograph. |
| `GET` | `/medical/guidelines` | Clinical practice guidelines (KDIGO, KDOQI, ADA, DASH). |
| `POST` | `/log-meal` | Log patient meal consumption to SQLite. |
| `POST` | `/adaptation/log-meal` | Feedback adaptation meal logging. |
| `GET` | `/adaptation/summary/{user_id}` | Patient adherence trend analysis. |
| `POST` | `/chatbot/chat` | AI Clinical Nutritionist conversational endpoint. |

---

## 12. Verification & Automated Test Suites

### Precision Diet Recommendation Accuracy Suite
```bash
python scripts/test_diet_accuracy.py
```
Validates:
- **Biomarker & eGFR Derivation**: CKD Stage 3a (48.7 mL/min), SGLT2i carbohydrate floor ($\ge 130$ g), KDOQI Adjusted Body Weight protein targets.
- **Caloric Precision Across 5 Regions**: South Indian, North Indian, Western Indian, Eastern Indian, and Continental menus meet target calories within $\pm 0.5\%$.
- **Variety Audit**: Confirms 0 duplicate days across all 5 regions.
- **Dietary & Allergen Filtering**: 100% compliance for Jain (0 root veg) and allergen elimination.

### Comprehensive REST API Smoke Test Suite
```bash
python scripts/smoke_test.py
```
Validates all 22 REST endpoints, comorbidity conflict resolutions, and weekly diet plan generation with HTTP 200 status codes.

### Machine Learning Benchmark Suite
```bash
python scripts/benchmark_models.py
```
Evaluates Macro-F1, PR-AUC, ROC-AUC, Sensitivity, Specificity, and Brier calibration scores.

---

## 13. Ethical & Regulatory Compliance

- **Clinical Decision Support Notice**: NutriMed AI is designed to assist registered dietitians, nephrologists, and primary care physicians. It provides clinical decision support and does not replace professional medical diagnosis or emergency care.
- **Privacy & Security**: All inference and persistent data storage occur locally on the user's host machine. No protected health information (PHI) is transmitted to third-party cloud servers.

