# Hypertension Intended-Use and Validation Protocol — Draft

**Status: DRAFT / NOT APPROVED.** Planning worksheet only. No clinical study, external validation, or authorization to access patient data has been performed.

Last updated: 2026-09-28

## Evidence from the checked-in pipeline

- Training code pools Framingham `prevalentHyp`, NHANES 2017–2018 `BPQ020`, and an unavailable BRFSS-derived `hypertension_large_500k.csv` target. The raw cohort files and preprocessed train/test tables are absent from this branch.
- NHANES `BPQ020` asks whether a health professional ever told the participant they had hypertension. It is a self-reported history label, not the same as standardized measurement of current blood pressure. [CDC NHANES BPQ_J codebook](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/BPQ_J.htm)
- The prototype's weekly-plan output now calls a single elevated BP value a range flag and explicitly says one reading does not establish diagnosis. This is a wording safeguard; the same heuristic still changes internal meal targets, and the model's diagnostic status/measurement protocol has not been clinically validated.
- The GUI now displays the hypertension model output as an uncalibrated score with no probability or low/moderate/high category claim; the API schema marks it as research prototype output. The score and thresholds remain unvalidated.
- The previous code copied the NHANES target into `BPMeds`. The mapping now uses medication item `BPQ050A` when available; if unavailable it stays missing. The local merged file observed during audit lacks `BPQ050A`, and the target branch does not include that raw extract. The model has not been refit after this correction.
- The code pools cohort labels, fits imputation/scaling before the row split, changes prevalence in BRFSS sampling, The legacy trainer now selects its provisional threshold on training out-of-fold predictions. Pre-split imputation/scaling, CV on SMOTE-resampled rows, and calibration on that resampled distribution remain unresolved.
- In the inspected local Framingham CSV (not tracked in this branch), there are 4,240 rows with 1,317 positive and 2,923 negative `prevalentHyp` labels. Missing values include glucose in 388 rows, education in 105, BP medication in 53, and total cholesterol in 50. In the local NHANES extract, 6,151/9,254 rows have explicit `BPQ020` yes/no responses; 3,103 nonresponse/missing rows are excluded, and the required `BPQ050A` medication field is absent. Counts and file hashes are recorded in the [source inventory](DATA_SOURCE_INVENTORY.md); these are development-source counts, not performance validation or a weighted population estimate.
- The [generated exploratory benchmark](../../reports/clinical_validation/exploratory_public_cohort_benchmark.json) evaluates only the Framingham source for this disease using fold-local processing. Its fixed-cutoff cross-validation estimates are not independent-site validation, do not define a clinical threshold, and do not establish that contemporaneous BP predictors are independent of target construction.

## Candidate question — pending approval

**Candidate only:** How well does a frozen model classify a pre-specified current hypertension outcome in a defined cohort at a defined index time, using only information available for the intended user at that time?

This candidate is not a future-onset model. Choose one target: (1) prior clinician-diagnosed hypertension, (2) current hypertension under a standardized measurement/reference protocol, or (3) future incident hypertension over a stated horizon. These targets are not interchangeable.

## Decisions to freeze

| Item | Status | Required decision/evidence |
|---|---|---|
| Intended user and setting | Open | Research-only or a named setting; specify who sees the output. |
| Population and eligibility | Open | Age range, geography/site, care setting, inclusion/exclusion, pregnancy and acute-care handling. |
| Target definition | Open | Choose diagnosis history, current measured hypertension, or future onset; specify case/control criteria. |
| Reference standard and index date | Open | Define the measurement protocol/diagnosis source and label window independently of the model. |
| Prediction horizon | Open | None for current status; define a horizon and pre-index features if incident disease is intended. |
| Inputs and feature timing | Open | Confirm each field exists before the decision; document measurement windows, missingness, and leakage controls. |
| Threshold and pass criteria | Open | Clinical team sets false-negative/false-positive consequences, threshold, sensitivity/specificity floors, and CI precision. |
| Governance | Open | Data owner, ethics review/waiver, privacy/consent, and secure access path. |

## Validation sequence

1. Reconcile source-specific target definitions; preserve source, patient, site, and time identifiers. Do not pool labels until semantic equivalence is justified.
2. Rebuild from raw data with patient/source-aware splits. Fit imputation, encoding, scaling, resampling, calibration, and thresholds only within development data/folds.
3. Freeze model and threshold using development data. Do not tune on the external test set.
4. Evaluate in an independent cohort matching the chosen reference standard. If the purpose is to avoid missed cases, use sensitivity at a clinician-selected threshold as primary, with a 95% CI. Also report specificity, PPV/NPV at observed prevalence, PR-AUC, ROC-AUC, and confusion matrix. Evaluate calibration only if the intended output is a probability.
5. Consider silent prospective evaluation only after external results and governance review support continuation.

## Current blockers

- Raw source and preprocessed files are absent from this branch; exact counts and labels cannot be reproduced here.
- NHANES self-report, Framingham prevalent hypertension, and the unavailable BRFSS target may differ in timing and case definition.
- `BPQ050A` is absent from the observed merged extract; the corrected mapping leaves the feature missing for those rows and model refitting is required.
- BRFSS sampling changes prevalence; cross-source random row splitting does not test transportability.
- Shared preprocessing, SMOTE-CV, calibration, and test-threshold defects remain.

## References

- CDC NHANES 2017–2018 BPQ_J codebook: https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/BPQ_J.htm
- CDC BRFSS 2023 survey data and documentation: https://www.cdc.gov/brfss/annual_data/annual_2023.html
- TRIPOD+AI: https://www.bmj.com/content/385/bmj-2023-078378
- ICMR ethics guidance: https://www.icmr.gov.in/post/handbook-on-national-ethical-guidelines-for-biomedical-and-health-research-involving-human-participants-2018

**Current decision:** research planning only. No hypertension model performance claim or patient-facing use is supported.
