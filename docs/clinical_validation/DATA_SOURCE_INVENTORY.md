# Public Data Source Inventory — Three-Disease Prototype

**Inventory date:** 2026-09-28
**Purpose:** Record which candidate source files are present in the shared development workspace, whether they are in the `kevivt` repository, and what their labels can and cannot support. This is a provenance/readiness record, not a model evaluation.

## Scope and reproducibility boundary

The files below were inspected in the shared workspace's `medical datasets/raw` directory. They are **not** present in the `kevivt` branch at the training paths expected by `scripts/preprocess_data.py`; they are not copied or redistributed by this document. Their hashes identify the inspected local files only. A clean clone cannot reproduce these counts or retrain from them until provenance, licensing/terms, exact versions, and a controlled data staging procedure are resolved.

No protected health information or row-level data are included here. The NHANES extract contains a public survey identifier (`SEQN`), observed unique once in this extract; that does not establish patient linkage across files or satisfy a patient-level grouped validation requirement.

## Candidate source inventory

| Disease / role | Local file observed | Rows × columns | Target/count summary in inspected file | Inputs/features and preprocessing observations | Repository status |
|---|---|---:|---|---|---|
| CKD, UCI CKD candidate | `medical datasets/raw/chronic+kidney+disease/Chronic_Kidney_Disease.rar` | Archive 19,260 bytes; contains two ARFF files, each 400 × 25 (24 inputs + class) | Both ARFF copies contain 248 `ckd`, 150 `notckd`, and **2 blank class labels**. The included `.info.txt` says 250/150, so its CKD count disagrees with the actual labeled rows by two. Exclude unlabeled outcomes from supervised analysis and resolve/record the discrepancy; do not infer their labels. | 24 features cover age, BP, specific gravity, albumin, sugar, urine microscopy/culture, blood glucose, urea, creatinine, electrolytes, hemoglobin/cell counts, comorbidity and symptom indicators. The ARFF names white/red cell count `wbcc`/`rbcc`; the info file uses `wc`/`rc`. Missingness among the 24 features ranges from 1 to 152 rows per field (e.g. red blood cells 152, red cell count 131, white blood cell count 106, potassium 88, sodium 87). Code also derives four engineered fields. The local file appears structurally consistent with UCI ID 336 but its source/license lineage still needs confirmation. Its label is concurrent classification, not a progression horizon. | Absent from branch. Archive SHA-256 `b7782fba71381f998f4478f088de06e0ae76b043024d7cd4ce1ae8b0578db165`; `chronic_kidney_disease.arff` SHA-256 `0f3360c0e9239d3d211bfbbdedbe818e4569e6d7399e7398c9b464f6e8feeebe`; `chronic_kidney_disease_full.arff` SHA-256 `a5ea96369b8516d725e4f353ad9c6e7e25a1a7db227bc761f59d8e0dfab15797`; info file SHA-256 `7caf98e34606191d6e5278978a7a4e4df123840374f7a6f5063c4d18501744a3`. |
| Hypertension, Framingham candidate | `medical datasets/raw/hypertension/framingham_heart_study.csv` | 4,240 × 16 | `prevalentHyp`: 1,317 positive, 2,923 negative (31.06% positive). | Fields include age, sex, smoking, BP medication, systolic/diastolic BP, BMI, glucose, and the `prevalentHyp` target. BP measurements are contemporaneous with a prevalent-hypertension label; use for concurrent classification only after target/reference and feature timing are specified. Do not combine automatically with self-reported NHANES labels. | Absent from branch. SHA-256 `2c0e57dc0361b420becf1facec0a054af06c420eae0ae2faf0fdc8591fadb018`. |
| Hypertension + diabetes, NHANES 2017–2018 merged candidate | `medical datasets/raw/NHANES_2017_2018/NHANES_2017_2018_MERGED.csv` | 9,254 × 22 | `BPQ020`: yes 2,137; no 4,014; refusal/unknown code 9: 10; missing: 3,093. `DIQ010`: yes 893; no 7,816; borderline code 3: 184; code 9: 4; missing: 357. `SEQN` unique for all 9,254 rows. | Includes demographics, BMI, repeated BP measurements, glucose, diabetes and hypertension questionnaire responses, smoking questions, and `MCQ160F`. **Does not include `BPQ050A`**, the NHANES BP-medication question now required by the patched `BPMeds` mapping; the mapping correctly yields missing rather than copying `BPQ020`. Current self-report targets are not equivalent to lab-confirmed diagnoses. Before target use, apply the source-specific codebook and planned missing/indeterminate rules; account for the survey design/weights where appropriate. | Absent from branch. SHA-256 `f95c3d30d54eef2b7cb2ab24e91a709e263a431e990567358bf1027d0c1f5483`. |
| Type 2 diabetes, Pima candidate | `medical datasets/raw/diabetes/diabetes.csv` | 768 × 9 | `Outcome`: 268 positive, 500 negative (34.90% positive). | Features: pregnancies, glucose, blood pressure, skin thickness, insulin, BMI, diabetes pedigree function, and age. The preprocessing code treats zero in several physiologic fields as missing. The target's reference definition and sampling population must be verified; current glucose is target-proximal for concurrent classification and cannot establish future-onset performance. | Absent from branch. SHA-256 `698c203a14aa31941d2251175330c9199f3ccdb31597abbba2a3e35416257a72`. |

## Observed missingness and eligible target rows

These are counts from the local extracts only, not a validation cohort. Missingness was calculated before fitting any imputer. For the Pima field counts below, exact zero values in the five fields treated as invalid/missing by the repository preprocessing were first recoded to missing; the count is the resulting missing count, not the count of original blank cells.

- **Framingham hypertension:** among 4,240 rows, the local file has 105 missing education, 29 missing cigarettes/day, 53 missing BP medication, 50 missing total cholesterol, 19 missing BMI, 1 missing heart rate, and 388 missing glucose. Target `prevalentHyp` is present on all 4,240 rows (1,317 positive / 2,923 negative). The label distribution reflects this cohort and does not harmonize it with NHANES.
- **NHANES hypertension:** 6,151/9,254 rows have explicit binary `BPQ020` answers (2,137 yes / 4,014 no). The other 3,103 are missing/refusal/unknown and are excluded by the current target mapping. The extract lacks `BPQ050A`, leaving the medication feature unavailable. This count does not account for survey weights.
- **NHANES diabetes:** 8,709/9,254 rows have explicit yes/no `DIQ010` (893 yes / 7,816 no). The remaining 545 comprise 184 borderline, 4 refusal/unknown, and 357 missing responses and are excluded by binary mapping. This is self-report, not lab-adjudicated diabetes; the count is unweighted.
- **Pima diabetes:** after repository zero-to-missing handling, missing counts are glucose 5, blood pressure 35, skin thickness 227, insulin 374, and BMI 11. Target `Outcome` has no missing values in the file (268 positive / 500 negative). The very high missing fractions in insulin and skin thickness make the imputation assumption consequential and require sensitivity analysis.

The repository currently imputes/scales using the full concatenated table before splitting. These counts therefore describe source files only; they must not be used to justify or reproduce the existing model metrics. Re-estimate missingness per source and per fold during a corrected rebuild, keeping target-excluded and feature-missing counts distinct.

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
| `chronic+kidney+disease/Chronic_Kidney_Disease/chronic_kidney_disease.arff` | `0f3360c0e9239d3d211bfbbdedbe818e4569e6d7399e7398c9b464f6e8feeebe` |
| `chronic+kidney+disease/Chronic_Kidney_Disease/chronic_kidney_disease_full.arff` | `a5ea96369b8516d725e4f353ad9c6e7e25a1a7db227bc761f59d8e0dfab15797` |
| `chronic+kidney+disease/Chronic_Kidney_Disease/chronic_kidney_disease.info.txt` | `7caf98e34606191d6e5278978a7a4e4df123840374f7a6f5063c4d18501744a3` |
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
2. Resolve the CKD count discrepancy (metadata says 250 CKD; both ARFF copies have 248 labeled CKD plus two unlabeled targets) with a source-of-record copy or documented exclusion. Normalize `wc`/`rc` versus `wbcc`/`rbcc` names only through an explicit, tested mapping.
3. Reacquire the needed NHANES component containing `BPQ050A`, join on survey participant ID, and retain survey design variables and source lineage.
4. Recover or rebuild BRFSS inputs from the CDC source with documented transformations, natural prevalence, and original survey weights; do not fabricate missing positive rows.
5. Store patient/participant and source/site/time identifiers out of model features; agree data governance before cohort linkage.
6. Define target and reference standard per disease, then build source-specific, group-aware development and held-out evaluations with all preprocessing and resampling inside folds.

Until those prerequisites are met, this inventory supports source-readiness planning only. It does not validate any model or authorize real-patient use.
