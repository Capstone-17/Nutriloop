# Clinical Validation Log and Release Rules

**Status: NOT VALIDATED FOR CLINICAL USE.** This is the running record of validation checks, rules followed, findings, and unmet release gates for the desktop GUI bundled from `Capstone-17/6th_Sem`.

Last updated: 2026-09-28
Validation scope: source/code audit plus one deterministic synthetic-input probe. No human-subject or clinical-performance study has been conducted.

## System under review

- Desktop snapshot: repository root desktop app, audited source commit `cba57d92ea7271bed8789495be6739b212d4125b`.
- This review covers the desktop GUI risk pipeline, including its Python backend, SQLite data store, feature mappings, thresholds, rules, and model bundles. It does not establish validity of another model or API in this repository.
- Desktop environment used: Python 3.11.9, scikit-learn 1.7.2, NumPy 2.4.6, pandas 3.0.6.
- Model bundle hashes (SHA-256):
  - CKD: `0E78F4B4F9ECB17D6D27362F408E4A58D085E9F1C0F54E57C689C7FBD75464FB`
  - Hypertension: `199241D623D5B6C746A3945985CD83A1698FFAE01ECABCC9D472CF8CE02477D7`
  - Diabetes: `08B89FA711C2BCC0B76467807D1F840FF991B959DA0CA2A64B38454BBAEF082F`
- The tracked snapshot contains model bundles and training/benchmark scripts, but this review did not find an independent clinical validation report, a pre-registered protocol, or an external-site test result. Training-data lineage and exact reference-label definitions still need verification. The scripts require `datasets/preprocessed/{disease}_train_smote.csv` and `{disease}_test.csv`; that directory is absent from the bundled snapshot, so the reported benchmark/retraining protocol cannot currently be reproduced from the checked-in snapshot.

## Intended-use boundary for this stage

The only supported use at this stage is software development and demonstration with synthetic inputs. The outputs are not for diagnosis, screening decisions, treatment, nutrition prescriptions, or patient triage. Do not enter identifiable or real patient data. Do not use the score as a clinical probability unless its meaning, outcome, population, horizon, and calibration have been established and independently validated.

The exact eventual intended use is **unresolved**. Before a clinical study, the team must specify, per disease:

1. Target population and care setting, including country/site and eligibility criteria.
2. Intended user (clinician, dietitian, patient) and what decision or action the output is meant to inform.
3. Whether the target is prevalent disease, incident disease within a stated time horizon, or another endpoint.
4. The reference standard, index date, follow-up window, exclusions, and handling of indeterminate labels.
5. The clinical action and harms of false negatives and false positives that determine the operating threshold.

## Validations performed

| Check | Result | Evidence / limit |
|---|---|---|
| Upstream revision pinned | Pass | The audited source revision is the target branch parent `cba57d92ea7271bed8789495be6739b212d4125b`. |
| Desktop import and three model bundles load | Pass | Loaded as `CalibratedClassifierCV` under the isolated Python 3.11 / scikit-learn 1.7.2 environment. Load success does not prove predictive validity. |
| Desktop window starts | Pass | App process remained responsive and exposed a `Nutriloop` window title. No patient workflow or clinical output was approved by this check. |
| Synthetic risk-score behavior probe | **Fail / blocking finding** | `scripts/audit_desktop_clinical_rules.py` reproduced the screenshot's 5.3% CKD score for the displayed synthetic values. It was 0.053 with raw model scores of both 0.01 and 0.99. The CKD branch does not use `raw_score`. Hypertension changed from 0.022 to 0.99, and diabetes from 0.036 to 0.99, because those branches add hand-set adjustments to the raw score and clip it. This probe does not establish that those adjustments are empirically calibrated. See `reports/clinical_validation/synthetic_ckd_rule_probe.json`. |
| CKD explanation claim review | **Fail / blocking finding** | For synthetic eGFR 100, the UI text says “robust, healthy ... (KDIGO Stage 1).” KDIGO uses GFR and albuminuria together and requires chronicity for CKD; G1 is a GFR category and does not by itself establish CKD or establish kidney health. |
| Individualized action text review | **Not passed** | The low-risk CKD path emits hydration, sodium-intake, NSAID, and annual-test instructions. This code audit did not establish evidence, patient-specific appropriateness, or clinician approval for these recommendations. The source also maps serum sodium (mEq/L) into dietary-sodium advice (mg/day); these are distinct inputs and this mapping requires clinical review. |
| Clinical discrimination/calibration/utility | Not performed | No eligible independent clinical cohort, reference labels, or pre-specified protocol was evaluated. A classifier wrapper named `CalibratedClassifierCV` is not proof that the final score after additional hand-coded score adjustments is calibrated. |
| Subgroup/fairness, missingness, robustness, workflow and safety evaluation | Not performed | Requires defined intended population, adequate data, and a study protocol. |
| Human-subject prospective evaluation | Not performed / approval required | No real patients or patient records were used in this validation work. |

The synthetic probe can be reproduced from the repository root:

```powershell
python scripts\audit_desktop_clinical_rules.py
```

It is a deterministic source-behavior check only; it does **not** estimate sensitivity, specificity, predictive value, calibration, clinical benefit, or safety.

## Blocking findings to resolve before any real-patient evaluation

1. **Score provenance:** CKD risk calibration code ignores the fitted model score and substitutes an eGFR-based heuristic plus hand-set deltas. Hypertension and diabetes scores add hand-set deltas to their model scores and clip the result. None of these combined outputs has a demonstrated target horizon or empirical calibration in an independent intended-use population. Do not present the percentages as clinical probabilities.
2. **Clinical interpretation:** The G1 / “healthy kidney” output overstates what eGFR alone establishes. The explanation and labels require revision by a nephrologist against the current guideline and the model's actual intended target.
3. **Advice:** Personalized salt, fluid, medication, activity, retesting, and diet directions are not cleared for use. Build a source-and-context review table with a qualified clinician/dietitian for every advice template, including contraindications, uncertainty, and escalation language.
4. **Data lineage:** Establish training cohort provenance, inclusion/exclusion rules, outcome definitions, dates, feature construction, missing-data handling, and patient/site overlap for each model. Do not infer these from marketing claims in the upstream README.
5. **Potential evaluation leakage:** The checked-in training script reads pre-SMOTEd training CSVs and then runs stratified CV on those rows; it does not show fold-local resampling or a patient/group-aware split. Whether there is patient overlap cannot be decided without the missing source cohorts and IDs. Calibration is fitted using the SMOTE training distribution; this is not evidence of calibration at intended-use prevalence.
6. **Reproducibility:** Required preprocessed train/test CSVs are absent from the bundled snapshot, so the saved artifacts and advertised metrics cannot be independently regenerated from it.
7. **External evidence:** No independent validation cohort is currently attached to this desktop snapshot. Metrics from other cohorts, targets, or model pipelines are not interchangeable with this app's evidence.
8. **Regulatory and research governance:** Before collecting or processing real patient data for research, obtain institutional ethics committee review and follow the applicable consent/privacy process. Have Indian regulatory counsel determine whether the intended software function is regulated under CDSCO's current Medical Device Software guidance / Medical Devices Rules.

## Required validation sequence and release gates

### Gate 1 — Freeze intended use and protocol

Write and approve an intended-use statement for each model/output. Pre-register the analysis plan, reference standard, cohort and sites, sample-size rationale, missing-data rules, thresholds, subgroup analysis, and stopping/acceptance criteria before accessing the held-out cohort. A biostatistician should base sample size on precision of clinically important estimates, not an arbitrary large N.

### Gate 2 — Correctness and clinical content

- Trace each UI field through mapping, preprocessing, estimator, score adjustment, threshold, and displayed explanation.
- Verify units, ranges, transformations, missing-value behavior, and out-of-range handling.
- Remove or qualify claims that go beyond the observed inputs; include “unknown / insufficient data” paths and no-result/abstention behavior.
- Have disease-specific clinicians and dietitians review every statement and recommendation against cited, dated guidelines and patient-specific contraindications.
- Resolve CKD score/probability semantics and test correctness before performance evaluation.

### Gate 3 — Retrospective external validation

Use an independent, appropriately consented clinical cohort matching the frozen intended use. Keep all records for each patient within one partition; use a later time period and preferably a different site for external validation. Do not tune features, calibrators, or thresholds on the final test set. Compare with an appropriate baseline and usual clinical process.

Report per disease with confidence intervals: sensitivity, specificity, PPV, NPV, ROC-AUC, PR-AUC, calibration plot/slope/intercept, Brier score, confusion matrix, coverage/abstention, and decision-curve or other pre-specified clinical utility at the intended action threshold. Report prevalence because PPV/NPV depend on it. Assess performance and missingness across clinically relevant age, sex, site, and other justified population groups; avoid underpowered subgroup claims.

### Gate 4 — Silent prospective evaluation

Only after Gates 1–3 pass and approvals are obtained, collect the required data prospectively while hiding system output from care teams and patients. Compare it with the independently defined reference outcome. Do not let the tool alter care. Monitor data quality, missing fields, workflow failures, calibration, subgroup performance, and adverse-event signals against pre-specified stop criteria.

### Gate 5 — Supervised workflow and impact study

If silent-mode results justify proceeding, conduct an ethics-approved, clinician-supervised early workflow study. Measure usability, automation bias, overrides, alert burden, errors, delays, and safety events. Then use a suitably designed comparative impact study to determine whether using the tool improves care or patient outcomes without unacceptable harm. Early-stage human-in-the-loop evaluation should be reported using DECIDE-AI; prediction-model development/validation should be reported using TRIPOD+AI.

### Gate 6 — Regulatory, quality, and post-release controls

Before any deployment claim, resolve applicable CDSCO classification/licensing and institutional governance with qualified specialists. Establish controlled model/data versions, software risk management, security/privacy controls, user training, audit trail, incident reporting, ongoing performance/drift monitoring, update review, rollback, and a process to suspend the tool.

## Rules followed in this validation work

- Used only the synthetic values shown by the demo UI; no real patient records, credentials, or identifiers were collected or entered.
- Did not make clinical decisions, alter thresholds, retrain on a test cohort, claim accuracy, or infer clinical readiness from successful app startup/model loading.
- Kept conclusions limited to the audited desktop pipeline; no evidence was transferred from a different model or dataset.
- Preserved the pinned upstream revision and SHA-256 hashes of the three model bundles so later results can identify the exact tested artifacts.
- Reported the CKD score-invariance result as a blocking defect rather than hiding it or describing it as a passing performance validation.
- Used current primary guidance for CKD evaluation, India ethics/regulatory pathway, and AI study reporting; reporting checklists do not substitute for sound study design or regulatory review.
- Left the desktop app's current open window running. A visible “research prototype / synthetic data only” banner and synthetic demo label were added to the source; the already-open window must be restarted to display those UI changes.

## Guidance references

- KDIGO, *2024 Clinical Practice Guideline for the Evaluation and Management of CKD*: https://kdigo.org/guidelines/ckd-evaluation-and-management/
- CDSCO, Medical Device Software guidance under MDR-2017 (current listing; dated 2026-07-21): https://www.cdsco.gov.in/opencms/opencms/en/Medical-Device-Diagnostics/Medical-Device-Diagnostics/
- ICMR, *National Ethical Guidelines for Biomedical and Health Research Involving Human Participants*: https://www.icmr.gov.in/icmrobject/custom_data/pdf/resource-guidelines/ICMR_Ethical_Guidelines_2017.pdf
- DECIDE-AI, early-stage live evaluation of AI decision support: https://www.nature.com/articles/s41591-022-01772-9
- TRIPOD+AI, reporting clinical prediction model studies: https://www.bmj.com/content/385/bmj-2023-078378

## Current CKD validation focus

CKD was selected as the first disease to scope. A planning-only [CKD intended-use and validation protocol draft](CKD_PROTOCOL_DRAFT.md) records the source-code evidence, unresolved intended-use decisions, and proposed gated evaluation sequence. The target population, use, outcome, horizon, reference standard, and acceptance criteria remain unapproved; no external patient data should be accessed until these are frozen with clinical, statistical, data-governance, and ethics review.

## Three-disease pipeline review and mapping fixes

Static inspection identified a direct hypertension label leak (`NHANES BPQ020` copied into `BPMeds`) and a diabetes-label handling issue (NHANES borderline `DIQ010=3` mapped to negative). The preprocessing code now maps `BPMeds` only from CDC medication variable `BPQ050A` when available, otherwise leaves it missing; the diabetes label now maps only explicit yes/no codes, leaving borderline and nonresponse values missing for target-row exclusion. Two focused mapping regression tests passed. These source changes have not been used to retrain or reevaluate any disease model. Shared preprocessing-before-split, CV-after-SMOTE, and resampled calibration remain unresolved. The separate test-threshold selection defect was corrected in a later iteration and is recorded below. See [Three-Disease Pipeline Audit](THREE_DISEASE_PIPELINE_AUDIT.md).

## Hypertension and diabetes protocol focus

Draft intended-use worksheets were added for hypertension and type 2 diabetes. Both distinguish current-condition labels from future-risk outcomes, list the reference-standard and cohort decisions to freeze, and record the source-label and preprocessing blockers. They are planning documents only; no clinical target has been approved. See [Hypertension Protocol Draft](HYPERTENSION_PROTOCOL_DRAFT.md) and [Type 2 Diabetes Protocol Draft](DIABETES_PROTOCOL_DRAFT.md).
## Current decision

**Do not use this desktop app with real patient information or to guide care.** Continue only synthetic software checks and clinical-content review until the blocking findings are resolved. Gates 1–6 remain open; real-patient evaluation cannot begin until appropriate oversight, cohort access, protocol, and regulatory review are in place.


## Public data source inventory iteration

On 2026-09-28, a read-only inventory was made of four candidate public-source files in the shared development workspace: UCI-style CKD archive, Pima diabetes CSV, Framingham hypertension CSV, and a merged NHANES 2017–2018 extract. Their local-file SHA-256 hashes, row/column counts, available label counts, feature columns, and limitations are in the [Public Data Source Inventory](DATA_SOURCE_INVENTORY.md). None of these raw source files or the expected preprocessed train/test tables is included in the `kevivt` branch. The NHANES extract lacks `BPQ050A`; it includes one unique `SEQN` per row but that is not evidence of independent patient-level validation. No model was retrained and no accuracy/sensitivity/specificity claim was generated. Treat this as a provenance/readiness check only. Local-file provenance and redistribution terms remain unresolved, so do not present these local copies as a reproducible, licensed release dataset.


Initial CKD archive count (superseded): the first read-only parser reported 248 CKD, 150 non-CKD, and two blank targets. That count was wrong because it treated trailing empty delimiters after two valid CKD labels as extra blank class fields. The corrected source-row parser and benchmark below supersede that preliminary finding; no label was imputed. ARFF fields `wbcc`/`rbcc` differ from metadata names `wc`/`rc`; see the inventory and CKD protocol draft.


A follow-on data-readiness check quantified missing fields and eligible target counts in the locally available, untracked Framingham, Pima, and NHANES CSVs. Framingham has missing glucose in 388/4,240; Pima has missing insulin in 374/768 after the code's zero-to-missing conversion. The NHANES merged extract has 6,151 explicit binary hypertension responses and 8,709 explicit binary diabetes responses; excluded NHANES responses include missing/refusal/unknown and diabetes borderline values. No survey weighting was applied. See `DATA_SOURCE_INVENTORY.md` for details. These counts inform preprocessing planning only and are not clinical validation results.


## Exploratory cross-validation iteration and CKD parser correction

Added `scripts/evaluate_public_cohorts.py`, which runs five-fold source-specific stratified evaluation with a fixed seed. The local raw inputs generated `reports/clinical_validation/exploratory_public_cohort_benchmark.json`; it compares majority, plain and balanced logistic regression, balanced random forest, histogram gradient boosting, Gaussian NB, RBF SVM, KNN, a stacking ensemble, and XGBoost. Imputation/encoding/scaling are fold-local; no resampling, threshold selection, or calibration is performed. NHANES uses participant-ID grouped folds; the other sources have no ID, so their row-fold independence remains unverified. Metrics and fold confusion matrices are machine-generated in JSON.

The first CKD parser run incorrectly counted two valid CKD labels as blank because each data line had a trailing empty delimiter. The corrected parser removes that empty token only when it is the sole extra field. It excludes a different row with 26 populated values for 25 declared columns rather than guessing a repair. Both ARFF variants yield 399 analyzed records: 250 CKD and 149 not-CKD. Previous inventory/handoff wording implying 248 CKD and two unlabeled rows was wrong and is superseded. This correction is retained in the audit trail. The benchmark is exploratory and does not validate the desktop model or establish patient-use performance.


## Legacy trainer threshold leakage correction

Updated `scripts/train_and_optimize.py`: it now generates fixed-seed out-of-fold probabilities from the development training input, derives its provisional macro-F1 threshold from those predictions, and reports test metrics only after applying that locked threshold. A deterministic synthetic OOF check passed for all eight legacy candidate estimators, including stacking and XGBoost; it verified finite out-of-fold predictions for every synthetic development row. The two NHANES mapping regression tests passed again. This fixes direct threshold tuning on test labels only. The loaded `*_train_smote.csv` remains oversampled before fold assignment, and preprocessing was fit before split generation; calibrator fitting also uses the resampled distribution. The corrected legacy path is therefore still not an acceptable source of publishable performance metrics. No model was retrained because the preprocessed train/test files are absent from the branch.

## Metric provenance/API and diet smoke-test claim audit

On 2026-09-28, removed the unverified historical `metrics` objects from the active `artifacts/risk_thresholds_and_factors.json` profile. The runtime thresholds and feature-factor metadata remain, explicitly marked `NOT_CLINICALLY_VALIDATED` and `ENGINEERING_DEFAULTS_NOT_CLINICIAN_APPROVED`. The previous metrics are preserved only as quarantined historical numbers in `METRIC_CLAIM_AUDIT.md`; their source train/test inputs are absent and their evaluation used leaky preprocessing/resampling and test-based threshold selection, so no before/after delta is justified.

Changed `backend.app._read_project_model_metrics()` to read exclusively from `reports/clinical_validation/exploratory_public_cohort_benchmark.json`. A smoke invocation returned 40 rows (four source cohorts by ten algorithms); each row includes an explicit exploratory/non-clinical status, fold means and standard deviations, per-class results, aggregate confusion matrix, cohort counts, split metadata, and source hash. The endpoint no longer falls back to historical profile metrics. These data are public-cohort exploratory estimates and are not metrics of the bundled GUI models.

Audited checked-in quantified README claims and corrected calorie tolerance from ±0.5% to ±5%, removed unsupported zero-duplicate/allergen/Jain compliance claims, and narrowed statements to the assertions actually exercised. Reframed `scripts/test_diet_accuracy.py` as synthetic software smoke checks; the example eGFR arithmetic is 49.3 mL/min under the implemented equation and is not a CKD diagnosis. Python compilation passed, the API metric-loader assertions passed, and the synthetic diet smoke script passed. This does not address the live `derive_clinical_targets()` behavior that infers CKD/HTN/diabetes from individual measurements; this remains an unresolved safety blocker, along with the absence of clinician review and clinical validation.

## Non-diagnostic disease-flag wording iteration

KDIGO 2024 practice point 1.1.3.2 says not to infer chronicity from one abnormal eGFR/albumin result; chronicity requires evidence extending at least three months (practice point 1.1.3.1). Updated `backend/weekly_diet_engine.py` output labels so a one-time CKD-range eGFR/biomarker, BP range, or diabetes-range test is presented as a finding that does not establish diagnosis. No-flags wording now explicitly avoids reassurance that disease is absent. Updated the GUI heading and chatbot summary accordingly. Generated diet notes identify themselves as prototype output rather than a validated prescription.

Synthetic regression assertions confirm that the current example CKD/BP/glucose findings carry non-diagnostic wording and that generated diet notes include the prototype disclaimer. `py_compile` and `scripts/test_diet_accuracy.py` passed after the change. No patient data, clinical cohort, or human evaluation was used.

This is a wording safeguard only. `derive_clinical_targets()` still uses its single-value heuristic booleans internally to select CKD-, hypertension-, and diabetes-specific nutrient targets, and the app has no separate clinician-confirmed diagnosis field or chronicity evidence. Until that logic is redesigned and reviewed, output targets must not be used for individual care. Official reference: [KDIGO 2024 CKD guideline](https://kdigo.org/guidelines/ckd-evaluation-and-management/).

## Three-disease uncalibrated-score display iteration

Reviewed the GUI's disease-score flow for CKD, hypertension, and diabetes. It had multiplied the returned score by 100, printed a percent sign, assigned arbitrary low/moderate/high labels, and shown disease-specific recommendations. Updated the GUI to render a raw three-decimal prototype score as uncalibrated, remove risk bands/percentage semantics, label feature output as non-clinical, and replace individualized score-based actions with a research-only warning. Updated the API response schemas so `risk_score_status` is `uncalibrated_research_prototype`, the score is described as not a probability, and `risk_level` is described as an engineering threshold band.

Validation: JavaScript syntax check and Python compilation passed; schema inspection confirmed the status and descriptions; prior synthetic diet/mapping regressions continue to pass. No patient data or clinical cohort used.

Limits: this only corrects the primary GUI and response contract. The underlying CKD rules score is still not responsive to classifier probabilities in the prior synthetic probe, and other consumers of risk levels/explanations may still show categories or advice. Model weights, thresholds, class predictions, feature factors, and disease-specific recommendations remain unvalidated. Do not use for care.
