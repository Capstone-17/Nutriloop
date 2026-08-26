# A Deep Learning and Generative AI-Driven Diet Recommendation System for Personalized Chronic Disease Management

> **Production Release: `Latest_Update`**  
> An enterprise-grade, clinically grounded AI healthcare platform integrating calibrated machine learning risk models, multi-morbid clinical nutrition planning (KDOQI, ADA, DASH), thread-safe SQLite persistence, longitudinal adaptation & feedback tracking, and a zero-downtime clinical chatbot agent.

---

## Table of Contents

- [Key Innovations & Capabilities](#key-innovations--capabilities)
- [System Architecture](#system-architecture)
- [Model Performance Benchmarks](#model-performance-benchmarks)
- [Clinical Intelligence & Comorbidity Solver](#clinical-intelligence--comorbidity-solver)
- [Expanded Pharmacopeia (18+ Medications)](#expanded-pharmacopeia-18-medications)
- [Directory Structure](#directory-structure)
- [Quick Start Guide](#quick-start-guide)
- [Interactive CLI Tool](#interactive-cli-tool)
- [REST API Reference (21 Endpoints)](#rest-api-reference-21-endpoints)
- [Database Persistence & Concurrency](#database-persistence--concurrency)
- [Frontend & Deployment Documentation](#frontend--deployment-documentation)
- [License & Medical Disclaimer](#license--medical-disclaimer)

---

## Key Innovations & Capabilities

1. **Non-Linear Clinical Risk Modeling**:
   - Advanced metabolic feature engineering (HOMA-IR proxy, non-linear glucose-BMI curves, age-glycemic interactions).
   - Platt probability calibration (`CalibratedClassifierCV`) delivering well-calibrated confidence scores (Brier score $< 0.18$).
2. **Dynamic Population Imputation & Adaptive Lab Inputs**:
   - Accepts optional clinical lab biomarkers (serum creatinine, blood urea, HbA1c, fasting insulin, urine dipstick, lipid panels).
   - When omitted, imputes dynamically using training population medians from [artifacts/population_medians.json](file:///d:/College/Capstone/Sem_7/capstone_repo/artifacts/population_medians.json).
3. **Multi-Condition Comorbidity Solver (The KDOQI vs. DASH Paradox Resolution)**:
   - Evaluates multi-disease patient profiles (e.g., Diabetic Nephropathy with Hypertension) and applies guideline precedence rules: **Renal electrolyte safety strictly overrides DASH potassium loading** ($\text{Potassium} \le 2,000\,\text{mg/day}$ while locking Sodium to the stricter $\le 1,500\,\text{mg/day}$ DASH bound).
4. **Expanded 18+ Drug Pharmacopeia**:
   - Automated cross-referencing of active medications (SGLT2 inhibitors, GLP-1 RAs, Beta-Blockers, CCBs, ARBs, Diuretics, Potassium/Phosphate Binders) with meal nutrients.
5. **Zero-Downtime Hybrid Chatbot & Fuzzy KB Search**:
   - Seamless degradation to the deterministic [AgenticMealPlanner](file:///d:/College/Capstone/Sem_7/capstone_repo/backend/agent_engine.py) if local LLM service (Ollama) is unreachable.
   - Built-in culinary synonym mapping (*daal*, *roti*, *paneer*, *dahi*, *chawal*, *sabzi*) and `difflib` fuzzy search across 7,110 food items.
6. **Concurrent SQLite Persistence**:
   - Write-Ahead Logging (`WAL` mode) with busy timeouts for multi-worker production scalability (`uvicorn --workers 4`).

---

## System Architecture

```
                                ┌─────────────────────────────────────────┐
                                │       Client Applications / UI          │
                                └────────────────────┬────────────────────┘
                                                     │ REST API / CLI
                                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    FastAPI Service Layer                                        │
│  ├── Health & Diagnostics      ├── Risk Prediction (Direct & Raw)   ├── Nutrition & Comorbidity │
│  ├── Multi-Agent Planner       ├── Safety & Boundary Validation     ├── Real-Time Adaptation    │
│  ├── Medical Knowledge Base    ├── Feedback & Outcomes Learning     └── Hybrid Chatbot Agent    │
└───────────────┬───────────────────────────────────┬─────────────────────────────────┬───────────┘
                │                                   │                                 │
                ▼                                   ▼                                 ▼
┌───────────────────────────────┐   ┌───────────────────────────────┐   ┌─────────────────────────┐
│     Trained ML Models         │   │   Medical Knowledge & Rules   │   │  Food Knowledge Base    │
│  • CKD (HistGradientBoosting) │   │  • KDOQI (Renal Safety)       │   │  • 7,110 Curated Items  │
│  • HTN (HistGradientBoosting) │   │  • ADA (Glycemic Control)     │   │  • 28 Standardized      │
│  • T2DM (HistGradientBoosting)│   │  • DASH (Cardiovascular)      │   │    Nutrients & Micronut.│
│  • Platt-Calibrated Scores    │   │  • Comorbidity Precedence     │   │  • Culinary Synonyms    │
│  • Dynamic Median Imputation  │   │  • 18+ Drug Interactions      │   │  • Fuzzy String Search  │
└───────────────────────────────┘   └───────────────────────────────┘   └─────────────────────────┘
```

---

## Model Performance Benchmarks

All models are trained with non-linear interaction features, SMOTE re-sampling on training folds, Platt probability calibration via `CalibratedClassifierCV(method='sigmoid')`, and tuned decision thresholds.

| Clinical Condition | Model Architecture | 5-Fold CV Macro F1 | Test Accuracy | Macro F1 | Recall (+) | Specificity | PR-AUC | ROC-AUC | Brier Score |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Chronic Kidney Disease (CKD)** | `HistGradientBoosting` | **0.9874** | **98.75%** | **0.9868** | **98.00%** | **100.0%** | **0.9985** | **0.9973** | **0.0229** |
| **Hypertension (HTN)** | `HistGradientBoosting` | **0.9155** | **89.50%** | **0.8823** | **91.25%** | **88.72%** | **0.8893** | **0.9523** | **0.0831** |
| **Type 2 Diabetes (T2DM)** | `HistGradientBoosting` | **0.8145** | **74.68%** | **0.7294** | **70.37%** | **77.00%** | **0.6358** | **0.8074** | **0.1760** |

---

## Clinical Intelligence & Comorbidity Solver

When managing overlapping chronic conditions, standard single-disease guidelines often present direct clinical contradictions. Our constraint intersection solver applies strict medical hierarchy rules:

```
                               ┌────────────────────────────────┐
                               │ Multi-Morbid Patient Profile   │
                               │ (e.g., CKD + HTN + Diabetes)   │
                               └───────────────┬────────────────┘
                                               │
                       ┌───────────────────────┴───────────────────────┐
                       ▼                                               ▼
         ┌───────────────────────────┐                   ┌───────────────────────────┐
         │     Renal Precedence      │                   │     DASH Precedence       │
         │  KDOQI Potassium Safety   │                   │    Sodium Restriction     │
         │   Potassium <= 2,000 mg   │                   │     Sodium <= 1,500 mg    │
         └─────────────┬─────────────┘                   └─────────────┬─────────────┘
                       └───────────────────────┬───────────────────────┘
                                               ▼
                               ┌───────────────────────────────┐
                               │  ADA Glycemic Restriction     │
                               │   Free Sugars <= 20 g/day     │
                               │   Carbohydrates <= 40%        │
                               └───────────────────────────────┘
```

- **CKD + Hypertension**: DASH suggests high potassium ($>3,500\,\text{mg}$), but compromised renal clearance risks fatal hyperkalemia. The solver overrides DASH with KDOQI potassium safety ($\le 2,000\,\text{mg/day}$), while applying the tighter DASH sodium restriction ($\le 1,500\,\text{mg/day}$).
- **CKD + Diabetes**: Imposes strict glycemic distribution while restricting dietary phosphorus ($\le 800\text{--}1,000\,\text{mg/day}$) and moderating protein portions ($0.18\text{--}0.20$ ratio).

---

## Expanded Pharmacopeia (18+ Medications)

The platform evaluates drug-food interactions across modern chronic disease therapeutics:

| Drug Class | Examples | Clinical Mechanism & Nutritional Warning |
| :--- | :--- | :--- |
| **SGLT2 Inhibitors** | *Empagliflozin (Jardiance), Dapagliflozin (Farxiga)* | Euglycemic DKA risk with severe carbohydrate restriction ($<100\,\text{g/d}$); dehydration warning. |
| **GLP-1 RAs** | *Semaglutide (Ozempic), Liraglutide, Tirzepatide* | Delayed gastric emptying; avoid high-fat meals to prevent severe nausea and vomiting. |
| **ACE Inhibitors & ARBs** | *Lisinopril, Ramipril, Losartan, Valsartan* | Impaired renal potassium clearance; strict warning on potassium-based salt substitutes. |
| **Beta-Blockers** | *Metoprolol, Atenolol, Carvedilol* | Blunts sympathetic response; masks hypoglycemia signs (tachycardia, tremors). |
| **CCBs** | *Amlodipine (Norvasc), Diltiazem, Nifedipine* | Irreversible intestinal CYP3A4 inhibition by grapefruit/grapefruit juice causing severe hypotension. |
| **Diuretics** | *Furosemide (Lasix), Hydrochlorothiazide* | Blunted natriuresis from high dietary sodium; licorice glycyrrhizin interaction. |
| **Potassium Binders** | *Patiromer (Veltassa), Lokelma* | Non-specific GI drug binding; must be separated by $\ge 2\text{--}3$ hours from other oral meds. |
| **Phosphate Binders** | *Sevelamer (Renvela), Calcium Acetate* | Luminal dietary phosphorus binding; must be taken with the first bites of meals. |

---

## Directory Structure

```
Latest_Update/
├── backend/
│   ├── chatbot/
│   │   ├── agent.py               # Hybrid ReAct agent with zero-downtime offline fallback
│   │   ├── eval_harness.py        # 30-turn automated clinical safety evaluation harness
│   │   ├── system_prompt.py       # Clinical safety-first guardrail prompt
│   │   └── tools.py               # Schema-bound tools with culinary synonyms & fuzzy search
│   ├── adaptation_engine.py       # Longitudinal meal deviation tracking & SQLite persistence
│   ├── agent_engine.py            # Multi-agent nutrition & wellness planner
│   ├── app.py                     # Modern FastAPI application with lifespan context manager
│   ├── db.py                      # Concurrency-safe SQLite WAL persistence & CRUD helpers
│   ├── feedback_learning.py       # Patient feedback & longitudinal outcome tracker
│   ├── medical_knowledge.py       # 18+ drug interactions, KDOQI, DASH, & ADA guidelines
│   ├── model_registry.py          # Model artifact loader & probability predictor
│   ├── raw_input.py               # Dynamic median imputation & feature mapping engine
│   ├── reporting.py               # Comorbidity food scoring & clinical narrative builder
│   ├── rules.py                   # Multi-tier threshold & comorbidity constraint solver
│   ├── safety_engine.py           # Safety boundary validator for nutrients & medications
│   └── schemas.py                 # Strict Pydantic v2 validation models
├── artifacts/
│   ├── ckd_model.joblib           # Calibrated HistGradientBoosting CKD model
│   ├── ckd_features.json          # Ordered feature manifest
│   ├── hypertension_model.joblib  # Calibrated HistGradientBoosting HTN model
│   ├── hypertension_features.json # Ordered feature manifest
│   ├── diabetes_model.joblib      # Calibrated HistGradientBoosting T2DM model
│   ├── diabetes_features.json     # Ordered feature manifest (with interaction features)
│   ├── population_medians.json    # Baseline population medians for dynamic imputation
│   ├── risk_thresholds_and_factors.json # Calibrated risk thresholds & factor profiles
│   └── nutrient_calibration_rules.json  # Multi-condition nutrient constraints
├── datasets/
│   ├── raw/                       # Original clinical datasets (UCI CKD, Framingham, Pima)
│   ├── preprocessed/              # Cleaned, imputed, scaled splits (train_smote & test)
│   └── unified_food_kb.csv        # Unified 7,110-item Indian & global nutrition dataset
├── scripts/
│   ├── preprocess_data.py         # Advanced feature engineering & dataset preprocessor
│   ├── train_and_optimize.py      # Cross-validated hyperparameter optimizer & calibration
│   ├── benchmark_models.py        # Comprehensive diagnostic benchmark report
│   ├── calibrate_nutrition.py     # Food knowledge base calibration generator
│   ├── predict_cli.py             # Interactive terminal wizard & JSON predictor
│   └── smoke_test.py              # Automated 21-endpoint & comorbidity test suite
├── demo_inputs/
│   ├── ckd_sample.json            # Sample clinical payload for CKD
│   ├── hypertension_sample.json   # Sample clinical payload for Hypertension
│   └── diabetes_sample.json       # Sample clinical payload for Diabetes
├── frontend.md                    # Frontend UI/UX, dashboard, & chart architecture spec
├── deployment.md                  # Docker Compose, CI/CD, & production deployment spec
├── requirements.txt               # Lean production dependencies
└── README.md                      # Comprehensive project documentation
```

---

## Quick Start Guide

### 1. Environment Setup
```powershell
# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install lean production requirements
pip install -r requirements.txt
```

### 2. Preprocess Data & Train Models (Optional - Artifacts Pre-built)
```powershell
python scripts/preprocess_data.py
python scripts/train_and_optimize.py
python scripts/benchmark_models.py
```

### 3. Start REST API Backend
```powershell
# Launch FastAPI server with multi-worker support
uvicorn backend.app:app --reload --workers 4
```
API Documentation will be live at:
- **Interactive Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc UI**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

### 4. Run Automated Smoke Test (21 Endpoints + Comorbidity Suite)
```powershell
python scripts/smoke_test.py
```

---

## Interactive CLI Tool

### Run Interactive Questionnaire Wizard
```powershell
python scripts/predict_cli.py --interactive
```

### Run Prediction from Demo JSON
```powershell
python scripts/predict_cli.py --raw-input demo_inputs/ckd_sample.json
python scripts/predict_cli.py --raw-input demo_inputs/hypertension_sample.json
python scripts/predict_cli.py --raw-input demo_inputs/diabetes_sample.json
```

---

## REST API Reference (21 Endpoints)

### Core Prediction & Health
| Method | Endpoint | Description |
|:---|:---|:---|
| `GET` | `/health` | Server status, loaded models, and active alerts |
| `GET` | `/implementation-progress` | Model benchmark metrics and summary |
| `GET` | `/raw-input-template/{disease}` | Questionnaire field template and defaults |
| `POST` | `/predict-risk` | Predict risk score from pre-scaled features |
| `POST` | `/predict-risk-raw` | Predict risk score from raw clinical answers (with dynamic imputation) |
| `POST` | `/risk-explanation-raw` | Clinical narrative explanation with top contributing factors |
| `POST` | `/risk-report` | Full diagnostic report with diet plan & food rankings |
| `POST` | `/risk-report-raw` | Full diagnostic report from raw questionnaire inputs |
| `POST` | `/recommend-plan` | Generate personalized single or comorbidity multi-disease diet plan |
| `POST` | `/log-meal` | Log meal consumption and compute calorie deviations |
| `GET` | `/risk-explanations` | Query historical risk explanation logs by user |

### Medical Safety & Guidelines
| Method | Endpoint | Description |
|:---|:---|:---|
| `GET` | `/medical/guidelines` | Evidence-based nutritional guidelines (KDOQI, ADA, DASH) |
| `GET` | `/medical/drug-interactions/{drug}` | Food/electrolyte interaction warnings for 18+ medications |
| `POST` | `/safety/validate` | Validate meal safety against patient comorbidity bounds and active drugs |

### Dynamic Adaptation & Outcomes
| Method | Endpoint | Description |
|:---|:---|:---|
| `POST` | `/adaptation/log-meal` | Track longitudinal meal adherence and persist adaptation actions |
| `GET` | `/adaptation/summary/{user_id}` | Retrieve patient deviation history and active adaptations |
| `POST` | `/feedback/submit` | Record patient subjective satisfaction and adherence in SQLite |
| `POST` | `/outcomes/record` | Record longitudinal biomarker trends (BP, HbA1c, eGFR, weight) |
| `GET` | `/learning/summary` | Global cohort outcome and adaptation efficacy metrics |

### AI Multi-Agent & Chatbot
| Method | Endpoint | Description |
|:---|:---|:---|
| `POST` | `/chatbot/chat` | Clinical safety-first chatbot with tool-calling and zero-downtime offline fallback |
| `POST` | `/agent/chat` | Multi-agent dietary goal planner and personalization engine |

---

## Database Persistence & Concurrency

The backend persists application state to `app_data.db` utilizing SQLite Write-Ahead Logging:
- **`PRAGMA journal_mode=WAL;`**: Permits concurrent readers and writers without database locking errors.
- **`PRAGMA busy_timeout=30000;`**: 30-second busy handler guaranteeing safe multi-worker scaling (`uvicorn --workers 4`).
- **Context Managers (`with get_db_conn() as conn:`)**: Guarantees automatic commit and connection teardown.

---

## Frontend & Deployment Documentation

- **Frontend & UI Specification**: See [frontend.md](file:///d:/College/Capstone/Sem_7/capstone_repo/frontend.md) for full dashboard component hierarchy, interactive Recharts/Chart.js layouts, multi-disease radar visualizations, and patient meal logging interfaces.
- **DevOps & Production Deployment**: See [deployment.md](file:///d:/College/Capstone/Sem_7/capstone_repo/deployment.md) for containerization specs (`Dockerfile`, `docker-compose.yml` with Ollama), GitHub Actions CI/CD pipelines, and Nginx reverse proxy configurations.

---

## Medical Disclaimer

> **IMPORTANT**: This software is intended solely for general wellness, academic research, and patient lifestyle education. It is not an FDA-cleared medical device, Software as a Medical Device (SaMD), or clinical diagnostic tool. Users should always consult a licensed physician or registered dietitian before initiating significant dietary modifications or altering medication regimens.
