# Comparison of Student Visa Decision Outcomes Between Australia and New Zealand Across Applicant-Origin Countries

## Abstract

This study compares student visa decision approval rates using aggregate public records from Australia and New Zealand for 2022–2025. We calculate each rate as approvals divided by approvals plus refusals and compare 173 published applicant origins observed in both destinations. The mean Australian-minus-New Zealand difference was 16.3 percentage points (95% confidence interval 12.7–19.9). Approval rates were positively associated across destinations (Pearson $r = 0.629$), which is consistent with applicant-origin context contributing to the observed pattern. However, 56 country-specific differences remained significant after Benjamini–Hochberg adjustment, and the pooled origin-adjusted model produced an Australian-minus-New Zealand contrast of 10.9 points (95% confidence interval 6.6–15.2). The positive average direction persisted at every pre-specified minimum-decision threshold, although country-specific differences varied in both size and direction. These findings show that the student's origin country is relevant but does not fully explain recorded approval rates. Records for the same published origin country can have different rates in Australia and New Zealand as immigration destinations. Explanations must therefore consider the pair formed by the student's origin country and the immigration destination country. The estimates are aggregate associations and do not identify a causal destination effect or an individual applicant's probability of approval.

The manuscript is available as [article/article.pdf](article/article.pdf), with its LaTeX source in [article/article.tex](article/article.tex). Its reserved Zenodo preprint DOI is [10.5281/zenodo.23739706](https://doi.org/10.5281/zenodo.23739706); the DOI will resolve publicly after the Zenodo record is published.

## Study design

The analysis uses the closest comparable public populations available:

- Australia: primary applicants outside Australia in the Higher Education Sector;
- New Zealand: offshore or overseas applicants in the student visa categories covered by the annual releases; and
- period: calendar years 2022–2025.

Country labels are harmonized separately within each year against the English UN M49 reference before annual records are pooled. Taiwan and Kosovo are retained as reviewed non-M49 exceptions where present. Australian `Not Specified` and `Refugee` records are excluded from country-level comparison.

The principal analytical population contains 173 matched applicant origins. The pipeline distinguishes decision-weighted national summaries, equally weighted origin-country comparisons, country-specific differences, and origin-adjusted grouped-binomial estimates.

## Data sources

The source data are published separately on Zenodo:

- [A Reproducible Cross-National Dataset of Public Student Visa and Study Permit Statistics](https://doi.org/10.5281/zenodo.21453632) — data paper;
- [Country-to-Visa: A Cross-National Dataset of Public Student Visa and Study Permit Statistics](https://doi.org/10.5281/zenodo.21446641) — data artifact.

The raw archive and extracted source tables are intentionally not committed to this repository. [data/README.md](data/README.md) records the source files, checksums, selective extraction commands, field meanings, filters, harmonization procedure, and validation totals.

## Repository structure

| Path | Contents |
| --- | --- |
| [`article/`](article/) | Manuscript, bibliography, compiled PDF, and publication tables and figures |
| [`data/`](data/) | Data documentation, schemas, reviewed mappings, audits, prepared-data layout, and result manifests |
| [`scripts/`](scripts/) | Source preparation, article-only publication generators, and the end-to-end reproduction command |
| [`src/`](src/) | Dependency-ordered statistical analysis modules |
| [`tests/`](tests/) | Unit, contract, regression, publication-output, and pipeline tests |
| [`AU_NZ_visa_comparison_methods.md`](AU_NZ_visa_comparison_methods.md) | Human-readable statistical protocol and interpretation boundaries |
| [`process_log.json`](process_log.json) | Chronological record of material project milestones and verification evidence |

## Requirements

- Python 3.10 or later. The Python pipeline uses the standard library.
- R with `Rscript`. The grouped-binomial models use base R.
- `curl` and `unzip` to retrieve and selectively extract the Zenodo inputs.
- A TeX distribution with `latexmk`, BibTeX, and PGFPlots to rebuild the manuscript.

## Reproducing the analysis

Run commands from the repository root.

1. Download and selectively extract the source data using the commands and checksums in [data/README.md](data/README.md).

2. Reproduce the prepared data, statistical results, article tables and figures, test suite, and PDF:

```sh
python3 scripts/reproduce_article.py --run-tests --build-pdf
```

The reproduction command checks that the selectively extracted inputs exist, prepares both destinations, harmonizes annual origin names, runs the dependency-ordered analyses, regenerates exactly the publication artifacts imported by the manuscript, optionally runs all tests, and optionally compiles the PDF. It stops immediately if a source, validation gate, analysis, artifact hash, test, or LaTeX build fails.

To reuse already prepared source tables while regenerating the results and manuscript artifacts:

```sh
python3 scripts/reproduce_article.py --skip-preparation
```

The individual preparation, analysis, and publication-generation commands are documented in [scripts/README.md](scripts/README.md). The complete test suite can also be run separately:

```sh
python3 -m unittest discover -s tests
```

More detailed module contracts and outputs are documented in [src/README.md](src/README.md) and [tests/README.md](tests/README.md).

## Building the manuscript

After the analysis and publication artifacts are available:

```sh
cd article
latexmk -pdf -interaction=nonstopmode -halt-on-error article.tex
```

The committed PDF is provided for convenient reading. Generated LaTeX auxiliary files are excluded from version control.

## Reproducibility and provenance

The project keeps preparation, analysis, validation, and publication formatting separate:

- immutable source downloads and large extracted tables remain local and are recreated from the published Zenodo records;
- `scripts/` prepares and harmonizes source data;
- `src/` contains the statistical calculations;
- `data/results/manifests/` records input and output hashes, validation status, software versions, and pipeline order;
- `process_log.json` records the material source, preparation, analysis, manuscript, and publication milestones; and
- `article/tables/` and `article/figures/` contain publication-format selections generated from verified results.

Generated prepared and result CSV files are excluded from Git because they are reproducible outputs. Small schemas, reviewed mappings, audit records, manifests, publication artifacts, source code, tests, and the manuscript remain part of the repository.

## License and citation

The repository includes an [MIT License](LICENSE) for its software and associated documentation. The upstream Zenodo data artifact is distributed under CC BY 4.0; consult its record for attribution requirements. If the manuscript requires separate publication terms, state them before its formal release.

The comparison article uses the reserved Zenodo preprint DOI [10.5281/zenodo.23739706](https://doi.org/10.5281/zenodo.23739706). Cite the separate data paper and data artifact above when using their data.
