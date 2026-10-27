# Prepared Comparison Tables

This directory contains canonical analysis-ready tables derived from the verified annual and pooled M49-based AU and NZ inputs. They are prepared data, not statistical results.

`python3 -m src.analysis_02_build_tables` generates:

- `destination_country_2022-2025.csv` — long pooled table with one row per destination and represented country;
- `matched_country_2022-2025.csv` — common-country pooled table with AU and NZ counts, rates, and the rate difference defined as AU minus NZ;
- `destination_country_year.csv` — long panel with one row per destination-country-year; and
- `matched_country_year.csv` — common-country-year panel with AU and NZ counts, rates, and AU-minus-NZ differences.

Later descriptive, paired, concordance, model, composition, and temporal modules should read these tables rather than repeat joins against the national inputs. The generator validates the inputs and refuses to write tables when a blocking contract check fails.
