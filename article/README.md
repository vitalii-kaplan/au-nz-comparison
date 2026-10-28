# Active Article: Matched-Origin Decision Outcomes

## Status and purpose

This directory contains the active manuscript and its publication artifacts. `article.tex` is the manuscript source of record. Its bibliography, class and style files, generated tables and figures, and compiled PDF are stored here.

The manuscript compares recorded student-visa decision outcomes between Australia and New Zealand for matched applicant-origin countries. It establishes the shared decision denominator, assesses the comparability of the source populations, defines the matched-origin analytical population, and reports the main cross-national comparison.

## Title plan

The preprint title is:

**Comparison of Student Visa Decision Outcomes Between Australia and New Zealand Across Applicant-Origin Countries**

The intended journal-publication title, subject to acceptance and venue requirements, is:

**Statistical Comparison of International Student Visa Approval Rates Between Australia and New Zealand**

The LaTeX manuscript currently uses the preprint title. Replace it only when preparing an accepted journal version or when the selected journal requires the shorter title.

The reserved Zenodo preprint DOI is [10.5281/zenodo.23739706](https://doi.org/10.5281/zenodo.23739706). It is printed on the manuscript title page and will resolve publicly after the Zenodo record is published.

Use *decision outcomes* or *decision approval rates*, not application approval rates. The common denominator is grants or approvals plus refusals or declines; it is not lodgements or all applications.

## Central question and contribution

The article asks: after aligning decision denominators and matching published origin-country labels, how do recorded student visa decision outcomes differ between Australia and New Zealand?

Its contribution is the matched-origin comparison. It shows how the Australia--New Zealand difference appears in pooled summaries, matched-country estimates, concordance, country-specific comparisons, and an origin-adjusted model. It reports heterogeneity and retains an aggregate, descriptive, non-causal interpretation.

## Implemented scope

The manuscript includes:

- the Australian and New Zealand source populations and decision measures;
- the common two-outcome decision denominator;
- period and population differences that cannot be fully aligned;
- country-name harmonisation, reviewed exceptions, exclusions, and overlap;
- the missingness and comparability gate;
- pooled descriptive and matched-country comparisons;
- cross-destination concordance and country-specific differences;
- the pooled country-fixed-effect binomial model; and
- sensitivity to minimum decision denominators.

## Publication artifacts

The main text uses these generated artifacts from verified results:

- `tables/comparability_coverage.tex`;
- `tables/descriptive_comparison.tex`;
- `tables/matched_country_comparison.tex`;
- `tables/approval_rate_concordance.tex`;
- a selected form of `tables/country_specific_results.tex`;
- `tables/pooled_binomial_regression_results.tex`;
- `tables/sensitivity_analysis.tex`;
- `figures/decision_volume_log10_bins.tex`;
- `figures/descriptive_ecdfs.tex`;
- `figures/matched_difference_distribution.tex`;
- `figures/approval_rate_concordance.tex`;
- `figures/country_difference_forest.tex`;
- `figures/pooled_standardized_probabilities.tex`; and
- `figures/threshold_sensitivity.tex`.

The complete 173-country result, detailed diagnostics, validation inventories, and technical pipeline checks should normally remain supplementary or repository material.

## Interpretation boundaries

Interpret the pooled, matched-origin, country-specific, concordance, and adjusted comparisons together. Emphasize heterogeneity, unequal denominators, source-population differences, overdispersion, ecological limits, and the absence of a causal identification strategy.

The defensible conclusion is that Australia had higher recorded decision approval rates in pooled, matched-origin, and adjusted comparisons under the study definitions, while the magnitude depended on weighting and country inclusion and varied substantially across origins. The article must not infer policy effects, procedural fairness, applicant quality, or individual approval probabilities.

## Public repository requirement before publication

The project repository is configured at <https://github.com/vitalii-kaplan/au-nz-comparison>. The manuscript currently uses repository-relative paths such as `data/prepared/comparison/`; keep those paths stable as the project continues.

Before the manuscript is treated as publication-ready:

- publish the release-ready project files in that repository;
- add a reader-facing reference to that repository wherever repository-relative paths are used;
- add the final repository reference to the appropriate data or code availability statement if required by the venue; and
- verify that every path cited in the manuscript exists and is accessible in the public version.

The manuscript cites the public repository wherever it gives a repository-relative documentation or manifest path. The cited paths must be retested against the public version after each release and before publication.

## Current status

The manuscript is implemented and compiles independently as `article.pdf`. Its Abstract, Introduction, Literature Review, Discussion, Limitations, and Conclusion have been revised against the verified evidence and current scope. Statistical foundations and their references remain in Methods and `Methods-citations.md` rather than being repeated in the Literature Review. Further manuscript revisions require separate authorization and supporting evidence.
