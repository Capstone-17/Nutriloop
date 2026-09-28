# Project Handoff — Three-Disease Validation

- **Updated:** 2026-09-28
- **Repository branch:** `kevivt`
- **Last completed iterations:** CKD protocol draft (`b16d1ff`), three-disease audit and mapping fixes (`27747fa`), followed by the source-file inventory in this iteration
- **Current status:** Research planning and static source audit only; no model is clinically validated or approved for patient use.

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
- Confirmed shared evaluation defects in the checked-in code: imputers/scalers fit before splitting, cross-validation runs on the already SMOTE-resampled table, calibration uses the resampled distribution, and the “best” threshold is selected on held-out test labels.
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
- Both ARFF members contain 400 records and 25 columns (24 features plus `class`): 248 labeled CKD, 150 labeled not-CKD, and two blank target labels. The accompanying info file reports 250 CKD and 150 not-CKD. The two unlabeled rows remain unknown and must not be silently assigned.
- Recorded separate SHA-256 hashes for the archive, both ARFF files, and metadata in the [Public Data Source Inventory](docs/clinical_validation/DATA_SOURCE_INVENTORY.md).
- The ARFF fields use `wbcc`/`rbcc`; the metadata uses `wc`/`rc`. This naming mismatch must be reconciled in a documented schema mapping.
- Updated the CKD protocol and pipeline audit with the discrepancy. No model was retrained and no metrics were produced.

## Completed latest iteration — missingness and label availability

- Added per-field local-source missingness counts for Framingham hypertension and Pima diabetes after applying the repository's documented zero-to-missing rule.
- Counted NHANES explicit binary-response rows separately from missing, refusal, and borderline rows: 6,151 hypertension and 8,709 diabetes rows in this unweighted extract. `BPQ050A` remains absent.
- Updated both disease protocols, the three-disease source audit, README, inventory, and validation log. No imputation, model retraining, or performance evaluation was run.
- These local-source counts do not establish representative population prevalence; source lineage and licensing remain unresolved, and the extracts are not in the branch.

## Disease-level status

| Disease | Status | Main blockers |
|---|---|---|
| CKD | Protocol draft; target/outcome decision pending | Training files and label provenance absent; displayed score heuristic ignores classifier output; preprocessing/evaluation leakage. |
| Hypertension | Source mapping fix applied; retraining pending | Source labels differ; BRFSS-derived file absent; threshold tuned on test; provided local merged NHANES extract lacks `BPQ050A`; raw inputs are absent from target branch. |
| Type 2 diabetes | Source mapping fix applied; retraining pending | Pima/NHANES/BRFSS labels differ; BRFSS-derived file absent; threshold tuned on test. |

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

1. Establish provenance, license/terms, and reproducible acquisition for each locally inventoried source; inspect/extract CKD archive and fetch/join NHANES `BPQ050A` using `SEQN`.
2. Recover or reproducibly rebuild BRFSS source tables; inspect row counts, duplicates, synthetic augmentation, missingness, source/site/time fields, feature timing, and direct/indirect target leakage.
3. Rebuild the hypertension model with corrected `BPQ050A` mapping when available; otherwise retain the feature as missing and document fold-local imputation. Rebuild diabetes with borderline outcomes excluded.
4. Rebuild a pipeline with patient grouping and all imputers, encoders, scalers, resampling, calibration, and threshold selection confined to development folds. Select threshold on development data, never on the final external test set.
5. Freeze separate disease-specific protocols and models, then seek appropriately governed independent external cohorts.
6. Report disease-specific sensitivity with confidence intervals at a locked threshold, specificity, PPV/NPV, prevalence, PR-AUC, ROC-AUC, confusion matrices, and calibration only where probabilities are intended.
7. Move to silent prospective evaluation only if external validation and governance review support continuation.

## Current safety boundary

Synthetic examples and source-level engineering review only. Do not enter real patient data, use the displayed scores to guide care, or represent the prototype as clinically validated. The CKD score semantics and explanations, all three source-label definitions, training provenance, post-fix model refitting, and evaluation pipeline remain blocking items.
