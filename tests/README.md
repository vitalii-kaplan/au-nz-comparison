# Research Analysis Tests

This directory contains regression tests for preparation scripts and tests for statistical research modules under `src/`. Methods Sections 1--15 are implemented and tested, including the prerequisite Section 11 comparability gate and the final reproducibility and quality-control pipeline.

The current executable preparation regression test is:

- `test_prepare_new_zealand.py`, which runs `scripts/prepare_new_zealand.py` with temporary outputs and verifies its combined table against `tests/data/inz_student_visa_decisions_2022-2025.csv`, copied from the previous article.

The current executable article-production test is:

- `test_generate_article_validation_outputs.py`, which verifies the scale and coverage values read from the validation artifacts, checks the generated LaTeX table and PGFPlots source, and confirms that a failed blocking check prevents publication-output generation; and
- `test_generate_article_analysis_outputs.py`, which verifies the Section 3 and 4 manifests, result dimensions, reported values, and generated publication tables and figures.
- `test_generate_article_concordance_country_outputs.py`, which verifies the Section 5 and 6 manifests and the generated concordance table, equal-axis scatterplot, selected-country table, and 20-country forest plot.
- `test_generate_article_model_outputs.py`, which verifies the pooled origin-adjusted model table and standardized-probability figure used by the article.
- `test_generate_article_sensitivity_outputs.py`, which verifies the minimum-denominator sensitivity tables and figure used by the article.
- `test_generate_article_comparability_outputs.py`, which verifies the Section 11 manifest and generated overlap table, gate-decision table, and comparability figure.

The current executable research-module tests are:

- `test_analysis_01_define_contract.py`, covering contract generation, input totals, and rejection of an incorrect comparison direction; and
- `test_analysis_02_build_tables.py`, covering all primary comparison-table row counts, matched-difference direction, exclusions, annual overlap, validation status, and rejection of inconsistent prepared counts;
- `test_analysis_03_descriptive.py`, covering type-7 quantiles, destination totals and rates, distribution outputs, ECDF completeness, and the module manifest; and
- `test_analysis_04_matched_comparison.py`, covering Student-$t$ calculations, signed ranks and zero handling, matched output contracts, the seeded bootstrap, and deterministic results.
- `test_analysis_05_concordance.py`, covering tied ranks, Pearson calculation, the two concordance outputs, complete scatter points, and deterministic seeded intervals; and
- `test_analysis_06_country_differences.py`, covering Fisher's exact test, Newcombe intervals, Benjamini--Hochberg adjustment, full-family output, test selection, and forest-plot selection.
- `test_analysis_07_binomial_regression.py`, covering model gates, destination coefficients, cluster-robust uncertainty, standardized contrasts, convergence, and separation diagnostics;
- `test_analysis_08_origin_composition.py`, covering HHI and Gini calculations, share reconciliation, concentration outputs, matched-share plotting points, and the explicit Jensen--Shannon skip; and
- `test_analysis_09_temporal.py`, covering annual distribution summaries, complete destination-year and matched-year outputs, seeded bootstrap intervals, and deterministic artifacts;
- `test_analysis_10_sensitivity.py`, covering seeded intervals, pre-specified threshold populations, baseline concordance reproduction, model comparison, and stability flags; and
- `test_analysis_11_comparability.py`, covering matched pooled and annual eligibility, pooled and annual audit summaries, and the prohibition on unsupported zero assignment.
- `test_analysis_12_reproducibility.py`, covering manifest and artifact-hash consolidation, publication-artifact registration, software-version records, and the zero-issue audit;
- `test_analysis_13_validate_outputs.py`, covering the required nine-table and nine-figure inventory, schemas, unique keys, hash registration, and the documented optional-output skip;
- `test_analysis_14_interpretation_checks.py`, covering result metadata boundaries and rejection of unsupported machine-generated claims; and
- `test_analysis_15_run_pipeline.py`, covering dependency order, comparability-based skips, stage-status records, and immediate failure propagation.

## Layout

Each public analysis module has one mirrored test module:

```text
src/analysis_01_define_contract.py        tests/test_analysis_01_define_contract.py
src/analysis_02_build_tables.py           tests/test_analysis_02_build_tables.py
src/analysis_03_descriptive.py            tests/test_analysis_03_descriptive.py
src/analysis_04_matched_comparison.py     tests/test_analysis_04_matched_comparison.py
src/analysis_05_concordance.py            tests/test_analysis_05_concordance.py
src/analysis_06_country_differences.py    tests/test_analysis_06_country_differences.py
src/analysis_07_binomial_regression.py    tests/test_analysis_07_binomial_regression.py
src/analysis_08_origin_composition.py     tests/test_analysis_08_origin_composition.py
src/analysis_09_temporal.py               tests/test_analysis_09_temporal.py
src/analysis_10_sensitivity.py            tests/test_analysis_10_sensitivity.py
src/analysis_11_comparability.py          tests/test_analysis_11_comparability.py
src/analysis_12_reproducibility.py        tests/test_analysis_12_reproducibility.py
src/analysis_13_validate_outputs.py       tests/test_analysis_13_validate_outputs.py
src/analysis_14_interpretation_checks.py  tests/test_analysis_14_interpretation_checks.py
src/analysis_15_run_pipeline.py           tests/test_analysis_15_run_pipeline.py
```

Reference datasets used only for regression testing are stored under `tests/data/`. Shared synthetic fixtures may be defined in `tests/conftest.py` or stored under `tests/fixtures/`. Tests must not modify verified prepared data. Preparation integration tests may read their documented immutable inputs under `data/original/`; statistical research-module tests must use prepared data or controlled fixtures and must not read original data.

## Required test levels

- Unit tests for formulas, statistics, confidence intervals, multiple-testing correction, concentration measures, and table transformations.
- Boundary tests for zero cells, zero paired differences, small denominators, absent countries, ties, sparse tables, and invalid schemas.
- Contract tests for required columns, key uniqueness, sorting, count reconciliation, stable output schemas, and explicit exclusions.
- Regression tests for deterministic CSV contents and configured random seeds.
- Integration tests that run each module against controlled fixtures and verify all declared artifacts.
- Pipeline tests that verify dependency order, validation gates, recorded skips, failure propagation, and manifest completeness.

Numerical tests should use justified tolerances and compare against independently calculated expected values. A test should not merely reproduce the implementation formula with the same helper being tested.
