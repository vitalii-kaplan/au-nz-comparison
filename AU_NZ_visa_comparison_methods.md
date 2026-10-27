# Statistical Methods Specification: Australia--New Zealand Visa-Decision Comparison

This document records the statistical protocol for a comparative study
of Australian (AU) and New Zealand (NZ) visa-decision data for
2022--2025. It is the human-readable methodology and the original
implementation specification for the analysis scripts.

## Status and authority

All Sections 1--15 are implemented and verified. `src/README.md` is the
authoritative map from these methods to the current modules, tests, and
artifacts. Run manifests under `data/results/manifests/` are authoritative
for executed inputs, outputs, configuration, and hashes. This document
remains the concise statement of methodological intent and interpretation
boundaries.

The specification supports the repository's complete analysis record. The
active manuscript uses the pooled matched-origin comparisons. Composition,
annual, and country-year analyses remain verified supporting outputs but are
not substantive contributions of the active manuscript. The sections below
describe the analysis record rather than the manuscript outline.

The study uses **only the two normalized AU and NZ datasets**. Do not
add external country characteristics, regional explanatory variables,
gravity models, or machine-learning predictors.

"Comparison" is divided into distinct questions:

1.  What are the overall scale and distributions of the datasets?
2.  For the same origin countries, are approval rates systematically
    different?
3.  Do AU and NZ show similar cross-country approval patterns?
4.  Which individual countries show evidence of different approval
    proportions?
5.  Is there an overall destination difference after accounting for
    origin country and year?
6.  Do AU and NZ differ in the composition and concentration of
    applicant origins?
7.  Are differences stable across 2022--2025?

**Presentation principle:** whenever a mean, median, aggregate rate,
correlation, or concentration statistic summarizes heterogeneous country
data, also show an appropriate distribution or relationship plot where
feasible.

## 1. Units, notation, and estimands

Let (i) denote origin country, (j) destination (AU/NZ), and (t) year.
Let (A\_{ijt}) be approvals, (D\_{ijt}) declines/refusals, (N\_{ijt})
total observed decisions, and (p\_{ijt}=A\_{ijt}/N\_{ijt}) the approval
proportion.

If source definitions permit, verify (N=A+D). Do not silently
reconstruct totals if other decision categories exist.

Keep three perspectives distinct:

-   **Decision-weighted:** large origin countries contribute more;
    describes the typical recorded decision.
-   **Country-weighted:** every country contributes once; describes the
    typical origin country.
-   **Country-year:** every `(country, year)` observation contributes;
    supports temporal analysis.

These answer different questions and must not be mixed in
interpretation.

## 2. Data validation and derived tables

Before analysis, verify schemas, key uniqueness, duplicates,
non-negative integer counts, rates in \[0,1\], count/rate consistency,
missingness, year coverage, countries unique to each destination, common
countries, and small denominators. Never silently discard records;
export an issue/exclusion table.

The pipeline creates the following derived tables.

### Country aggregates

Aggregate 2022--2025 by destination and country:

\[
A_{ij}=\sum_t A_{ijt},\quad D_{ij}=\sum_t D_{ijt},\quad
N_{ij}=\sum_t N_{ijt},\quad p_{ij}=A_{ij}/N_{ij}.
\]

### Matched-country table

Inner-join AU and NZ on normalized country name. Define:

\[
\Delta_i=p_{i,\mathrm{AU}}-p_{i,\mathrm{NZ}}.
\]

Always use positive = AU higher; negative = NZ higher.

### Matched country-year table

Inner-join the validated annual observations on `(country, year)`.

## 3. Descriptive comparison

### Question

What are the scale, approval structure, and distributions of AU and NZ
data?

For each destination report represented countries, approvals, declines,
total decisions, and aggregate approval rate:

\[
P_j=\frac{\sum_i A_{ij}}{\sum_i N_{ij}}.
\]

Do **not** calculate the aggregate rate as the mean of country rates.

For country decision counts and approval rates report: n, min, Q1,
median, Q3, max, mean, SD, and IQR. Because decision volumes are
right-skewed, also use $\log_{10}(N)$ for visualization where $N>0$.

### Figures

Produce:

- an ECDF of country approval rates, AU versus NZ;
- a histogram or density plot of country approval rates;
- an ECDF or histogram of decision counts on a log10 scale; and
- optional box or violin plots.

Do not interpret a higher aggregate rate as proving one destination is
"easier"; applicant-origin composition differs.

## 4. Matched-country approval-rate comparison

### Question

For countries observed in both destinations, are country-level approval
rates systematically different?

For each common country compute $\Delta_i$. Report n, mean, median, SD,
IQR, min/max, a 95% CI for the mean, and a fixed-seed bootstrap 95% CI
for the median. Also count countries with positive, negative, and zero
differences.

### Distribution

Plot the full distribution of $\Delta_i$ with a clear zero
reference line. A histogram, ECDF, density, boxplot, or ordered dot plot
is acceptable. This plot is important because the median alone cannot
show whether the difference is broad or driven by a subset.

### Primary test: Wilcoxon signed-rank

Use a two-sided paired Wilcoxon signed-rank test unless a directional
hypothesis was specified in advance. Report statistic, p-value, usable
pair count, and handling of zero differences.

Do not describe Wilcoxon casually as simply a "test of medians"; its
interpretation depends on assumptions about the paired-difference
distribution.

### Sensitivity: paired t-test

Run the paired t-test as a sensitivity analysis:

\[
t=\frac{\bar{\Delta}}{s_\Delta/\sqrt{n}}.
\]

Treat it as sensitivity analysis and inspect the distribution first.

This section is **country-weighted**: a country with 10 decisions and
one with 100,000 each contribute one paired rate.

## 5. Cross-destination concordance

### Question

Do countries with relatively high approval in AU also tend to have
relatively high approval in NZ?

Calculate Pearson correlation:

\[
r=\operatorname{cor}(p_{\mathrm{AU}},p_{\mathrm{NZ}})
\]

and Spearman rank correlation:

\[
\rho=\operatorname{cor}\left(\operatorname{rank}(p_{\mathrm{AU}}),
\operatorname{rank}(p_{\mathrm{NZ}})\right).
\]

Report coefficients, sample sizes, p-values, a Fisher-$z$ 95% CI for
Pearson $r$, and a fixed-seed percentile-bootstrap 95% CI for Spearman
$\rho$.

### Figure

Create an AU-vs-NZ scatterplot with identical 0--1 (or 0--100%) axes and
the equality line (y=x). The equality line is not a fitted regression
line.

**Interpretation:** correlation is not agreement. High correlation can
coexist with a systematic difference in approval levels.

## 6. Country-specific differences

### Question

For which origin countries is there evidence that AU and NZ approval
proportions differ?

For each country construct a 2×2 table of destination × {approved,
declined}.

Primary effect size:

\[
RD_i=p_{\mathrm{AU},i}-p_{\mathrm{NZ},i}.
\]

Where meaningful also calculate:

\[
RR_i=p_{\mathrm{AU},i}/p_{\mathrm{NZ},i}
\]

and

\[
OR_i=\frac{A_{\mathrm{AU},i}/D_{\mathrm{AU},i}}
{A_{\mathrm{NZ},i}/D_{\mathrm{NZ},i}}.
\]

Use the Newcombe hybrid-score interval for the approval-rate difference.
Handle zero cells explicitly. When any observed cell is zero, add 0.5 to
all four cells for RR and OR estimation only, and record the correction.

Use Pearson's chi-square test without continuity correction when every
expected cell is at least five. Otherwise, use the two-sided Fisher exact
test. Record the selected test and expected cell counts for every country.

### Multiple testing

Apply Benjamini--Hochberg false-discovery-rate correction across country
tests. Store both raw p-values and adjusted q-values. Do not identify
country differences using unadjusted p\<0.05 alone.

### Small denominators

Keep small countries in descriptive results, expose denominator N, and
use exact tests where appropriate. Run pre-specified sensitivity
analyses such as $N\geq20$ and $N\geq50$ **in each destination**. Do not
choose thresholds after seeing which produces the desired result.

### Figure

Create a forest plot of rate differences with 95% CIs. If all countries
are unreadable, use a transparent display rule (e.g. minimum
denominator, largest absolute differences, or FDR-significant cases),
while exporting complete numerical results.

## 7. Binomial regression

### Question

After accounting for origin-country differences, is destination
associated with approval probability?

Use counts rather than OLS on percentages because denominators vary
substantially.

For aggregated country data:

\[
A_{ij}\sim\operatorname{Binomial}(N_{ij},p_{ij})
\]

\[
\operatorname{logit}(p_{ij})=\alpha+\beta\,\mathrm{Destination}_j+\gamma_i.
\]

Here $\gamma_i$ controls for origin-country identity. Document
the reference destination. Report beta, SE, 95% CI, p-value, odds ratio
($e^\beta$), and a model-based probability contrast if useful.

For the validated annual observations:

\[
A_{ijt}\sim\operatorname{Binomial}(N_{ijt},p_{ijt})
\]

\[
\operatorname{logit}(p_{ijt})=
\alpha+\beta\,\mathrm{Destination}_j+\gamma_i+\delta_t,
\]

where $\delta_t$ represents year effects.

For repeated country-year observations, use an appropriate dependence
treatment such as cluster-robust standard errors by origin country and
document it.

Check convergence, complete/quasi-complete separation, extreme fitted
probabilities, influential observations, overdispersion where relevant,
and all model warnings. Never suppress warnings merely to obtain output.

**Interpretation:** this is observational association, not a causal
effect of choosing AU instead of NZ.

## 8. Applicant-origin composition

### Question

Do AU and NZ have the same distribution of recorded decisions across
origin countries?

Normalize counts to destination shares:

\[
s_{ij}=\frac{N_{ij}}{\sum_i N_{ij}},\qquad \sum_i s_{ij}=1.
\]

Calculate for each destination:

- top-1, top-5, and top-10 origin shares;
- median country share;
- Herfindahl--Hirschman Index; and
- Gini coefficient.

\[
HHI_j=\sum_i s_{ij}^2.
\]

State whether HHI uses the 0--1 or 0--10,000 convention.

For matched countries calculate Spearman correlation of decision
shares and optionally Pearson correlation.

### Optional distribution distance

Jensen--Shannon divergence may be calculated using the union of origin
countries only when absence genuinely means zero rather than missing or
suppressed data:

\[ M=(P+Q)/2 \]

\[
JSD(P,Q)=\frac{1}{2}D_{KL}(P\|M)+\frac{1}{2}D_{KL}(Q\|M).
\]

Specify the logarithm base. Treat JSD as a descriptive distance, not an
unsupported hypothesis test. The implemented comparability gate found
that zero-filling was not justified for these data, so the pipeline
correctly skips JSD unless future source evidence changes that finding.

### Figures

Produce ranked decision-share curves, Lorenz curves, an AU-versus-NZ
share scatterplot, and optionally a top-origin bar chart. Consider
log-scaled share plots when skew is severe, handling zeros explicitly.

## 9. Temporal comparison: 2022--2025

The annual observations passed the implemented comparability checks and
support the analyses in this section.

For each year and destination calculate total decisions,
approvals/declines, aggregate approval rate, represented countries,
median country approval rate and IQR, and median decision volume.

Use line charts for annual total decisions, aggregate approval rate,
median country approval rate, and represented-country count.

Where medians are shown, also provide annual distribution plots or
distribution summaries.

For matched countries within year define:

\[
\Delta_{it}=p_{i,\mathrm{AU},t}-p_{i,\mathrm{NZ},t}.
\]

Report annual distributions of these differences, not only annual
medians. The country-year binomial model is the primary inferential
method for separating destination and year effects.

## 10. Sensitivity analyses and inferential policy

The pre-specified sensitivity set comprises:

1.  all matched countries;
2.  $N\geq20$ in each destination;
3.  $N\geq50$ in each destination;
4.  $N\geq100$ in each destination;
5.  aggregate 2022--2025 analysis;
6.  country-year analysis;
7.  Pearson versus Spearman concordance; and
8.  Wilcoxon versus paired t-test.

Sensitivity analysis tests robustness; it is not a search for
statistical significance.

Prioritize reporting in this order:

1.  effect size;
2.  confidence interval/uncertainty;
3.  distribution/visualization;
4.  p-value.

Use percentage points for differences between approval percentages.

Example preferred reporting style:

> AU 82%, NZ 61%, difference +21 percentage points, 95% CI \[...\],
> q=...

rather than only "p\<0.05".

## 11. Missingness and comparability

Absence of a country is not automatically zero. Distinguish true zero,
missing record, suppressed data, not represented, and incompatible
source definition.

For paired approval analyses, require valid observations in both
datasets.

For composition analysis, assign zero share to an absent country only if
the data semantics establish that absence means zero. Document
assumptions and exclusions.

## 12. Reproducible implementation

The implemented modules save:

-   package/software versions;
-   input file names and cryptographic hashes;
-   analysis timestamp;
-   row counts before/after filters;
-   exclusion/validation logs;
-   random seeds for bootstrap procedures;
-   all numerical result tables;
-   publication-quality figures.

Implemented structure:

``` text
data/prepared/comparison/
data/results/
  validation/
  descriptive/
  paired/
  concordance/
  country_tests/
  models/
  composition/
  temporal/
  robustness/
  manifests/
  figures/
```

Do not manually copy calculated values into downstream
manuscript-generation code when they can be loaded from
machine-generated result files.

## 13. Required output families

The pipeline produces the following result families, except for an
optional measure that an upstream comparability gate finds ineligible.

### Tables

1.  Dataset summary by destination.
2.  Country-level descriptive statistics.
3.  Matched-country differences.
4.  Pearson/Spearman concordance.
5.  Complete country-specific effect/test table with FDR.
6.  Binomial regression results.
7.  Decision-origin concentration statistics.
8.  Annual statistics.
9.  Sensitivity-analysis summary.

### Figures

1.  AU/NZ approval-rate distributions.
2.  AU/NZ decision-volume distributions.
3.  Paired-difference distribution with zero reference.
4.  AU-vs-NZ approval-rate scatterplot with equality line.
5.  Forest plot of selected country differences.
6.  Ranked decision-share distributions.
7.  Lorenz curves.
8.  Decision-share scatterplot.
9.  Annual trend figures.

## 14. Interpretation boundaries

The scripts may calculate statistical results but should not
automatically generate causal or policy conclusions.

Permitted interpretations include:

-   observed approval rates differ;
-   country-level rates are correlated;
-   applicant-origin distributions differ in concentration;
-   an association remains after controlling for origin-country and year
    effects.

Avoid unsupported claims such as:

-   AU/NZ is "fairer";
-   one system discriminates against a nationality;
-   destination itself causally changes an individual's chance of
    approval;
-   observed national differences reveal applicant quality.

The available data describe aggregated administrative outcomes, not
comparable individual applicants or decision-making mechanisms.

## 15. Implemented analysis order

The pipeline follows this dependency-aware order:

1.  schema inspection and validation;
2.  construction of country and country-year tables;
3.  missingness and comparability gating, including the zero-filling
    decision;
4.  descriptive statistics and distributions;
5.  matched-country differences;
6.  Pearson/Spearman concordance;
7.  country-specific proportion comparisons and FDR correction;
8.  binomial regression;
9.  applicant-origin composition and concentration;
10. temporal analysis;
11. sensitivity analyses; and
12. automated result, figure, and manifest export.

Do not begin with significance testing. First understand the
distributions, denominators, overlap, and data quality.
