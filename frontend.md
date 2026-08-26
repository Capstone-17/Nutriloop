# Frontend & Interactive Visualization Architecture

This document outlines the proposed frontend applications, UI components, and visualization features for the Deep Learning and Generative AI-Driven Diet Recommendation System.

---

## 1. Overview & Objectives

The goal of the frontend layer is to translate the platform's 21 REST API endpoints and clinical engines into an intuitive, responsive, and aesthetically pleasing interface for two primary user personas:
1. **Patients**: Seeking chronic disease risk self-assessment, personalized disease-specific meal plans, live food search, and interactive chatbot assistance.
2. **Clinicians & Dietitians**: Reviewing patient risk stratification, longitudinal biomarker trends, meal adherence logs, and exporting clinical summary reports.

---

## 2. Core UI Modules & Features

### A. Interactive Clinical Risk Dial & Assessment
- **Real-Time Risk Gauge**: Visual speedometer/gauge dial rendering the predicted risk probability score ($0.0 \rightarrow 1.0$) with color-coded risk bands (`Low` $\le \text{Moderate Cutoff} \le \text{High Cutoff}$).
- **Interactive Questionnaire Wizard**: Step-by-step conversational wizard for raw patient inputs (Age, Sex, BP, Glucose, BMI, Smoking status) with instant client-side validation and tooltips.
- **Top Influential Factor Attribution**: Dynamic horizontal bar chart displaying top contributing clinical biomarkers (e.g., Hemoglobin for CKD, Systolic BP for HTN, Glucose/BMI for T2DM).

### B. Personalized Nutrition & Meal Plan Visualizer
- **Macronutrient & Calorie Distribution Cards**: Daily target cards for calories, protein, carbohydrates, and dietary fats with progress bars.
- **Electrolyte Safety Thresholds**: Visual limit indicators for daily Sodium ($\text{mg}$), Potassium ($\text{mg}$), Phosphorus ($\text{mg}$), and Added Sugars ($\text{g}$) with warning thresholds based on KDOQI, DASH, and ADA guidelines.
- **Dietary Focus Badges**: Highlighted clinical priorities (e.g., *"Aggressive Sodium Restriction"*, *"Low-Phosphorus Preference"*).

### C. Live Food Knowledge Base Explorer
- **Search & Multi-Filter Interface**: Fast search across the 7,110-item unified food database with category filters (Vegetables, Legumes, Cereals, Fruits, Dairy).
- **Medical Compliance Badges**: Instant color-coded badges (`Safe`, `Caution`, `Limit`) based on patient's risk level and active disease profile.
- **Interactive Nutritional Breakdown Drawer**: Side drawer displaying exact energy (kcal), protein (g), carbs (g), sodium (mg), potassium (mg), and phosphorus (mg) per 100g serving.

### D. Conversational Assistant & Chat Interface
- **Clinical Chat Interface**: Dedicated chat drawer/window interacting with the local Ollama LLM / Multi-Agent engine.
- **Grounded Tool-Call Transparency**: Visual indicator showing when risk profiles, diet plans, or food databases were referenced.
- **Safety Escalation Alerts**: Prominent clinical banners when medical symptoms or medication questions are redirected to supervising physicians.

### E. Longitudinal Adherence & Biomarker Tracker
- **Meal Log Timeline**: Visual log of planned vs. consumed calories with automated deviation severity tags (`Low`, `Moderate`, `High`).
- **Health Outcome Charts**: Longitudinal time-series graphs tracking systolic/diastolic blood pressure, fasting blood glucose, HbA1c, and weight changes.

### F. Clinical Report & PDF Export
- **One-Click Physician Summary**: Formatted printable diagnostic report compiling patient risk profile, factor importance, diet guidelines, and recent adherence statistics.

---

## 3. Technology Stack Recommendation

- **Framework**: Next.js / React or Lightweight Vanilla Modern Web UI (ES6+ Modules, Vanilla CSS Design System).
- **Visualization**: Chart.js / Recharts / D3 for risk dials and biomarker trend lines.
- **Design System**: Modern clean medical aesthetics, HSL color tokens, accessible typography (Inter / Roboto), glassmorphism cards, and responsive layout.
