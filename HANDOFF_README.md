# Project Handoff — CKD Validation

- **Updated:** 2026-09-28
- **Repository branch:** `kevivt`
- **Last completed iteration:** CKD protocol draft, commit `b16d1ff` (parent iteration `f9abf61`)
- **Current status:** Research planning only; not clinically validated and not approved for patient use.

## Goal and working rule

Work toward a defensible CKD evaluation while treating clinical safety, data governance, and reproducibility as core engineering requirements. After each iteration, update the main README with a short explanation and direct links, update this handoff with evidence and open decisions, then commit/push the finished iteration to `kevivt`.

## Completed in this iteration

- Selected CKD as the first disease branch to scope.
- Added [CKD Intended-Use and Validation Protocol — Draft](docs/clinical_validation/CKD_PROTOCOL_DRAFT.md).
- Updated the [clinical validation log](docs/clinical_validation/VALIDATION_LOG.md) and the README to link the CKD draft.
- Confirmed the checked-in pipeline references UCI CKD dataset ID 336 and an optional local expanded file. The repository branch does not contain the raw CKD files or expected preprocessed train/test CSVs.
- The UCI source describes 400 records, 24 input features, missing values, and `ckd` / `notckd` labels. The checked-in model schema has 29 fields after feature engineering. The use and provenance of any expanded data remain unverified.
- Source review found preprocessing transforms fitted before row splitting, followed by CV on an already SMOTE-resampled training table. Patient/site identifiers and group separation are not evident in the checked-in feature schema.
- The previous synthetic probe found the CKD rule score ignored changes in the raw classifier score; therefore its displayed percentage is not established as a calibrated probability.

## Evidence and limits

Evidence currently consists of source inspection, the deterministic synthetic behavior probe, and metadata/code present in this branch. No independent clinical cohort, patient-level validation, external-site evaluation, prospective study, or clinician sign-off has been performed. No automated tests were run for this documentation-only iteration; whitespace checks passed.

- [UCI CKD dataset metadata](https://archive.ics.uci.edu/dataset/336/chronic%2Bkidney%2Bdisease)
- [KDIGO 2024 CKD guideline](https://kdigo.org/guidelines/ckd-evaluation-and-management/)
- [TRIPOD+AI reporting guidance](https://www.bmj.com/content/385/bmj-2023-078378)
- [ICMR ethics guidance](https://www.icmr.gov.in/post/handbook-on-national-ethical-guidelines-for-biomedical-and-health-research-involving-human-participants-2018)

## Decisions still open

1. What is the model's target: current CKD status at an encounter, future CKD progression, kidney failure by a defined horizon, or research demonstration only?
2. What intended population, care setting, and user should the eventual evaluation represent?
3. What independent reference standard, index date, and feature timing will define the outcome?
4. What sensitivity and specificity requirements, confidence-interval precision, and action threshold will the nephrologist and biostatistician set before evaluation?
5. What data owner, ethics review, privacy controls, and consent/waiver process will govern any human-data study?

The target/outcome choice is the immediate dependency. Until it is set, do not describe this model as predicting future risk and do not tune its threshold against a clinical dataset.

## Next work after the target is chosen

1. Trace the exact training label and reconcile UCI ID 336 with the missing expanded data; obtain versioned raw files, provenance, licenses, counts, IDs, dates, and hashes.
2. Check duplicates, synthetic augmentation, feature timing, missingness, near-target features, and patient/site overlap.
3. Rebuild a reproducible pipeline with transforms, calibration, resampling, and threshold selection fitted only inside development folds; keep patients grouped across partitions.
4. Freeze an approved protocol and model before evaluation on a properly governed independent cohort.
5. Report sensitivity at the pre-specified threshold with confidence intervals, plus specificity, PPV/NPV, prevalence, ROC-AUC, PR-AUC, calibration when probabilities are intended, missingness, subgroup performance, and confusion matrix.
6. Proceed to silent prospective evaluation only if retrospective external validation and governance review support continuation.

## Current safety boundary

Synthetic data and source-level engineering review only. Do not enter real patient data, use the displayed score to guide care, or represent the prototype as clinically validated. The CKD score semantics, “healthy / KDIGO Stage 1” wording, individualized advice, training provenance, and evaluation pipeline remain blocking items.
