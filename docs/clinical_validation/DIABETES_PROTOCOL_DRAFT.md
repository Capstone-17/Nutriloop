# Type 2 Diabetes Intended-Use and Validation Protocol — Draft

**Status: DRAFT / NOT APPROVED.** Planning worksheet only. No clinical study, external validation, or authorization to access patient data has been performed.

Last updated: 2026-09-28

## Evidence from the checked-in pipeline

- Training code pools Pima `Outcome`, NHANES 2017–2018 `DIQ010`, and an unavailable BRFSS-derived `diabetes_large_500k.csv` target. Raw cohort files and preprocessed train/test tables are absent from this branch.
- NHANES `DIQ010` is self-reported history of clinician-diagnosed diabetes. The code now maps explicit yes/no values only; borderline and nonresponse values stay missing and are excluded by the binary-target `dropna` step. [CDC NHANES 2017–2018 variable list](https://wwwn.cdc.gov/nchs/nhanes/search/variablelist.aspx?Component=Questionnaire&Cycle=2017-2018)
- The prototype's weekly-plan output now calls a single diabetes-range lab a finding and says one measurement does not establish diagnosis. This is a wording safeguard; the same heuristic still changes internal meal targets, and no confirmatory-diagnosis workflow is collected or validated.
- The Pima input schema includes glucose and glucose-derived interaction features. This may be circular if the target is defined from the same-encounter diagnostic tests; it does not establish future diabetes risk.
- The BRFSS preprocessing samples up to 20,000 positive rows while retaining all negatives, changing natural prevalence. Its source file is absent. Imputation/scaling happen before row splitting. The training script now selects a provisional threshold on training out-of-fold predictions, but its pre-SMOTE inputs still leak synthetic neighbors across CV folds.
- The inspected local Pima file has 768 rows (268 positive / 500 negative); after the repository's zero-to-missing rule, insulin is missing in 374 rows, skin thickness in 227, blood pressure in 35, BMI in 11, and glucose in 5. The local NHANES extract has 8,709 explicit yes/no `DIQ010` answers (893 yes / 7,816 no); 545 borderline/nonresponse/missing rows are excluded. These are unweighted source counts, not performance results; hashes and limitations are in the [source inventory](DATA_SOURCE_INVENTORY.md).
- The [generated exploratory benchmark](../../reports/clinical_validation/exploratory_public_cohort_benchmark.json) keeps Pima and NHANES in separate cohorts. Pima glucose may be target-proximal; NHANES uses prior self-reported diagnosis and is unweighted. Neither result is an independent clinical validation or supports patient use.

## Candidate question — pending approval

**Candidate only:** How well does a frozen model classify a pre-specified current type 2 diabetes outcome at a defined index time in a defined cohort, using only information available for the intended user at that time?

The existing labels appear to describe current/past status, not a future-onset horizon. Choose one target: prior clinician diagnosis, diabetes under a defined laboratory/clinical reference standard at index, or incident diabetes within a future horizon. These targets need different inputs and analyses.

## Decisions to freeze

| Item | Status | Required decision/evidence |
|---|---|---|
| Intended user and setting | Open | Research-only or named clinical setting; specify who sees output and what action may follow. |
| Population and eligibility | Open | Age range, geography/site, pregnancy handling, comorbidities, and exclusions. |
| Target definition | Open | Choose diagnosis history, current status under a defined standard, or future onset; resolve borderline and gestational cases. |
| Reference standard and index date | Open | Specify test(s), repeat/confirmation rule, source records, index, and label window. |
| Prediction horizon | Open | None for current status; define the future horizon and enforce pre-index features if incident risk is intended. |
| Inputs and feature timing | Open | Decide whether glucose, insulin, and derived features are allowed and available before prediction. Document missingness and units. |
| Threshold and pass criteria | Open | Set sensitivity/specificity and CI requirements before external validation; never choose threshold on the external test cohort. |
| Governance | Open | Identify source/data owner, ethics review/waiver, consent/privacy path, and secure environment. |

## Validation sequence

1. Recover/checksum source files and document label definitions separately for Pima, NHANES, and BRFSS. Preserve source, patient, site, and time fields.
2. Decide current diagnosis support versus future-risk prediction. Audit glucose and other diagnostic features against the reference standard and feature timing.
3. Rebuild source-aware development/validation pipelines with group separation and fold-local imputation, encoding, scaling, resampling, calibration, and threshold selection. Handle borderline values as prespecified indeterminate/excluded cases, never silently as negatives.
4. Freeze the model and threshold before testing in an independent cohort with a matching reference standard. When avoiding missed disease is the goal, report sensitivity with a 95% CI as primary; also report specificity, PPV/NPV at source prevalence, PR-AUC, ROC-AUC, confusion matrix, and calibration if probabilities are intended.
5. Consider silent prospective evaluation only after retrospective external validation and governance review support it.

## Current blockers

- Cohort raw files and train/test outputs are absent from the target branch; exact counts, labels, IDs, and source provenance cannot be reproduced here.
- Pima `Outcome`, NHANES self-report, and BRFSS-derived labels are not shown to be equivalent.
- The corrected NHANES mapping has not been used to refit the diabetes model.
- Glucose features may be target-proximal for concurrent diagnosis and do not define a future-risk model.
- BRFSS sampling, preprocessing-before-split, SMOTE-before-CV, resampled calibration, and test-set threshold selection remain unresolved.

## References

- CDC NHANES 2017–2018 questionnaire variable list: https://wwwn.cdc.gov/nchs/nhanes/search/variablelist.aspx?Component=Questionnaire&Cycle=2017-2018
- CDC BRFSS 2023 survey data and documentation: https://www.cdc.gov/brfss/annual_data/annual_2023.html
- TRIPOD+AI: https://www.bmj.com/content/385/bmj-2023-078378
- ICMR ethics guidance: https://www.icmr.gov.in/post/handbook-on-national-ethical-guidelines-for-biomedical-and-health-research-involving-human-participants-2018

**Current decision:** research planning only. No diabetes model performance claim or patient-facing use is supported.
