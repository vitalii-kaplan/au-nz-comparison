# Data Sources and Extraction Plan

This project uses the published Country-to-Visa data paper and its separate Zenodo data artifact:

- Data paper: [A Reproducible Cross-National Dataset of Public Student Visa and Study Permit Statistics](https://doi.org/10.5281/zenodo.21453632)
- Dataset: [Country-to-Visa: A Cross-National Dataset of Public Student Visa and Study Permit Statistics](https://doi.org/10.5281/zenodo.21446641)

The two records have different roles. Record `21453632` contains the explanatory paper. Record `21446641` contains the data archive used by this project.

## Downloaded release

The files were downloaded from Zenodo on 26 September 2026.

| Record | Local file | Bytes | Published MD5 |
| --- | --- | ---: | --- |
| `21453632` | `original/zenodo/Reproducible-Cross-National-Dataset.pdf` | 363,333 | `bba6ab4c9096904d5ff664d2c7ec89ac` |
| `21446641` | `original/zenodo/data.zip` | 672,630,395 | `f82c8b153099fd1a19cdf4fb20f58ab6` |

Both downloaded files were checked successfully against the MD5 values returned by the Zenodo records API. The API responses are preserved locally as `original/zenodo/record-21453632.json` and `original/zenodo/record-21446641.json`.

These large downloaded files and extracted tables are intentionally ignored by Git. They remain local immutable inputs and can be recreated with the commands below.

## Archive structure

The dataset archive expands to approximately 13.96 GB and contains:

```text
data/
  README.md
  RETRIEVAL.md
  country-schema.json
  country_aliases.csv
  UNSD — Methodology.csv
  csv/
    australia/
    canada/
    new-zealand/
    united-kingdom/
    united-states/
  original/
    <preserved official source files by destination>
  student_visa_common_long.csv
  student_visa.sqlite
```

`student_visa_common_long.csv` is a 30-field, cross-country long table and `student_visa.sqlite` is its query-oriented database representation. They are useful for general cross-national queries, but they are very large: approximately 5.18 GB and 7.70 GB uncompressed. This project does not need to unpack them for the initial Australia–New Zealand analysis.

The smaller source-level country CSVs preserve the fields required here. The recommended input is the Australian decision-based grant-rate table plus the four New Zealand annual decision tables.

## Reproduce the download

Run from the repository root:

```sh
mkdir -p data/original/zenodo

curl -L --fail \
  'https://zenodo.org/api/records/21446641/files/data.zip/content' \
  -o data/original/zenodo/data.zip

curl -L --fail \
  'https://zenodo.org/api/records/21453632/files/Reproducible%20Cross-National%20Dataset.pdf/content' \
  -o data/original/zenodo/Reproducible-Cross-National-Dataset.pdf

md5 data/original/zenodo/data.zip \
  data/original/zenodo/Reproducible-Cross-National-Dataset.pdf
```

Expected MD5 values are listed above. Stop if either checksum differs.

## Extract only the required files

The following selective extraction avoids expanding the multi-gigabyte common table and database:

```sh
mkdir -p \
  data/original/australia \
  data/original/new-zealand \
  data/original/zenodo/artifact-metadata

unzip -j -o data/original/zenodo/data.zip \
  'data/csv/australia/student_visa_grant_rates_2005_2026-02-28.csv' \
  -d data/original/australia

unzip -j -o data/original/zenodo/data.zip \
  'data/csv/new-zealand/student_visa_decisions_*.csv' \
  -d data/original/new-zealand

unzip -j -o data/original/zenodo/data.zip \
  'data/README.md' \
  'data/RETRIEVAL.md' \
  'data/country-schema.json' \
  'data/country_aliases.csv' \
  'data/UNSD*' \
  -d data/original/zenodo/artifact-metadata
```

The extracted Australian filename contains `2026-02-28`, but the artifact metadata identifies the file contents as the 30 April 2026 snapshot. The final financial-year label is `2025-26 to 30 April 2026`. Preserve the upstream filename and record the actual snapshot date separately.

## Reproduce the article from the extracted inputs

After the selective extraction succeeds and the checksums match, return to the repository root and run:

```sh
python3 scripts/reproduce_article.py --run-tests --build-pdf
```

This command prepares and harmonizes the source tables, executes the statistical pipeline in dependency order, regenerates every table and figure imported by the manuscript, runs the test suite, and rebuilds `article/article.pdf`. It stops on the first missing input, validation failure, stale artifact hash, failed test, or LaTeX error.

## Selected input files

### Australia

`original/australia/student_visa_grant_rates_2005_2026-02-28.csv` contains 2,046,442 data rows with these fields:

```text
financial_year_of_decision
financial_year_quarter
month
client_location
lodgement_channel
sector
applicant_type
education_provider_registered_state
gender
citizenship_country
age_group
grant_total
refused_total
total
computed_grant_rate
```

Each row is an aggregate cell across the listed dimensions, not an individual application. The inspected table has two client-location values (`In Australia`, `Outside Australia`) and two applicant types (`Primary`, `Secondary`). All 2,046,442 source rows satisfy:

```text
grant_total + refused_total = total
```

The decision-based rate is:

```text
computed_grant_rate = grant_total / (grant_total + refused_total)
```

It is not grants divided by lodged applications.

### New Zealand

The four files under `original/new-zealand/` contain one annual row per published country, territory, or special administrative region.

- 2022 contains year, origin label, approvals, declines, and decline rate.
- 2023–2025 additionally contain application volume and approval rate.
- Application volume is absent in 2022.
- In 2023–2025, application volume can differ from approvals plus declines because not every application is represented by a completed approval or decline in the same published table.
- The 2023–2025 CSVs contain a final `Total` row. It is an aggregate, not an origin, and must be excluded before summing or normalizing country rows.

For a comparable decision-rate analysis, calculate the New Zealand denominator as `number_approved + number_declined`. Preserve the official application-volume field separately; do not overwrite it or call the decision total an application total.

## Prepare the New Zealand annual and combined tables

Run from the repository root:

```sh
python3 scripts/prepare_new_zealand.py
```

The script reads the four immutable annual files under `original/new-zealand/`, validates their years and required fields, excludes the published aggregate `Total` rows, and derives the decision total and approval rate defined by `schema.json` for every source-label country row. It writes four annual source-label tables and then sums those annual tables into the compatibility combined table:

- `prepared/new-zealand/student_visa_decisions_2022.csv` through `student_visa_decisions_2025.csv`;
- `prepared/new-zealand/inz_student_visa_decisions_2022-2025.csv`; and
- `support/new-zealand-reference-comparison.json`.

The comparison report verifies that the combined counts equal the sum of the four annual prepared tables. It also checks the five retained combined columns against the previous article fixture at `tests/data/inz_student_visa_decisions_2022-2025.csv`, including column order, country order, row count, integer counts, and approval rates. The reference-only `Applications_log10` column is intentionally ignored: it is derived entirely from the decision total and is not part of this project's prepared table. The regression test in `tests/test_prepare_new_zealand.py` independently runs the preparation script in a temporary directory and repeats this semantic comparison.

## Prepare the Australian annual and combined tables

Run from the repository root:

```sh
python3 scripts/prepare_australia.py
```

The script reads the preserved Australian grant-rate source, applies the documented population filters, reconstructs calendar years, produces four intermediate annual tables and one combined 2022--2025 table, and writes a machine-readable audit to `support/australia-preparation-audit.json`.

### 1. Select the comparable Australian population

From the Australian grant-rate CSV:

1. retain `client_location = Outside Australia`;
2. retain `applicant_type = Primary`;
3. retain `sector = Higher Education Sector`;
4. retain the source grant, refusal, and decision counts;
5. retain the original citizenship label for auditability; and
6. do not join lodgement counts to decision rows as though they represented the same cohort.

`Postgraduate Research Sector` is a separate source category and is not included by the Higher Education Sector filter. The prepared Australian population therefore follows the user's selected sector literally.

The remaining dimensions—lodgement channel, sector, provider state, gender, and age group—contain mutually exclusive category values in the inspected release rather than `All` or `Total` rows. They can therefore be summed when constructing country-period totals, subject to conservation and duplicate-key checks.

### 2. Convert Australian financial periods to calendar years

Australia labels months within a July–June financial year:

- `M01 Jul` through `M06 Dec` belong to the starting year in `financial_year_of_decision`;
- `M07 Jan` through `M12 Jun` belong to the following calendar year.

For example, July–December in `2022-23` map to calendar year 2022, while January–June map to 2023. After this conversion, retain calendar years 2022–2025 for the initial comparison with New Zealand.

Do not relabel an Australian financial year as a New Zealand calendar year.

### 3. Aggregate Australian decisions

Group the filtered Australian rows by derived calendar year and citizenship country. Sum:

```text
granted_or_approved = sum(grant_total)
refused_or_declined = sum(refused_total)
decision_total = sum(total)
decision_grant_rate = granted_or_approved / decision_total
```

Recalculate the rate from aggregated counts. Do not average `computed_grant_rate` across source rows.

### 4. Write and validate Australian outputs

Every output uses the five fields in `schema.json`. Australian grants map to `Number approved`, refusals map to `Number declined`, and the legacy `Total applications` field is grants plus refusals. Rates are recalculated after aggregation.

| Calendar year | Selected source rows | Country labels | Grants | Refusals | Decisions |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 2022 | 16,398 | 166 | 143,885 | 17,993 | 161,878 |
| 2023 | 16,732 | 168 | 188,588 | 42,578 | 231,166 |
| 2024 | 14,924 | 163 | 162,405 | 22,998 | 185,403 |
| 2025 | 14,617 | 172 | 144,201 | 14,804 | 159,005 |
| **2022--2025** | **62,671** | **194 distinct** | **639,079** | **98,373** | **737,452** |

The generated files are:

```text
prepared/australia/student_visa_decisions_2022.csv
prepared/australia/student_visa_decisions_2023.csv
prepared/australia/student_visa_decisions_2024.csv
prepared/australia/student_visa_decisions_2025.csv
prepared/australia/student_visa_decisions_2022-2025.csv
support/australia-preparation-audit.json
```

The audit records the filter funnel, source checksum, financial years and months used for each calendar year, row and country counts, sums, output checksums, and validation results. It verifies all 2,046,442 source rows satisfy `grant_total + refused_total = total`, source grant rates reconcile, annual aggregation conserves counts, and the combined table equals the sum of the annual tables.

Country labels remain in their Australian source form at this stage. In particular, `Not Specified` is preserved rather than silently treated as a country; it must be classified and excluded or otherwise handled during the later origin-harmonization step.

## UN M49 reference and country-name harmonization

The official English UN M49 overview was downloaded from the United Nations Statistics Division on 26 September 2026:

```text
https://unstats.un.org/unsd/methodology/m49/overview/
```

The source page is preserved as `original/reference/un-m49-overview.html`. Because the website's CSV button is generated in the browser rather than exposed as a stable file URL, `scripts/extract_un_m49.py` reproducibly extracts its embedded English table to `original/reference/un-m49.csv`. The extracted table contains 248 unique country-or-area names and M49 codes.

```sh
python3 scripts/extract_un_m49.py
python3 scripts/check_country_names.py
```

The second script checks each of the four annual tables for each destination. Within every year it first accepts exact English M49 names, then applies a destination-specific reviewed alias and finally a generic reviewed alias from `reference/country_aliases.csv`. Labels resolving to the same M49 name within a year are aggregated and their rates recalculated. The reviewed non-M49 labels Taiwan and Kosovo are retained unchanged with status `non_m49_retained` and a null M49 code. Unknown, aggregate, and unmatched labels are excluded from normalized annual outputs but retained with their year, decision count, and reason in `support/country-name-harmonization.json`.

Only after annual harmonization does the script sum the four normalized annual tables by destination and normalized country name. It recalculates the combined decision rates from the summed counts and verifies that the combined counts equal the annual normalized totals. Thus, the pooled tables are derived from the country-year data used by the temporal analysis rather than normalized independently.

The normalized five-column outputs are:

```text
prepared/new-zealand/student_visa_decisions_2022-m49.csv
prepared/new-zealand/student_visa_decisions_2023-m49.csv
prepared/new-zealand/student_visa_decisions_2024-m49.csv
prepared/new-zealand/student_visa_decisions_2025-m49.csv
prepared/new-zealand/student_visa_decisions_2022-2025-m49.csv
prepared/australia/student_visa_decisions_2022-m49.csv
prepared/australia/student_visa_decisions_2023-m49.csv
prepared/australia/student_visa_decisions_2024-m49.csv
prepared/australia/student_visa_decisions_2025-m49.csv
prepared/australia/student_visa_decisions_2022-2025-m49.csv
```

Annual normalization produces 149, 157, 151, and 155 New Zealand rows for 2022--2025, respectively, with no excluded decisions. It produces 164, 167, 162, and 171 Australian rows, excluding 11, 10, 4, and 3 non-country decisions, respectively. Across all years the excluded Australian decisions comprise `Not Specified` (27) and `Refugee` (1).

The New Zealand output has 179 names: 178 exact M49 names plus Taiwan. The Australian output has 192 names: 190 exact M49 names plus Taiwan and Kosovo. There are 173 shared output names, comprising 172 exact M49 names and Taiwan. Apart from the explicitly reviewed Taiwan and Kosovo exceptions, every retained `Country` value is an exact name from the downloaded M49 table. Different coverage does not indicate a naming mismatch.

The non-M49 handling is explicit:

- New Zealand retains `Taiwan` unchanged (1,094 decisions).
- Australia retains `Taiwan` unchanged (5,811 decisions) and `Kosovo` unchanged (8 decisions).
- Australia excludes `Not Specified` (27 decisions) and `Refugee` (1 decision), because neither label identifies a country or area.

The retained exceptions have no separate country-or-area records in the downloaded M49 reference and therefore have null M49 codes in the audit. They are not presented as official M49 names.

Reference checksums for this snapshot are:

| File | SHA-256 |
| --- | --- |
| `original/reference/un-m49-overview.html` | `b9048114f6e7f2abda83bf03d4263c9d7cd1bd7230e3d0461025ee7839a7a1fb` |
| `original/reference/un-m49.csv` | `b0ed5587787b027786005d153c92b6ba87b6fafcfb218b2e7921d323f931f1e7` |
| `reference/country_aliases.csv` | `232a0852e21333c9da19a9bf77d162d84d2e1ce4387cccfd5368111abb9b5f76` |

### 5. Normalize origins

Use `original/reference/un-m49.csv` as the current downloaded UN M49 reference and `reference/country_aliases.csv` as the reviewed alias table.

1. retain the year and original Australian or NZ origin label;
2. try an exact UN M49 match independently within each annual table;
3. apply a destination-specific alias before a generic alias;
4. retain `matched`, `alias_matched`, `non_m49_retained`, `aggregate`, `unknown`, or `unmatched` status;
5. retain Taiwan and Kosovo unchanged as the reviewed `non_m49_retained` exceptions;
6. exclude aggregate, unknown, and unmatched labels while reporting them by year in the audit; and
7. sum the four normalized annual tables to create each destination's combined table.

### 6. Produce the canonical comparison tables

The implemented pooled and country-year long tables contain destination code and name, normalized country, approved or granted count, declined or refused count, decision total, recalculated approval rate, and period or calendar year. Their matched counterparts place AU and NZ counts and rates on one row and define the rate difference as AU minus NZ.

Source labels, normalization statuses, administrative scope, source snapshots, and file provenance remain in the preparation audits, harmonization audit, input registry, and analysis manifests rather than being duplicated into every analytical row. This keeps the numerical tables compact without losing traceability.

The first implemented analysis stages now formalize the contract and construct the canonical comparison tables:

```sh
python3 -m src.analysis_01_define_contract
python3 -m src.analysis_02_build_tables
python3 -m src.analysis_05_concordance
python3 -m src.analysis_06_country_differences
```

Reusable joined tables are stored under `prepared/comparison/`. Validation and coverage tables are stored under `results/validation/`, while input/output hashes and run summaries are stored under `results/manifests/`. See the README files in those directories for the artifact roles. Statistical result tables should not be mixed with prepared comparison data or validation evidence.

The concordance outputs are stored under `results/concordance/`: a two-row Pearson/Spearman result table, the complete matched plotting points, and calculation diagnostics. Country-specific outputs are stored under `results/country_tests/`: the authoritative 173-country effect-and-test table, a compact test-family summary, and a separate table that records the fixed forest-plot display rule. These are result artifacts derived from the canonical comparison table; they are not prepared input data.

Store country-specific prepared tables under `prepared/australia/` and `prepared/new-zealand/`, then place the aligned table under `prepared/comparison/`.

## Broader pre-filter audit values for the selected release

The Australian values below were calculated before the Higher Education Sector restriction was selected. They apply only the outside-Australia and primary-applicant filters and are retained as broader extraction sanity checks, not as the current prepared outputs or article results. The current sector-specific values are reported above and in `support/australia-preparation-audit.json`.

For Australia after filtering to outside-Australia primary applicants and reconstructing calendar years:

| Calendar year | Detailed rows | Citizenship labels | Grants | Refusals | Decisions |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 2022 | 44,254 | 193 | 251,386 | 51,258 | 302,644 |
| 2023 | 46,839 | 198 | 300,140 | 76,052 | 376,192 |
| 2024 | 39,952 | 192 | 227,465 | 44,285 | 271,750 |
| 2025 | 38,431 | 196 | 200,767 | 28,359 | 229,126 |

For New Zealand before country normalization and after excluding the aggregate `Total` row:

| Calendar year | Origin rows | Approvals | Declines | Decisions | Official application volume |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 2022 | 149 | 16,311 | 1,702 | 18,013 | unavailable |
| 2023 | 157 | 32,749 | 7,711 | 40,460 | 40,922 |
| 2024 | 151 | 36,892 | 11,881 | 48,773 | 49,336 |
| 2025 | 155 | 35,013 | 6,487 | 41,500 | 41,951 |

The published `Total` rows report approvals and declines of 32,706 and 7,689 for 2023, 36,892 and 11,871 for 2024, and 35,013 and 6,487 for 2025. These values do not always equal the sum of the displayed origin rows. Future extraction code should reproduce and audit the detail-row sums and the published aggregate rows separately; it must never add a `Total` row to its components.

## Provenance and checksums for selected tables

| Extracted file | MD5 |
| --- | --- |
| `australia/student_visa_grant_rates_2005_2026-02-28.csv` | `0c41e436e901a0655b8e84d215be4fe7` |
| `new-zealand/student_visa_decisions_2022.csv` | `c3e83ecad45390ca33edecf444778f83` |
| `new-zealand/student_visa_decisions_2023.csv` | `4bcd5fc8559593e2a8505ef3835aa7fa` |
| `new-zealand/student_visa_decisions_2024.csv` | `2fe33e032f0c681b2652889bb1975312` |
| `new-zealand/student_visa_decisions_2025.csv` | `053dcfd87182874310ff9b46b41cc0a9` |
| `zenodo/artifact-metadata/country_aliases.csv` | `4073092ffd1ac8f30742ea091dedbcca` |
| `zenodo/artifact-metadata/country-schema.json` | `6f6f40bcd8493f286022dad813d75abb` |
| `zenodo/artifact-metadata/UNSD — Methodology.csv` | `96bbad1f90cea25a1fae6ac268260bd3` |
