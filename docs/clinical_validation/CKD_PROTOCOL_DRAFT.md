# CKD Intended-Use and Validation Protocol — Draft

**Status: DRAFT / NOT APPROVED.** This is a planning worksheet, not a clinical study protocol, regulatory determination, or authorization to access patient data. It is limited to the CKD branch. All open items require review by the responsible nephrologist, study investigator, biostatistician, data custodian, and ethics committee as applicable.

Last updated: 2026-09-28

## 1. Current evidence and scope

- The checked-in training code points to UCI Chronic Kidney Disease dataset ID 336, with a fallback to a local “expanded” CSV. The local workspace archive contains two 400-row, 25-column ARFF copies; both contain 248 `ckd`, 150 `notckd`, and two blank target labels, while the accompanying metadata claims 250/150. This count discrepancy is unresolved. The archive and expanded CSV are absent from the target branch; exact training cohort and counts after preprocessing remain unverified. See the [source inventory](DATA_SOURCE_INVENTORY.md).
- The checked-in model feature schema contains 28 fields: the original clinical fields plus engineered features. The feature list includes age, blood pressure, urine findings, serum creatinine, blood urea, electrolytes, hemoglobin/cell counts, hypertension, diabetes, and engineered ratios/interactions. The deployed raw-input mapper fills omitted features from medians or zero and emits warnings; those defaults need validation against the intended population.
- The preprocessor fits imputation, categorical encoding, and scaling before its random row split; the training script then cross-validates an already SMOTE-resampled training table. These operations can leak information across evaluation folds. The split is stratified by row and no patient/site identifier or group-aware split is evident in the checked-in feature list.
- The current CKD score path substitutes a hand-written eGFR/bio-marker heuristic for the raw model score. The synthetic probe showed the displayed result did not change when the raw model score changed from 0.01 to 0.99. The score must not be interpreted as a calibrated probability or used to set a clinical threshold.

## 2. Candidate research question — pending approval

**Candidate only:** In an independently sourced cohort, how well does a frozen CKD classifier distinguish a pre-specified CKD reference outcome at a defined index encounter, compared with a pre-specified baseline?

This is a concurrent classification question, not a prediction of future CKD or kidney failure. The candidate cannot be finalized until the model's training label, intended population, reference standard, and clinical decision are confirmed. No output will be shown to clinicians or patients during retrospective validation.

## 3. Intended-use fields to freeze

| Protocol item | Current status | Required decision/evidence |
|---|---|---|
| Intended user and care setting | **Open** | Specify who would use an output and where; or state that the work is research-only with no user-facing decision. |
| Target population and eligibility | **Open** | Specify age range, care setting, sites, relevant comorbidities, exclusions, and whether acute-care records are eligible. |
| Target outcome | **Open** | Verify exactly what the source label “CKD” means and whether the intended target is current CKD, future CKD, CKD progression, or kidney failure. These are different endpoints. |
| Index time and prediction horizon | **Open** | For current-condition classification, define the index encounter and label window. For a prognostic target, specify a future horizon and ensure all features precede it. |
| Reference standard | **Open** | Have nephrology and study leadership define adjudication independent of the model. For CKD, align the protocol with chronicity and GFR plus albuminuria assessment; eGFR category alone is insufficient to establish the full CKD classification. |
| Clinical action | **Open** | Define what action, if any, follows a positive or negative result and the consequences of false negatives/positives. Until then there is no clinically justified threshold. |
| Input timing and allowed features | **Open** | Record when each feature was measured relative to the index and reference outcome. Remove identifiers and any post-index or label-derived fields. Decide whether same-encounter diagnostic labs are appropriate for the chosen use. |
| Threshold and acceptance criteria | **Open** | A nephrologist and biostatistician must set sensitivity/specificity requirements and confidence-interval targets before unblinding validation results. Do not select a threshold on the external test cohort. |
| Governance and data access | **Open** | Identify the data controller, lawful access path, ethics review/waiver determination, consent/privacy requirements, and secure analysis environment before receiving human data. |

## 4. Proposed validation sequence

### Stage A — Source and label audit (no patient data collection)

1. Obtain the exact raw source files used by training, record source/license/citation and SHA-256 hashes, and reproduce row/column counts.
2. Reconcile UCI ID 336 with every “expanded” source. Document whether records were observed, duplicated, synthetically generated, or SMOTE-derived. Never treat synthetic rows as independent clinical validation subjects.
3. Confirm the label definition, cohort/site/time period, patient identifiers, repeated visits, missingness, and all feature timestamps. Investigate direct label leakage and near-target variables against the intended use.
4. Rebuild preprocessing so imputation, encoding, scaling, feature selection, resampling, calibration, and threshold choice are fit only within development folds. Keep every record from one patient in a single partition.
5. Do not claim performance from the existing checked-in model until its training data and pipeline can be reproduced.

### Stage B — Freeze model and protocol

1. Select and version the CKD model, preprocessing, feature map, code, and threshold before external evaluation.
2. Pre-register eligibility, index date, reference standard, missing-data handling, subgroup plan, sample-size rationale, statistical analysis, and acceptance/stopping criteria.
3. Keep threshold development/calibration data separate from the external validation cohort. Prefer a later time period and an independent site; report all cohort differences.

### Stage C — Retrospective external validation

Use only an appropriately governed independent cohort matching the frozen intended use. Apply the locked pipeline without tuning on validation labels. Report prevalence, flow/inclusion counts, missingness, and a confusion matrix. The primary metric should be sensitivity at the pre-specified action threshold with a 95% confidence interval if the intended purpose is to avoid missed cases; report specificity, PPV, NPV, ROC-AUC, and PR-AUC as secondary measures. If and only if the output is intended as a probability, also evaluate calibration (plot, slope/intercept, Brier score) and recalibration separately. Report subgroup results only with adequate sample sizes and uncertainty intervals.

The required sample size must be calculated from the desired precision of the primary estimate and expected prevalence; no arbitrary “large dataset” count or pass threshold is set in this draft.

### Stage D — Silent prospective evaluation

Only after the retrospective external evaluation and governance reviews support continuation, evaluate prospectively with outputs hidden from care teams and patients. Pre-specify monitoring and stop criteria. Do not let the prototype influence care during this stage.

### Stage E — Supervised impact evaluation and release review

Any later human-facing workflow study requires independent clinical, ethics, privacy, and regulatory review. Evaluate workflow harms and benefits before considering deployment. Passing software tests or retrospective discrimination metrics alone is not deployment approval.

## 5. Immediate blockers from this repository

- Raw/preprocessed CKD training and test cohorts are not checked in; exact provenance, labels, patient IDs, and counts cannot currently be verified.
- Existing preprocessing fits transforms before splitting, and the training script performs cross-validation on the SMOTE-resampled table. Rebuild the pipeline with patient/group separation and fold-local transforms/resampling.
- The CKD “calibration” is an unvalidated rules formula that ignores the fitted model score; current percentages and risk bands are not clinically interpretable probabilities.
- The UI calls eGFR ≥90 “healthy” and “KDIGO Stage 1.” Have nephrology review and replace this statement; GFR category alone does not establish CKD status or kidney health.
- Current treatment/action language has not been reviewed for evidence, context, or contraindications. Do not deliver it as individualized CKD advice.
- No external clinical cohort, approved protocol, or external validation results are attached.

## 6. Required sign-off before external cohort access

- Nephrologist / CKD clinician: intended use, reference standard, feature timing, threshold harms, and explanations.
- Study investigator and biostatistician: protocol, sample-size rationale, analysis plan, and acceptance criteria.
- Data custodian/privacy lead and relevant ethics committee: lawful access, privacy controls, consent or waiver, and oversight requirements.
- Regulatory specialist, if any intended use could constitute medical-device software: applicable classification and obligations.

## 7. Reporting references

- KDIGO 2024 CKD guideline: https://kdigo.org/guidelines/ckd-evaluation-and-management/
- UCI Chronic Kidney Disease dataset, ID 336: https://archive.ics.uci.edu/dataset/336/chronic%2Bkidney%2Bdisease
- ICMR National Ethical Guidelines handbook: https://www.icmr.gov.in/post/handbook-on-national-ethical-guidelines-for-biomedical-and-health-research-involving-human-participants-2018
- TRIPOD+AI reporting guidance: https://www.bmj.com/content/385/bmj-2023-078378

**Current decision:** research planning only. Do not use real patient data or present CKD outputs as validated for care.
