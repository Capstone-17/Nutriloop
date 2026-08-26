# AI-Powered Clinical Risk Prediction & Personalized Medical Nutrition Engine

> **Production Release: `Latest_Update`**  
> A self-contained, enterprise-grade AI healthcare platform combining calibrated predictive risk models, guideline-based medical nutrition planning (KDOQI, ADA, DASH), continuous dietary adaptation, multi-agent goal planning, and a local clinical safety chatbot.

---

## Table of Contents

- [System Architecture](#system-architecture)
- [Model Performance Benchmark](#model-performance-benchmark)
- [Directory Structure](#directory-structure)
- [Quick Start Guide](#quick-start-guide)
- [Interactive CLI Tool](#interactive-cli-tool)
- [REST API Reference (21 Endpoints)](#rest-api-reference-21-endpoints)
- [Clinical Guidelines & Safety Guardrails](#clinical-guidelines--safety-guardrails)
- [License & Medical Disclaimer](#license--medical-disclaimer)

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
│  ├── Health & Diagnostics      ├── Risk Prediction (Direct & Raw)   ├── Nutrition & Diet Plans  │
│  ├── Multi-Agent Planner       ├── Safety & Boundary Validation     ├── Real-Time Adaptation    │
│  ├── Medical Knowledge Base    ├── Feedback & Outcomes Learning     └── Local Chatbot Agent     │
└───────────────┬───────────────────────────────────┬─────────────────────────────────┬───────────┘
                │                                   │                                 │
                ▼                                   ▼                                 ▼
┌───────────────────────────────┐   ┌───────────────────────────────┐   ┌─────────────────────────┐
│     Trained ML Models         │   │   Medical Knowledge & Rules   │   │  Food Knowledge Base    │
│  • CKD (HistGradientBoosting) │   │  • KDOQI (Renal Protocol)     │   │  • 7,110 Curated Items  │
│  • HTN (HistGradientBoosting) │   │  • ADA (Diabetes Protocol)    │   │  • 28 Standardized      │
│  • Diabetes (K-Nearest N.)    │   │  • DASH (Hypertension)        │   │    Nutrients & Micronut.│
│  • Calibrated Probabilities   │   │  • Drug-Nutrient Interactions │   │  • IFCT 2017 + OFF      │
└───────────────────────────────┘   └───────────────────────────────┘   └─────────────────────────┘
```

---

## Model Performance Benchmark

All models are trained with clinical feature engineering, SMOTE balancing on training splits only, probability calibration via `CalibratedClassifierCV`, and risk threshold optimization for maximum at-risk sensitivity.

| Clinical Condition | Model Family | Test Accuracy | Macro F1 | Recall (+) | Specificity | PR-AUC | ROC-AUC | Brier Score |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Chronic Kidney Disease (CKD)** | `HistGradientBoosting` | **98.75%** | **0.9868** | **98.00%** | **100.0%** | **0.9985** | **0.9973** | **0.0229** |
| **Hypertension (HTN)** | `HistGradientBoosting` | **89.50%** | **0.8823** | **91.25%** | **88.72%** | **0.8893** | **0.9523** | **0.0831** |
| **Type 2 Diabetes (T2DM)** | `KNeighbors (Distance)` | **70.78%** | **0.6919** | **68.52%** | **72.00%** | **0.6280** | **0.7692** | **0.1981** |

---

## Directory Structure

```
Latest_Update/
├── backend/
│   ├── chatbot/
│   │   ├── agent.py               # Deterministic tool-calling loop with local Ollama LLM
│   │   ├── eval_harness.py         # 30-turn automated evaluation harness
│   │   ├── system_prompt.py        # Clinical safety-first system prompt
│   │   └── tools.py                # Schema-bound tools for predictions & meal validation
│   ├── adaptation_engine.py        # Real-time meal deviation tracking & re-calibration
│   ├── agent_engine.py             # Multi-agent nutrition & wellness planner
│   ├── app.py                      # Production FastAPI application (21 endpoints)
│   ├── db.py                       # Thread-safe SQLite persistence layer
│   ├── feedback_learning.py        # Patient adherence & health outcome tracker
│   ├── medical_knowledge.py        # KDOQI, DASH, ADA clinical guidelines & drug interactions
│   ├── model_registry.py           # Model artifact loader & probability predictor
│   ├── raw_input.py                # Conversational questionnaire & feature mapping engine
│   ├── reporting.py                # Clinical explanation & risk narrative builder
│   ├── rules.py                    # Multi-tier threshold & meal plan generator
│   ├── safety_engine.py            # Safety boundary validator for electrolytes & nutrients
│   └── schemas.py                  # Strict Pydantic v2 validation models
├── artifacts/
│   ├── ckd_model.joblib            # Deployed calibrated CKD model
│   ├── ckd_features.json           # Ordered feature manifest
│   ├── hypertension_model.joblib   # Deployed calibrated Hypertension model
│   ├── hypertension_features.json  # Ordered feature manifest
│   ├── diabetes_model.joblib       # Deployed calibrated Diabetes model
│   ├── diabetes_features.json      # Ordered feature manifest
│   ├── risk_thresholds_and_factors.json # Tuned moderate/high cutoffs & feature weights
│   └── nutrient_calibration_rules.json  # Multi-condition nutrient constraints
├── datasets/
│   ├── raw/                        # Original clinical datasets (UCI CKD, Framingham, Pima)
│   ├── preprocessed/               # Cleaned, imputed, scaled splits (train_smote & test)
│   └── unified_food_kb.csv         # Unified 7,110-item Indian & global nutrition dataset
├── scripts/
│   ├── preprocess_data.py          # End-to-end dataset preprocessing pipeline
│   ├── train_and_optimize.py       # Cross-validated hyperparameter optimizer
│   ├── benchmark_models.py         # Comprehensive diagnostic benchmark report
│   ├── calibrate_nutrition.py      # Food knowledge base calibration generator
│   ├── predict_cli.py              # Interactive terminal wizard & JSON predictor
│   └── smoke_test.py               # Automated 21-endpoint test suite
├── demo_inputs/
│   ├── ckd_sample.json             # Sample clinical payload for CKD
│   ├── hypertension_sample.json    # Sample clinical payload for Hypertension
│   └── diabetes_sample.json        # Sample clinical payload for Diabetes
├── requirements.txt                # Lean production dependencies
└── README.md                       # Comprehensive documentation
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
# Launch FastAPI server with auto-reload
uvicorn backend.app:app --reload
```
API Documentation will be live at:
- **Interactive Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc UI**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

### 4. Run Automated Smoke Test (21 Endpoints)
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
| `POST` | `/predict-risk-raw` | Predict risk score from raw clinical answers |
| `POST` | `/risk-explanation-raw` | Clinical narrative explanation with top contributing factors |
| `POST` | `/risk-report` | Full diagnostic report with diet plan & food rankings |
| `POST` | `/risk-report-raw` | Full diagnostic report from raw questionnaire inputs |
| `POST` | `/recommend-plan` | Generate disease-specific macronutrient & calorie plan |
| `POST` | `/log-meal` | Log meal consumption and compute calorie deviations |
| `GET` | `/risk-explanations` | Query historical risk explanation logs by user |

### Medical Safety & Guidelines
| Method | Endpoint | Description |
|:---|:---|:---|
| `GET` | `/medical/guidelines` | Evidence-based nutritional guidelines (KDOQI, ADA, DASH) |
| `GET` | `/medical/drug-interactions/{drug}` | Food/electrolyte interaction warnings for medications |
| `POST` | `/safety/validate` | Validate meal safety against patient risk level and bounds |

### Dynamic Adaptation & Outcomes
| Method | Endpoint | Description |
|:---|:---|:---|
| `POST` | `/adaptation/log-meal` | Track longitudinal meal adherence and trigger adaptations |
| `GET` | `/adaptation/summary/{user_id}` | Retrieve patient deviation history and active adaptations |
| `POST` | `/feedback/submit` | Record patient subjective satisfaction and adherence |
| `POST` | `/outcomes/record` | Record longitudinal biomarker trends (BP, HbA1c, eGFR) |
| `GET` | `/learning/summary` | Global cohort outcome and adaptation efficacy metrics |

### AI Multi-Agent & Chatbot
| Method | Endpoint | Description |
|:---|:---|:---|
| `POST` | `/chatbot/chat` | Clinical safety-first chatbot agent with Ollama tool calling |
| `POST` | `/agent/chat` | Multi-agent dietary goal planner and personalization engine |

---

## Clinical Guidelines & Safety Guardrails

- **CKD (KDOQI Guidelines)**: Imposes strict potassium ($<2,000$ mg/day), sodium ($<2,000$ mg/day), and phosphorus limits ($<1,000$ mg/day) with controlled protein ($0.6\text{–}0.8$ g/kg/day).
- **Hypertension (DASH Protocol)**: Enforces sodium restriction ($<1,500$ mg/day) with elevated potassium ($>3,500$ mg/day) and high dietary fiber ($>30$ g/day).
- **Type 2 Diabetes (ADA Protocol)**: Regulates free sugars ($<25$ g/day) and carbohydrate distribution ($<45\%$ of total calories) with high fiber ($>30$ g/day).
- **Drug-Food Interactions**: Detects critical contraindications (e.g. ACE Inhibitors like Lisinopril + High Potassium foods $\rightarrow$ Hyperkalemia alert).

---

## Medical Disclaimer

> **IMPORTANT**: This software is intended solely for general wellness, academic research, and patient lifestyle education. It is not an FDA-cleared medical device, Software as a Medical Device (SaMD), or clinical diagnostic tool. Users should always consult a licensed physician or registered dietitian before initiating significant dietary modifications or altering medication regimens.
