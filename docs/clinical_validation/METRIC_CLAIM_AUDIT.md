# Metric and Quantified-Claim Audit

**Updated:** 2026-09-28  
**Scope:** metric-like claims in the checked-in README, API reporting path, model-profile artifacts, and software smoke tests. This is an audit trail, not a new clinical validation report.

## Current source of truth

The reproducible **exploratory public-cohort** metrics are generated from the local raw files by `scripts/evaluate_public_cohorts.py` and written to [`exploratory_public_cohort_benchmark.json`](../../reports/clinical_validation/exploratory_public_cohort_benchmark.json). That JSON records source hashes, versions, fold definitions, per-fold metrics, class distributions, confusion matrices, and mean ± standard deviation. The API's `/implementation-progress` now reads only this generated report for metric rows. It does not fall back to the old profile metrics.

These are source-specific, internal cross-validation estimates at a generic 0.5 cutoff. The sources/targets are not pooled, and the results are not metrics for the deployed desktop artifacts or clinical validation. The API adds an explicit `evaluation_status` field for this reason.

## Quarantined historical model-profile metrics

Before this audit, `artifacts/risk_thresholds_and_factors.json` contained the following numbers and `/implementation-progress` exposed them when no CSV comparison report existed. The train/test CSVs that would establish their source are absent from the branch. The checked-in legacy training code also fit transformations before splitting, cross-validated a pre-SMOTE training table, calibrated on the resampled distribution, and selected its threshold on test labels. **These historical values are not verified and must not be cited.** Their `metrics` fields have been removed from the active artifact; thresholds and feature-factor fields remain marked as unvalidated engineering defaults because the runtime still reads them.

| Disease | Historical accuracy | Historical macro-F1 | Historical sensitivity/recall | Historical specificity | Historical ROC-AUC | Historical PR-AUC | Historical Brier |
|---|---:|---:|---:|---:|---:|---:|---:|
| CKD | 0.8573 | 0.8572 | 0.8375 | 0.8770 | 0.9207 | 0.9239 | 0.1068 |
| Hypertension | 0.9399 | 0.9398 | 0.9407 | 0.9391 | 0.9537 | 0.9430 | 0.0535 |
| Type 2 diabetes | 0.9050 | 0.9041 | 0.8791 | 0.9269 | 0.9276 | 0.9066 | 0.0810 |

### Why a numeric “delta” is not meaningful

The new benchmark is not a like-for-like rerun of the old model-profile experiment: it uses separately defined CKD, Framingham hypertension, Pima diabetes, and NHANES self-report cohorts; compares ten algorithms; performs five-fold evaluation; uses fold-local preprocessing; does not SMOTE; and uses a fixed 0.5 cutoff. The legacy target files, raw training tables, cohort hashes, exact labels, and row membership are missing. Therefore, differences cannot be attributed to class imbalance alone or interpreted as improvement/regression of the same model. The historical metrics remain quarantined rather than being subtracted from non-comparable new estimates.

The newer result file itself still has limits: row-level folds are used for CKD, Framingham, and Pima because IDs are absent; NHANES grouping uses `SEQN`; no NHANES survey weights are used; no confidence intervals or clinician-approved operating thresholds are provided; and no independent site or prospective cohort was evaluated.

## README and smoke-test claim corrections

- Replaced the README's **±0.5%** calorie-precision statement with the tested **±5%** synthetic-plan tolerance.
- Replaced the claim of no duplicate days with the actual assertion: at least five distinct lunch/dinner *title pairs* in each generated sample week.
- Replaced “100% Jain/allergen compliance” wording with what the current smoke test actually asserts: a peanut substring is absent from Jain plan item names, and “fish”/“machh” substrings are absent from Bengali vegetarian dish titles. This does not check every ingredient or allergen.
- Renamed `scripts/test_diet_accuracy.py` as synthetic software smoke checks, not clinical validation. Its eGFR check is now formula arithmetic only and no longer requires the test to call one eGFR measurement a CKD diagnosis.
- Corrected the old arithmetic expectation 48.7 to 49.3 mL/min for the specified input according to the implemented race-free CKD-EPI 2021 equation; this arithmetic smoke check does not validate the equation clinically or establish CKD status.

The checked-in branch contains no PowerPoint, PDF manuscript, Word paper, TeX paper, or notebook files with additional reported model metrics. This was determined by enumerating tracked working-tree files with those extensions; future documents still need an audit before release.

## Remaining unverified claims

- Existing model bundles are still used by the GUI; they have not been retrained from the corrected source mappings or independently validated.
- The GUI can still display a CKD score/risk band driven by an unvalidated rules path. A displayed score is not a calibrated clinical probability.
- The software smoke checks do not establish nutrient-target appropriateness, ingredient-level dietary/allergen safety, or patient benefit.
- The paper/slide release process must source all reported metrics directly from the generated benchmark artifact and must label these public-cohort estimates as exploratory.
