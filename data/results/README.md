# Analysis Results and Audit Artifacts

This directory separates statistical results from the evidence needed to trust and reproduce them.

- `validation/` contains the machine-readable analysis contract, input registry, validation checks, country coverage, small-denominator audit, documented exclusions, missingness classifications, compact pooled/annual coverage summaries, and comparability decisions. These files describe analysis eligibility and data quality; they are not substantive findings.
- `manifests/` contains per-step manifests, the consolidated artifact and software registries, the minimum-output checklist, article-facing result metadata, interpretation-boundary checks, and dependency-ordered pipeline status.
- `manifests/` contains module provenance: input and output hashes, timestamps, row counts, validation status, and concise run summaries.
- `descriptive/` contains implemented destination summaries, country-level distribution statistics, and exact ECDF plotting points from Methods Section 3.
- `paired/` contains implemented matched-country differences, summary estimates and confidence intervals, paired test results, and the seeded bootstrap distribution from Methods Section 4.
- `models/` contains the implemented pooled and country-year binomial-model coefficients, probability contrasts, fit statistics, diagnostics, and influence table.
- `composition/` contains complete origin shares, concentration statistics, share concordance, plotting points, and the explicitly skipped composition-distance record.
- `temporal/` contains annual destination summaries, country-rate and decision-volume distributions, and matched country--year differences from Methods Section 9.
- `robustness/` contains the pre-specified 0/20/50/100-decision threshold comparisons, model-specification comparison, and transparent stability flags from Methods Section 10.

Canonical joined data belong in `data/prepared/comparison/`, not here. Publication-ready selections belong under `article/tables/` and `article/figures/` only after the underlying result artifacts have been verified.
