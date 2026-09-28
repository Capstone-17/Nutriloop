# Three-Disease Pipeline Audit — Source and Evaluation Readiness

**Status: static source audit only.** No clinical performance validation is reported here. This audit covers the checked-in preprocessing/training code and model feature schemas for CKD, hypertension, and type 2 diabetes.

Last updated: 2026-09-28

## Readiness summary

| Model | Declared training sources / target in code | Main validity blockers | Current status |
|---|---|---|---|---|
| CKD | UCI CKD dataset 336 (fallback), local ARFF/CSV, or an “expanded” CSV; target `class` mapped to CKD/not-CKD | Data files absent from target branch; possible same-encounter label/feature circularity; transforms are fit before split; CV happens after SMOTE; displayed rule score ignores classifier probability | Not reproducible / not clinically validated |
| Hypertension | Framingham `prevalentHyp`, NHANES self-report `BPQ020`, and an unavailable BRFSS-derived table also called `prevalentHyp` | Direct label copy to `BPMeds` patched in source; definitions still differ by source; BRFSS prevalence altered; test set used to tune threshold | Mapping fix not yet retrained; other blockers remain |
| Type 2 diabetes | Pima `Outcome`, NHANES self-report `DIQ010`, and an unavailable BRFSS-derived `diabetes` label | Outcome definitions differ; NHANES borderline responses are now left missing/excluded from the binary target; current diagnostic glucose is included among predictors for Pima; prevalence altered in BRFSS sampling; test set used to tune threshold | Label mapping corrected, model not retrained; target semantics and evaluation leakage remain |

## CKD

### What the code currently does

- `scripts/preprocess_data.py` checks local `datasets/raw/chronic+kidney+disease` ARFF/CSV paths, then a `med_dataset` expanded CSV, and finally fetches UCI repository dataset ID 336.
- It maps `class` values `ckd`/`notckd` to a binary target. UCI describes 400 instances, 24 predictors, missing values, and a class field.
- The model schema contains 28 inputs: those clinical/source fields plus four engineered features (`BP_ratio`, `pulse_pressure`, `glucose_diabetes`, `creatinine_urea_ratio`).
- KNN/most-frequent imputers, label encoders, and MinMax scaling are fitted before the random stratified row split. SMOTE is applied to training rows, then `train_and_optimize.py` cross-validates the already-resampled table.

### What is still unknown or unsafe to claim

- The “expanded” file and the actual training/test tables are absent from the target branch. The training population and any additional or synthetic rows cannot be confirmed.
- There is no patient/site identifier in the feature schema; whether source files contain repeated patients or multiple sites cannot be determined from this branch.
- Clinical labs used as features may be appropriate for a concurrent diagnostic classification only if feature timing and independent reference labels are specified. They do not support a future-risk claim without a separate prediction horizon and pre-index feature definition.
- The current UI score path uses an unvalidated hand-coded heuristic instead of the model probability. The existing synthetic probe confirmed score invariance to raw classifier values 0.01 and 0.99.

## Hypertension

### What the code currently does

- It appends Framingham rows, mapped NHANES 2017–2018 rows, and rows from an unavailable `hypertension_large_500k.csv`.
- Framingham uses `prevalentHyp` as target. NHANES uses `BPQ020`, the question “ever told by a doctor or other health professional ... hypertension,” as target. BRFSS target provenance/derivation cannot be audited because that file is absent.
- The original mapping copied target `BPQ020` into feature `BPMeds`, making the target trivially available for NHANES rows. This iteration changes the source mapping to the actual `BPQ050A` medication question when present, and otherwise leaves the feature missing; it never falls back to the target. The local merged CSV does not contain `BPQ050A`, so downstream imputation and refitting are still required. The mapping fix alone does not validate the model.
- The BRFSS-derived source retains all negatives and samples at most 20,000 positives. This changes its natural prevalence; unweighted pooled model probabilities, PPV/NPV, and threshold selection do not represent the source population.
- The merged table is imputed and scaled before its stratified random row split. No source-specific held-out set, patient grouping, or survey-design weighting is shown.

### What is still unknown or unsafe to claim

- `prevalentHyp` does not have a verified common definition across the three sources. Source rows are concatenated without a durable source label in the final feature schema.
- NHANES label is self-reported prior diagnosis while Framingham and BRFSS fields have separate construction histories. A common binary column does not prove a common outcome.
- Same-encounter measured BP may be a diagnostic input, but performance must be tied to an independent, pre-specified reference standard and intended use.

## Type 2 diabetes

### What the code currently does

- It appends Pima rows (`Outcome`), mapped NHANES 2017–2018 rows, and rows from an unavailable `diabetes_large_500k.csv`.
- NHANES uses `DIQ010` (ever told by a doctor/health professional the respondent had diabetes); code 1 maps positive, code 2 negative, and borderline/nonresponse values remain missing. Rows missing the binary target are excluded by the existing target `dropna` step.
- Pima preprocessing turns zeros in glucose, blood pressure, skin thickness, insulin, and BMI into missing values. The model feature schema still includes glucose and multiple glucose-derived interactions, so a current-disease classification may be closely tied to diagnostic measurements used to establish its source label. This needs a defined target/reference standard; it is not a future-onset model as currently documented.
- The BRFSS-derived source retains all negatives and samples up to 20,000 positives, altering the natural prevalence before it is concatenated with other cohorts.
- Median imputation and scaling are fitted before the stratified row split; no survey weights, source-specific evaluation, or patient group split is shown.

### What is still unknown or unsafe to claim

- `Outcome`, NHANES self-report, and the missing BRFSS label are not shown to represent the same case definition. Borderline NHANES answers should be handled as a distinct/indeterminate category or by a pre-specified clinical rule, not silently labeled negative.
- The checked-in branch lacks the Pima, NHANES merged, and BRFSS-derived source files at the paths the script expects. The actual cohort sizes and label distributions cannot be reproduced from this branch.

## Shared training/evaluation defects

- The training entry point reads `{disease}_train_smote.csv` and `{disease}_test.csv`; these files are absent from the branch.
- Candidate cross-validation is run on the SMOTE-resampled training table. Synthetic neighbors can therefore be split between a fold's training and validation portions.
- `CalibratedClassifierCV` is fit using the resampled training distribution; this alone does not establish probability calibration for the source or intended-use prevalence.
- `optimize_thresholds(y_test, y_test_probs)` selects the “best” threshold on the held-out test labels. The same test split is then used to report the resulting metrics. Those test results are no longer an unbiased evaluation at a locked threshold.
- The preprocessing functions fit imputers and scalers on the full combined table before splitting. All data-dependent transforms must be fit inside each training fold.
- Random row splits do not establish patient-level independence, source independence, temporal separation, or protection from repeated records.
- Threshold selection by macro-F1 does not encode the harms of a missed diagnosis. Clinical operating points must be set before final validation by the clinical team and statistician.

## Required engineering remediation before any performance claim

1. Recover and checksum the precise raw files and labels used for each saved model; include source/version metadata and row counts.
2. Preserve source and patient/site/time identifiers outside model features so cohort harmonization, grouping, and leakage checks are possible.
3. Define a separate, clinically meaningful outcome and reference standard for each disease. Do not combine source labels until equivalence is justified.
4. Split by patient, and hold out source/site or later time periods for external evaluation. Fit imputation, encoding, scaling, feature selection, resampling, and calibration only within development folds.
5. Move threshold selection to development data; freeze model and threshold before evaluating held-out external data.
6. Re-evaluate calibration on the target prevalence if probabilities are intended. Report disease-specific prevalence, sensitivity with confidence intervals, specificity, PPV/NPV, PR-AUC, ROC-AUC, Brier/calibration results where appropriate, confusion matrices, and subgroup uncertainty.
7. The direct `BPMeds = BPQ020` leak is fixed in source. Rebuild and re-audit the fitted hypertension model; map `BPMeds` only from verified `BPQ050A` when present, otherwise keep it missing. Audit remaining features against label source, timing, and deployment availability.

## Sources

- UCI CKD dataset 336 metadata: https://archive.ics.uci.edu/dataset/336/chronic%2Bkidney%2Bdisease
- CDC NHANES 2017–2018 BPQ_J codebook, including the correct `BPQ050A` medication field: https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/BPQ_J.htm
- CDC NHANES 2017–2018 variable list (includes BPQ020 and DIQ010 definitions): https://wwwn.cdc.gov/nchs/nhanes/search/variablelist.aspx?Component=Questionnaire&Cycle=2017-2018
- CDC BRFSS 2023 survey data and documentation: https://www.cdc.gov/brfss/annual_data/annual_2023.html
- TRIPOD+AI reporting guidance: https://www.bmj.com/content/385/bmj-2023-078378

## Decision

**No disease is clinically validated for patient use.** This iteration patches the direct hypertension label leak and prevents NHANES borderline diabetes responses from being silently labeled negative. The fitted models have not been retrained or reevaluated after these changes. Source-label incompatibility and shared evaluation leakage remain; resolve those before independent external validation.
