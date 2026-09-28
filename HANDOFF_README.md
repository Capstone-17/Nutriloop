# Project Handoff — Three-Disease Validation

- **Updated:** 2026-09-28
- **Repository branch:** `kevivt`
- **Last completed iterations:** CKD protocol draft (`b16d1ff`), three-disease audit and mapping fixes (`27747fa`), followed by the source-file inventory in this iteration
- **Current status:** Research planning and static source audit only; no model is clinically validated or approved for patient use.

## Completed latest iteration — metric provenance and software-claim correction

- Added [Metric Claim Audit](docs/clinical_validation/METRIC_CLAIM_AUDIT.md), including the old unverified profile values, why a numeric before/after comparison is invalid, and README/smoke-test claims corrected to match checked assertions.
- Removed historical metric fields from `artifacts/risk_thresholds_and_factors.json`; retained its runtime model/feature-factor configuration but marked evaluation and thresholds as unvalidated engineering defaults.
- Changed `/implementation-progress` metric reporting to read only the generated exploratory cross-validation JSON. It now returns 40 cohort/model rows with fold mean ± standard deviation, class-level metrics, aggregate confusion matrix, source hash, class distribution, split method, and an explicit non-clinical status; there is no fallback to the old metrics.
- Renamed/reframed the diet test as a synthetic software smoke check, corrected eGFR formula arithmetic to 49.3 for its example input, and removed the assertion that one result establishes CKD. This does not fix the live diet engine's single-measure CKD/HTN/diabetes condition inferences; those remain a clinical-safety blocker for the next disease-level implementation iteration.
- Verification: Python compile passed; API metric loader returned 40 rows and all included status/class/confusion fields; synthetic diet-engine smoke script passed. No training, patient data, clinical evaluation, or GUI model replacement occurred.
- Main limitation: exploratory metrics are not from the deployed model bundles. CKD/Framingham/Pima use row-level folds without record IDs, NHANES uses `SEQN` groups but no survey weights, and source lineage remains incomplete.

## Completed latest iteration — non-diagnostic disease flags

- Updated the weekly diet engine's user-visible output so CKD-range eGFR/biomarker findings, blood-pressure ranges, and diabetes-range laboratory values are explicitly described as non-diagnostic findings that require confirmation. A no-flag result now says it does not rule out disease.
- Updated the GUI condition heading and chatbot summary to say “Automated lab flags (not diagnoses)” and removed the misleading “None detected (Low Risk)” wording.
- Reframed generated diet notes as prototype meal-planning output, not a diagnosis or clinically validated nutrition prescription.
- Added synthetic regression assertions for single-measure flags and user-facing output; updated the CKD protocol with the KDIGO 2024 chronicity requirement and the remaining implementation issue.
- Critical remaining issue: the same single-reading booleans still select CKD/HTN/diabetes-specific nutrition targets internally. This iteration corrects wording only. Confirmed diagnoses are not separately collected, those targets are unvalidated, and patient use remains prohibited.
- Verification: Python compilation and `scripts/test_diet_accuracy.py` passed, including checks that single-value CKD/BP/diabetes outputs remain explicitly non-diagnostic and generated meal-plan notes carry the prototype disclaimer. No patient data or external clinical data used.

## Completed latest iteration — uncalibrated score display

- Changed all three GUI score cards to label outputs as research prototype signals; scores render as raw three-decimal values without percent signs or low/moderate/high bands.
- Detailed panels now show signal factors as unvalidated and suppress the old individualized action recommendations. API response schemas for risk predictions/reports document `risk_score_status=uncalibrated_research_prototype` and say threshold bands are engineering categories only.
- This is a presentation/API-contract safeguard. Model and heuristic score generation, disease-specific thresholds, and the legacy risk explanation content in other consumers remain unvalidated. No accuracy or clinical-performance claim follows from this change.
- Verification: JS syntax and Python schema compilation passed; API schema metadata checks confirmed the uncalibrated status/descriptions; synthetic diet and NHANES mapping regression checks passed. No patient data used.

## Goal and working rule

Work toward a defensible technical and clinical evaluation for CKD, hypertension, and type 2 diabetes. After each iteration, update the main README with a concise explanation and direct links, update this handoff with evidence/open decisions, and commit/push the finished iteration to `kevivt`.

## Completed protocol iteration

- Added [Hypertension Protocol Draft](docs/clinical_validation/HYPERTENSION_PROTOCOL_DRAFT.md) and [Type 2 Diabetes Protocol Draft](docs/clinical_validation/DIABETES_PROTOCOL_DRAFT.md), linked from the README.
- Both drafts distinguish current-disease classification from future-risk prediction and mark clinical target/reference-standard decisions as open.
- No patient data were accessed and no model was retrained in this documentation iteration.
## Completed this iteration

- Added [Three-Disease Pipeline Audit](docs/clinical_validation/THREE_DISEASE_PIPELINE_AUDIT.md) and linked it from the README.
- Confirmed the UCI CKD metadata describes a 400-row source dataset with 24 input fields, while the deployed CKD feature schema is 28 fields (24 source fields plus four engineered fields). The CKD protocol draft's earlier count of 29 was corrected.
- Fixed the hypertension mapping leak: use NHANES `BPQ050A` for `BPMeds` when present; otherwise leave missing. It no longer copies target `BPQ020`.
- Found incompatible outcome construction in the pooled hypertension and diabetes loaders: cohort-specific labels are concatenated under one target name without evidence that definitions are equivalent.
- Fixed the diabetes target mapping so NHANES borderline/nonresponse codes remain missing and are excluded by target-row `dropna`, rather than labeled negative.
- Confirmed shared evaluation defects in the checked-in code: imputers/scalers fit before splitting, cross-validation runs on the already SMOTE-resampled table, and calibration uses the resampled distribution. A later code change moved provisional threshold selection to training out-of-fold predictions; the split and resampling defects remain.
- Confirmed expected raw/preprocessed train/test files are absent from the target branch; a reproducible retraining or clinical performance result cannot be generated from this branch alone. Neither model was retrained after mapping fixes.

## Completed latest iteration — source inventory

- Added [Public Data Source Inventory](docs/clinical_validation/DATA_SOURCE_INVENTORY.md) and linked it from the README.
- Fingerprinted the CKD archive, Pima CSV, Framingham CSV, and NHANES merged extract present only in the shared development workspace. The document records dimensions and target counts for the three readable CSVs, variable/reference limitations, and explicit SHA-256 hashes.
- Confirmed NHANES `BPQ050A` is absent from the local merged file; after the prior mapping fix, `BPMeds` must remain missing for those rows. `SEQN` is unique within the merged file, but no cross-file linkage or patient-level split is established.
- Confirmed the three disease train/test CSVs and the derived BRFSS files are absent from the branch. No model was trained and no performance result was generated.
- Documented that synthetic oversampling cannot create independent patients or repair missing external validation data; preserve source prevalence and only oversample within development folds.
- Evidence remains a local source-file inventory plus code audit. Local files are not included in the branch and their redistribution licenses/source provenance are not yet established.

## Completed latest iteration — CKD archive contents

- Inspected the local CKD RAR archive read-only with the system `tar` utility; did not extract or modify the source file.
- Correction after parser verification: both ARFF members contain 400 physical data lines. Two have an extra empty trailing delimiter after a CKD label and are normalized without changing values. One other row has 26 populated fields for 25 declared attributes and is excluded as ambiguous. The 399 rows used by the benchmark contain 250 CKD and 149 non-CKD labels. The initial “two unlabeled rows” note was caused by the earlier parser and is superseded by the corrected inventory.
- Recorded separate SHA-256 hashes for the archive, both ARFF files, and metadata in the [Public Data Source Inventory](docs/clinical_validation/DATA_SOURCE_INVENTORY.md).
- The ARFF fields use `wbcc`/`rbcc`; the metadata uses `wc`/`rc`. This naming mismatch must be reconciled in a documented schema mapping.
- Updated the CKD protocol and pipeline audit with the discrepancy. No model was retrained and no metrics were produced.

## Completed latest iteration — missingness and label availability

- Added per-field local-source missingness counts for Framingham hypertension and Pima diabetes after applying the repository's documented zero-to-missing rule.
- Counted NHANES explicit binary-response rows separately from missing, refusal, and borderline rows: 6,151 hypertension and 8,709 diabetes rows in this unweighted extract. `BPQ050A` remains absent.
- Updated both disease protocols, the three-disease source audit, README, inventory, and validation log. No imputation, model retraining, or performance evaluation was run.
- These local-source counts do not establish representative population prevalence; source lineage and licensing remain unresolved, and the extracts are not in the branch.

## Completed latest iteration — fold-local exploratory cohort benchmark

- Added `scripts/evaluate_public_cohorts.py` and generated `reports/clinical_validation/exploratory_public_cohort_benchmark.json` directly from the inventoried local raw files.
- Evaluated UCI CKD, Framingham hypertension, Pima diabetes, and NHANES self-reported diabetes separately; labels were not pooled. Compared majority-class and plain logistic-regression baselines with balanced logistic regression, balanced random forest, histogram gradient boosting, Gaussian NB, RBF SVM, KNN, stacking, and XGBoost.
- Imputation, encoding, and scaling are fit within each training fold. No SMOTE/resampling, probability calibration, or threshold tuning is applied. Reports include fold metrics, mean ± standard deviation, per-class precision/recall/F1, sensitivity, specificity, PR-AUC, ROC-AUC, Brier score, confusion matrices, class counts, and exploratory paired Wilcoxon fold comparisons. The JSON records Python and library versions and source-file SHA-256 hashes.
- NHANES folds use `SEQN` grouping. CKD, Framingham, and Pima files have no record identifier, so stratified row folds are used and person-level independence is explicitly unverified. No survey weights are applied.
- Corrected CKD ARFF parsing: normalize only empty terminal delimiters; exclude the single row with one extra populated field. Both ARFF variants produce the same 399-row analysis cohort with 250 CKD / 149 non-CKD.
- Metrics use the fixed generic 0.5 cutoff; no clinically justified operating threshold or probability calibration is established. This is internal cross-validation on small public datasets, not independent or clinical validation. The older production training pipeline still has leakage defects and was not used to create this artifact.

## Completed latest iteration — threshold leakage reduction

- Changed `scripts/train_and_optimize.py` to generate out-of-fold probabilities on the training data, select the prototype macro-F1 threshold there, and evaluate the test split at that locked threshold. Test labels are no longer passed into threshold optimization.
- Deterministic synthetic OOF checks passed for all eight legacy candidate algorithms (including stacking and XGBoost), verifying one finite prediction per training row and valid derived thresholds. The two NHANES mapping regression checks also passed.
- This is a partial correction only: train inputs are still preprocessed before splitting and already SMOTE-resampled before model CV; calibration still uses those resampled rows. No checked-in train/test inputs were available, so no production model was retrained and no legacy metrics were regenerated. The derived threshold is an engineering threshold, not a clinician-approved operating point.

## Disease-level status

| Disease | Status | Main blockers |
|---|---|---|
| CKD | Protocol draft; target/outcome decision pending | Training files and label provenance absent; displayed score heuristic ignores classifier output; preprocessing/evaluation leakage. |
| Hypertension | Source mapping fix applied; retraining pending | Source labels differ; BRFSS-derived file absent; provided local merged NHANES extract lacks `BPQ050A`; raw inputs are absent from target branch. |
| Type 2 diabetes | Source mapping fix applied; retraining pending | Pima/NHANES/BRFSS labels differ; BRFSS-derived file absent; source-label mismatch and preprocessing/CV leakage remain. |

## Evidence and limits

Evidence consists of checked-in source inspection, the prior deterministic synthetic CKD behavior probe, and public dataset metadata. No independent clinical cohort, patient-level validation, external-site evaluation, prospective study, or clinician sign-off has been performed. Two focused `unittest` regression checks for NHANES mapping passed; `git diff --check` passed. Full preprocessing/training was not run because source cohorts are absent from this branch.

- [UCI CKD dataset metadata](https://archive.ics.uci.edu/dataset/336/chronic%2Bkidney%2Bdisease)
- [CDC NHANES 2017–2018 questionnaire variable list](https://wwwn.cdc.gov/nchs/nhanes/search/variablelist.aspx?Component=Questionnaire&Cycle=2017-2018)
- [CDC BRFSS 2023 data and documentation](https://www.cdc.gov/brfss/annual_data/annual_2023.html)
- [KDIGO 2024 CKD guideline](https://kdigo.org/guidelines/ckd-evaluation-and-management/)
- [TRIPOD+AI reporting guidance](https://www.bmj.com/content/385/bmj-2023-078378)
- [ICMR ethics guidance](https://www.icmr.gov.in/post/handbook-on-national-ethical-guidelines-for-biomedical-and-health-research-involving-human-participants-2018)

## Decisions still open

1. CKD target: current CKD status, future progression, kidney failure over a defined horizon, or research demo only?
2. Intended population, clinical setting, user, and action for each disease?
3. Independent reference standard, index date, feature timing, and exclusion criteria for each target?
4. Clinician/biostatistician-approved sensitivity, specificity, confidence-interval precision, and threshold acceptance criteria?
5. Source cohort, patient/site identifiers, dataset access, ethics/privacy review, and consent/waiver process?

The intended target/outcome choice is open for all three diseases. Freeze each separately before clinical evaluation. Do not use real patient data or claim future-risk performance while these items are unresolved.

## Next work

1. Establish provenance, license/terms, and reproducible acquisition for each locally inventoried source; fetch/join NHANES `BPQ050A` using `SEQN`.
2. Recover or reproducibly rebuild BRFSS source tables; inspect row counts, duplicates, synthetic augmentation, missingness, source/site/time fields, feature timing, and direct/indirect target leakage.
3. Rebuild the hypertension model with corrected `BPQ050A` mapping when available; otherwise retain the feature as missing and document fold-local imputation. Rebuild diabetes with borderline outcomes excluded.
4. Rebuild a pipeline with patient grouping and all imputers, encoders, scalers, resampling, calibration, and threshold selection confined to development folds. Select threshold on development data, never on the final external test set.
5. Freeze separate disease-specific protocols and models, then seek appropriately governed independent external cohorts.
6. Report disease-specific sensitivity with confidence intervals at a locked threshold, specificity, PPV/NPV, prevalence, PR-AUC, ROC-AUC, confusion matrices, and calibration only where probabilities are intended.
7. Move to silent prospective evaluation only if external validation and governance review support continuation.

## Current safety boundary

Synthetic examples and source-level engineering review only. Do not enter real patient data, use the displayed scores to guide care, or represent the prototype as clinically validated. The CKD score semantics and explanations, all three source-label definitions, training provenance, post-fix model refitting, and evaluation pipeline remain blocking items.
