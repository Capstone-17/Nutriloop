# Public Data Source Inventory — Three-Disease Prototype

**Inventory date:** 2026-09-28  
**Purpose:** Record which candidate source files are present in the shared development workspace, whether they are in the `kevivt` repository, and what their labels can and cannot support. This is a provenance/readiness record, not a model evaluation.

## Scope and reproducibility boundary

The files below were inspected in the shared workspace's `medical datasets/raw` directory. They are **not** present in the `kevivt` branch at the training paths expected by `scripts/preprocess_data.py`; they are not copied or redistributed by this document. Their hashes identify the inspected local files only. A clean clone cannot reproduce these counts or retrain from them until provenance, licensing/terms, exact versions, and a controlled data staging procedure are resolved.

No protected health information or row-level data are included here. The NHANES extract contains a public survey identifier (`SEQN`), observed unique once in this extract; that does not establish patient linkage across files or satisfy a patient-level grouped validation requirement.

## Candidate source inventory

| Disease / role | Local file observed | Rows × columns | Target/count summary in inspected file | Inputs/features and preprocessing observations | Repository status |
|---|---|---:|---|---|---|
| CKD, UCI CKD candidate | `medical datasets/raw/chronic+kidney+disease/Chronic_Kidney_Disease.rar` | Archive 19,260 bytes; contents not inspected | Not measured from archive. UCI source metadata describes 400 records, 24 predictors, missing values, and CKD/not-CKD classes. | Code expects UCI-style clinical fields and derives `BP_ratio`, `pulse_pressure`, `glucose_diabetes`, and `creatinine_urea_ratio`. Archive must be extracted and compared field-by-field before treating it as the code's training source. The UCI CKD target is a concurrent CKD classification label, not a progression horizon. | Absent from branch; local archive SHA-256 `b7782fba71381f998f4478f088de06e0ae76b043024d7cd4ce1ae8b0578db165`. |
| Hypertension, Framingham candidate | `medical datasets/raw/hypertension/framingham_heart_study.csv` | 4,240 × 16 | `prevalentHyp`: 1,317 positive, 2,923 negative (31.06% positive). | Fields include age, sex, smoking, BP medication, systolic/diastolic BP, BMI, glucose, and the `prevalentHyp` target. BP measurements are contemporaneous with a prevalent-hypertension label; use for concurrent classification only after target/reference and feature timing are specified. Do not combine automatically with self-reported NHANES labels. | Absent from branch. SHA-256 `2c0e57dc0361b420becf1facec0a054af06c420eae0ae2faf0fdc8591fadb018`. |
| Hypertension + diabetes, NHANES 2017–2018 merged candidate | `medical datasets/raw/NHANES_2017_2018/NHANES_2017_2018_MERGED.csv` | 9,254 × 22 | `BPQ020`: yes 2,137; no 4,014; refusal/unknown code 9: 10; missing: 3,093. `DIQ010`: yes 893; no 7,816; borderline code 3: 184; code 9: 4; missing: 357. `SEQN` unique for all 9,254 rows. | Includes demographics, BMI, repeated BP measurements, glucose, diabetes and hypertension questionnaire responses, smoking questions, and `MCQ160F`. **Does not include `BPQ050A`**, the NHANES BP-medication question now required by the patched `BPMeds` mapping; the mapping correctly yields missing rather than copying `BPQ020`. Current self-report targets are not equivalent to lab-confirmed diagnoses. Before target use, apply the source-specific codebook and planned missing/indeterminate rules; account for the survey design/weights where appropriate. | Absent from branch. SHA-256 `f95c3d30d54eef2b7cb2ab24e91a709e263a431e990567358bf1027d0c1f5483`. |
| Type 2 diabetes, Pima candidate | `medical datasets/raw/diabetes/diabetes.csv` | 768 × 9 | `Outcome`: 268 positive, 500 negative (34.90% positive). | Features: pregnancies, glucose, blood pressure, skin thickness, insulin, BMI, diabetes pedigree function, and age. The preprocessing code treats zero in several physiologic fields as missing. The target's reference definition and sampling population must be verified; current glucose is target-proximal for concurrent classification and cannot establish future-onset performance. | Absent from branch. SHA-256 `698c203a14aa31941d2251175330c9199f3ccdb31597abbba2a3e35416257a72`. |

## Missing inputs and consequences

The following code-expected files were not found in the target branch: `datasets/preprocessed/{ckd,hypertension,diabetes}_{train_smote,test}.csv`, `med_dataset/large/hypertension_large_500k.csv`, and `med_dataset/large/diabetes_large_500k.csv`. In particular:

- There is no auditable evidence for the claimed 500k BRFSS-derived tables in this branch. Do not use the phrase “500k cohort” as a verified sample size until the exact source, transformation, row counts, label construction, sampling, and hashes are supplied.
- No source-group field is preserved in the listed fitted feature schemas, so cross-source performance and source holdout results cannot be recovered from the saved models alone.
- No patient linkage key or repeated-measure strategy is established for a patient-level split. A row-level random split cannot be called patient-independent.
- SMOTE or any other synthetic oversampling would alter training examples and prevalence; it cannot add independent patients or substitute for external validation. Report original and resampled class counts separately, and perform resampling only inside each development training fold.
- The target branch lacks a complete source-data bundle and split outputs. Therefore, no new three-disease performance numbers are reported in this iteration.

## Harmonization and intended-use limits

Do not pool Framingham `prevalentHyp`, NHANES prior clinician-reported diagnosis, and a BRFSS-derived field under one target without demonstrating equivalent case definitions. Likewise, Pima `Outcome`, NHANES prior self-report, and a BRFSS diabetes field are not interchangeable by column name. Prefer separate source-specific cohorts/results until a clinician and epidemiologist approve an explicit harmonization rule. Survey weights, population exclusions, time periods, and label ascertainment must remain attached to source metadata.

For CKD, the archived UCI-style label is a prevalent CKD classification target. It does not show persistence for at least three months, albuminuria-based criteria, incident disease, progression, or kidney failure horizon. Those targets require their own reference standard and longitudinal data.

The described data are public development/benchmark sources with population and ascertainment limitations. The Pima diabetes dataset is a small, selected cohort of women of Pima heritage; NHANES is a US household survey; Framingham is a community cohort from a specific US setting; the UCI CKD dataset is small and its cohort lineage should be traced. These are not representative of Indian clinical populations or of all care settings. No generalization to Indian patients or deployment population is supported.

## Exact inspected-file fingerprints

SHA-256 digests were computed over the complete files. The data are intentionally not copied into the repository by this inventory iteration.

| Relative path | SHA-256 |
|---|---|
| `chronic+kidney+disease/Chronic_Kidney_Disease.rar` | `b7782fba71381f998f4478f088de06e0ae76b043024d7cd4ce1ae8b0578db165` |
| `diabetes/diabetes.csv` | `698c203a14aa31941d2251175330c9199f3ccdb31597abbba2a3e35416257a72` |
| `hypertension/framingham_heart_study.csv` | `2c0e57dc0361b420becf1facec0a054af06c420eae0ae2faf0fdc8591fadb018` |
| `NHANES_2017_2018/NHANES_2017_2018_MERGED.csv` | `f95c3d30d54eef2b7cb2ab24e91a709e263a431e990567358bf1027d0c1f5483` |

## Primary source documentation

- [UCI Chronic Kidney Disease dataset](https://archive.ics.uci.edu/dataset/336/chronic%2Bkidney%2Bdisease)
- [CDC NHANES BPQ_J codebook](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/BPQ_J.htm) — includes `BPQ050A` medication status.
- [CDC NHANES variable list](https://wwwn.cdc.gov/nchs/nhanes/search/variablelist.aspx?Component=Questionnaire&Cycle=2017-2018)
- [CDC BRFSS 2023 data and documentation](https://www.cdc.gov/brfss/annual_data/annual_2023.html)
- [Pima Indians Diabetes Database record](https://www.kaggle.com/datasets/uciml/pima-indians-diabetes-database) — verify the upstream source/version/license for the local copy before redistribution.
- [Framingham Heart Study source listing](https://www.kaggle.com/datasets/amanajmera1/framingham-heart-study-dataset) — local file lineage/license still needs verification.

## Next reproducible data step

1. Resolve source URL/version/license and provenance for every local file; preserve source metadata and codebook.
2. Extract and inspect the CKD archive without altering it; compare field names/labels with UCI metadata and preprocessing expectations.
3. Reacquire the needed NHANES component containing `BPQ050A`, join on survey participant ID, and retain survey design variables and source lineage.
4. Recover or rebuild BRFSS inputs from the CDC source with documented transformations, natural prevalence, and original survey weights; do not fabricate missing positive rows.
5. Store patient/participant and source/site/time identifiers out of model features; agree data governance before cohort linkage.
6. Define target and reference standard per disease, then build source-specific, group-aware development and held-out evaluations with all preprocessing and resampling inside folds.

Until those prerequisites are met, this inventory supports source-readiness planning only. It does not validate any model or authorize real-patient use.
