<div align="center">

<img src="Assets/Nutriloop_1.png" alt="NutriLoop Logo" width="360" style="margin-bottom: 16px;" />

# NutriLoop

### Precision Clinical Nutrition & Chronic Disease Management Platform

[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB?logo=python&logoColor=white)](https://python.org)
[![Desktop](https://img.shields.io/badge/Platform-Windows%20Standalone%20(.exe)-0078D6?logo=windows&logoColor=white)](https://microsoft.com)
[![Engine](https://img.shields.io/badge/UI-Edge%20WebView2%20%2B%20PyWebView-blue)](https://pywebview.flowrl.com)
[![Clinical Guidelines](https://img.shields.io/badge/Standards-KDIGO%20%7C%20ADA%202024%20%7C%20DASH-critical)](https://kdigo.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

<p align="center">
  <strong>NutriLoop</strong> is a local-first clinical decision support and personalized nutrition therapy platform. It combines calibrated machine-learning risk intelligence with culturally authentic medical nutrition therapy (MNT) to help patients and healthcare providers prevent and manage chronic diseases.
</p>

</div>

---

## 🌟 Overview

Managing chronic health conditions—such as **Chronic Kidney Disease (CKD)**, **Essential Hypertension**, and **Type 2 Diabetes**—requires continuous vigilance over biomarker metrics, diet composition, and medication interactions. Standard generic diet charts often conflict with medical restrictions or fail to respect cultural preferences.

**NutriLoop** bridges this gap by providing:
- **Instant Risk Intelligence**: Real-time slider monitors for patient biomarkers with multi-condition risk assessment.
- **7-Day Cultural Meal Planning**: Guideline-adherent 5-interval meal schedules crafted from 5 regional culinary traditions.
- **Strict Clinical Guardrails**: Automatic cross-referencing against 31+ medications, zero-tolerance allergen scrubbing, and dynamic portion scaling.
- **Interactive AI Consultation**: Dr. Nutriloop, an integrated conversational agent supporting both local offline LLMs and cloud providers.
- **100% Offline Standalone Executable**: A native Windows application running completely in-process with zero external server dependencies.

---

## 🚀 Key Features

### 1. Real-Time Telemetry & Risk Assessment
- **Slider-Controlled Health Monitors**: Effortlessly adjust clinical biomarkers—Blood Pressure (Systolic/Diastolic), Fasting Blood Glucose, HbA1c, Serum Creatinine, eGFR, Potassium, Sodium, and BMI—using responsive interactive gauges.
- **Multi-Disease Risk Engine**: Concurrently evaluates risk across Chronic Kidney Disease, Hypertension, and Type 2 Diabetes using calibrated machine learning models.
- **Personalized Clinical Explanations**: Clear, actionable breakdowns detailing positive health signals, primary risk drivers, and targeted dietary guidance.

### 2. 7-Day Regional Nutrition Engine
- **5 Authentic Culinary Traditions**:
  - **South Indian**: Steamed ragi idlis, multi-millet dosas, sambar, vegetable upma.
  - **North Indian**: Multigrain rotis, dal tadka, paneer bhurji, palak chana.
  - **Western Indian**: Gujarati & Maharashtrian jowar bhakris, dalia khichdi, kadhi.
  - **Eastern Indian**: Bengali & Odia cholar dal, potol posto, brown rice khichuri.
  - **Continental & Global**: Mediterranean grain bowls, whole wheat pasta marinara, lentil stews.
- **5 Structured Daily Intervals**: Breakfast, Mid-Morning Snack, Lunch, Evening Snack, and Dinner with balanced caloric distribution.
- **Dynamic Portion Scaling**: Automatically adjusts culinary portions to hit patient-specific caloric targets within ±3–5%.
- **Smart Craving Indulgence**: Safely budgets requested treats (e.g., biryani, kheer) on Sunday with 6-day metabolic lock and intra-day caloric rebalancing.
- **Smart Meal Variety**: Clicking "Generate" produces fresh, varied weekly schedules while strictly respecting all health rules and exclusions.

### 3. Medical Safety & Pharmacopeia Guardrails
- **31+ Drug-Nutrient Cross-Checks**: Automatically flags food-drug interactions for ACE inhibitors, ARBs, SGLT2 inhibitors, GLP-1 receptor agonists, statins, and diuretics.
- **Zero-Tolerance Scrubbing**: Instantly detects and eliminates user allergens and disliked ingredients across all meals.
- **Clinical Guideline Compliance**: Built strictly around KDIGO 2024, KDOQI 2020, ADA 2024, and ACC/AHA DASH clinical standards.

### 4. Dr. Nutriloop AI Clinical Assistant
- **Conversational Health Companion**: Chat naturally with Dr. Nutriloop to ask dietary questions, request meal swaps, or understand lab results.
- **Local & Cloud Model Support**: Run completely offline using local models (Ollama: Llama 3.2, Qwen 2.5) or connect to cloud APIs (Google Gemini, OpenAI).
- **Full Download Lifecycle**: In-app download management featuring Pause, Resume, and Cancel buttons with zero orphan background processes when the app closes.

### 5. Royal Glassmorphism Desktop Interface
- **Deep Maroon & Golden Yellow Palette**: Sleek dark aesthetic tailored for professional clinical workflows.
- **Ambient Looping Background**: Subtle 3-image watermark emblem gently cross-fading in the background while ensuring all foreground cards and text remain 100% visible and readable.
- **Local Data Privacy**: Patient records and consultation histories are stored locally in SQLite (`Nutriloop_Data/app_data.db`) without cloud syncing.

---

## 💻 Quick Start & Running

### Option A: Run the Standalone Application (Recommended)
You can launch NutriLoop directly without installing Python, Node.js, or any background servers:
1. Navigate to the `dist/` directory.
2. Double-click **`Nutriloop.exe`**.
3. The native desktop window will launch instantly with the custom icon and Edge WebView2 rendering.

### Option B: Run from Source
If running in a Python development environment:

```powershell
# 1. Clone or open the repository
cd d:\College\Capstone\Sem_7\Nutriloop

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch the desktop application
python app_desktop.py
```

---

## 📁 Project Architecture

```
Nutriloop/
├── Assets/                        # Project logos and application icons
│   ├── Nutriloop_1.ico            # Standalone face and window icon
│   ├── Nutriloop_1.png            # High-resolution brand logo
│   └── Nutriloop_2.png            # Secondary brand artwork
├── backend/                       # Core clinical intelligence engines
│   ├── weekly_diet_engine.py      # 7-Day regional nutrition generator
│   ├── safety_engine.py           # Medical constraints & pharmacopeia guardrails
│   ├── rules.py                   # Clinical explanation & staging rules
│   ├── model_registry.py          # Machine learning model loader
│   ├── ollama_manager.py          # Local model lifecycle (pause/resume/cancel)
│   ├── reporting.py               # Local report export (HTML / JSON)
│   ├── schemas.py                 # Pydantic validation models
│   └── db.py                      # Local SQLite database manager
├── gui/                           # Edge WebView2 desktop frontend
│   ├── index.html                 # Clean semantic single-page layout
│   ├── style.css                  # Royal glassmorphism styling & animations
│   ├── app.js                     # Bidirectional JavaScript-Python bridge
│   └── assets/                    # Bundled icons and imagery
├── artifacts/                     # Trained ML models (.joblib)
├── datasets/                      # Unified clinical food knowledge base
├── scripts/                       # Automated test and verification suites
│   ├── test_diet_accuracy.py      # Precision nutrient & variety test suite
│   ├── test_diet_preferences.py   # Preference responsiveness verification
│   └── test_model_download_control.py # Lifecycle & persistence verification
├── app_desktop.py                 # PyWebView standalone application entrypoint
├── Nutriloop.spec                 # PyInstaller standalone build configuration
└── README.md                      # Project documentation
```

---

## 🧪 Testing & Verification

All core clinical and system modules include automated verification suites:

```powershell
# Run diet recommendation accuracy and clinical limits test
python scripts/test_diet_accuracy.py

# Verify patient preference responsiveness and allergy scrubbing
python scripts/test_diet_preferences.py

# Test local model download controls (pause, resume, cancel, persistence)
python scripts/test_model_download_control.py
```

---

## 🛡️ Clinical Disclaimer

> **Notice**: NutriLoop is designed as a clinical decision support tool to assist healthcare professionals, dietitians, and individuals in meal planning and chronic disease education. It does not replace formal medical evaluation, diagnostic consultation, or prescription therapy from a licensed physician.

---

<div align="center">
  <small>Developed with ❤️ for precision clinical nutrition and patient wellness.</small>
</div>
