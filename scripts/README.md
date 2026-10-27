# Data Preparation and Article Reproduction

The scripts in this directory reproduce the current article. Statistical calculations remain in `src/`; publication generators only transform verified result artifacts into the LaTeX tables and PGFPlots figures imported by `article/article.tex`.

## End-to-end command

After downloading and selectively extracting the source files described in [`../data/README.md`](../data/README.md), run:

```sh
python3 scripts/reproduce_article.py --run-tests --build-pdf
```

Without options, `reproduce_article.py` prepares the source data, runs the dependency-ordered statistical pipeline, and regenerates every article table and figure. `--run-tests` adds the complete unit and integration test suite. `--build-pdf` compiles `article/article.pdf` with `latexmk`.

Use `--skip-preparation` only when the prepared AU/NZ tables already exist and are known to correspond to the current source inputs.

## Preparation scripts

- `prepare_new_zealand.py` builds and validates the four annual New Zealand source-label tables and their pooled table.
- `prepare_australia.py` filters the Australian source to the study population, reconstructs calendar years, aggregates decisions, and records a preparation audit.
- `extract_un_m49.py` extracts the English UN M49 table from the preserved official overview page.
- `check_country_names.py` harmonizes every annual AU/NZ table and constructs the pooled normalized tables only after annual normalization.

## Article publication generators

The main pipeline runs these generators after the statistical results pass and before the reproducibility manifest is consolidated:

- `generate_article_validation_outputs.py` produces the dataset-scale table and coverage figure.
- `generate_article_comparability_outputs.py` produces the comparability table and audit figure.
- `generate_article_analysis_outputs.py` produces the descriptive and matched-origin tables and figures.
- `generate_article_concordance_country_outputs.py` produces the concordance and country-specific tables and figures.
- `generate_article_model_outputs.py` produces the pooled origin-adjusted model table and probability figure.
- `generate_article_sensitivity_outputs.py` produces the minimum-denominator sensitivity tables and figure.

These six generators produce exactly the eight tables and nine figures imported by the manuscript. They verify the relevant analysis manifests and output hashes before writing publication artifacts.

To regenerate only publication artifacts after a successful analysis run:

```sh
python3 scripts/generate_article_validation_outputs.py
python3 scripts/generate_article_comparability_outputs.py
python3 scripts/generate_article_analysis_outputs.py
python3 scripts/generate_article_concordance_country_outputs.py
python3 scripts/generate_article_model_outputs.py
python3 scripts/generate_article_sensitivity_outputs.py
```
