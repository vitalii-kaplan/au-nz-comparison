# Verified statistical references and recommendations — AU/NZ visa comparison

**Scope:** Statistical references for the 15 methods used in the AU/NZ visa-decision study. No external country predictors or gravity models.

**Verification:** Authors, titles, journal metadata and DOI identities checked against publisher/journal or established bibliographic pages on 20 October 2026. Full paywalled articles were not necessarily read. Citations support methods, not claims of causation or of optimality for your particular data.

## References, method by method

### 1. Wilcoxon signed-rank

Wilcoxon, F. (1945). Individual comparisons by ranking methods. Biometrics Bulletin, 1(6), 80–83. [DOI](https://doi.org/10.2307/3001968)

**Why cite / caution:** Original test; explicitly specify Wilcox zeros, ties, normal approximation and continuity correction.

### 2. Bootstrap

Efron, B. (1979). Bootstrap methods: Another look at the jackknife. The Annals of Statistics, 7(1), 1–26. [DOI](https://doi.org/10.1214/aos/1176344552)

**Why cite / caution:** Resample complete paired countries for Spearman and differences for the median. 10,000 resamples and seed are implementation choices.

### 3. Bootstrap interval limitations

Efron, B. (1987). Better bootstrap confidence intervals. Journal of the American Statistical Association, 82(397), 171–185. [DOI](https://doi.org/10.1080/01621459.1987.10478410)

**Why cite / caution:** Explains refinements to basic bootstrap CIs; do not claim percentile CIs have guaranteed coverage.

### 4. Type-7 quantiles

Hyndman, R. J., & Fan, Y. (1996). Sample quantiles in statistical packages. The American Statistician, 50(4), 361–365. [DOI](https://doi.org/10.1080/00031305.1996.10473566)

**Why cite / caution:** Computational definition for quartiles and bootstrap endpoints, not separate inference.

### 5. Newcombe hybrid-score

Newcombe, R. G. (1998). Interval estimation for the difference between independent proportions: Comparison of eleven methods. Statistics in Medicine, 17(8), 873–890. [DOI](https://doi.org/10.1002/(SICI)1097-0258(19980430)17:8%3C873::AID-SIM779%3E3.0.CO;2-I)

**Why cite / caution:** Use separate Wilson intervals and hybrid combination; assumes independent binomial samples.

### 6. Chi-square/Fisher rule

Campbell, I. (2007). Chi-squared and Fisher–Irwin tests of two-by-two tables with small sample recommendations. Statistics in Medicine, 26(19), 3661–3675. [DOI](https://doi.org/10.1002/sim.2832)

**Why cite / caution:** Discusses the expected-count-five convention but critiques it and recommends alternatives. Cite as contextual analysis, NOT endorsement.

### 7. Zero-cell correction

Gart, J. J., & Zweifel, J. R. (1967). On the bias of various estimators of the logit and its variance with application to quantal bioassay. Biometrika, 54(1–2), 181–187. [DOI](https://doi.org/10.1093/biomet/54.1-2.181)

**Why cite / caution:** Background on corrected logit/odds estimators. Define exactly when 0.5 is added.

### 8. Continuity-correction limitations

Sweeting, M. J., Sutton, A. J., & Lambert, P. C. (2004). What to add to nothing? Use and avoidance of continuity corrections in meta-analysis of sparse data. Statistics in Medicine, 23(9), 1351–1375. [DOI](https://doi.org/10.1002/sim.1761)

**Why cite / caution:** Applied methodological comparison: fixed 0.5 corrections can distort sparse/unbalanced results.

### 9. BH FDR

Benjamini, Y., & Hochberg, Y. (1995). Controlling the false discovery rate: A practical and powerful approach to multiple testing. Journal of the Royal Statistical Society: Series B (Methodological), 57(1), 289–300. [DOI](https://doi.org/10.1111/j.2517-6161.1995.tb02031.x)

**Why cite / caution:** Apply to the family of country tests (173 only if all 173 valid); report raw p and adjusted q.

### 10. Grouped binomial GLM

Nelder, J. A., & Wedderburn, R. W. M. (1972). Generalized linear models. Journal of the Royal Statistical Society: Series A (General), 135(3), 370–384. [DOI](https://doi.org/10.2307/2344614)

**Why cite / caution:** Primary foundation for binomial-logit GLM. State country fixed effects and reference destination.

### 11. Separation

Albert, A., & Anderson, J. A. (1984). On the existence of maximum likelihood estimates in logistic regression models. Biometrika, 71(1), 1–10. [DOI](https://doi.org/10.1093/biomet/71.1.1)

**Why cite / caution:** Explains nonfinite estimates under separation; do not say all invariant-outcome groups must always be excluded.

### 12. Cluster-robust CR1

Cameron, A. C., & Miller, D. L. (2015). A practitioner's guide to cluster-robust inference. Journal of Human Resources, 50(2), 317–372. [DOI](https://doi.org/10.3368/jhr.50.2.317)

**Why cite / caution:** Report exact CR1 finite-sample factor, cluster count, and inference distribution.

### 13. Correlated GLMs

Liang, K.-Y., & Zeger, S. L. (1986). Longitudinal data analysis using generalized linear models. Biometrika, 73(1), 13–22. [DOI](https://doi.org/10.1093/biomet/73.1.13)

**Why cite / caution:** Related foundation for correlated observations; not the main source for ordinary grouped binomial GLM.

### 14. Predictive margins

Muller, C. J., & MacLehose, R. F. (2014). Estimating predicted probabilities from logistic regression: Different methods correspond to different target populations. International Journal of Epidemiology, 43(3), 962–970. [DOI](https://doi.org/10.1093/ije/dyu029)

**Why cite / caution:** Applied example of standardization. Equal averaging over countries is NOT applicant weighting.

### 15. Delta method

Oehlert, G. W. (1992). A note on the delta method. The American Statistician, 46(1), 27–29. [DOI](https://doi.org/10.1080/00031305.1992.10475842)

**Why cite / caution:** Use gradient and full fitted coefficient covariance for standardized probability difference.

### 16. Overdispersion

Williams, D. A. (1982). Extra-binomial variation in logistic linear models. Journal of the Royal Statistical Society: Series C (Applied Statistics), 31(2), 144–148. [DOI](https://doi.org/10.2307/2347977)

**Why cite / caution:** Pearson chi-square/residual df is a diagnostic, not a definitive test of a particular mechanism.

### 17. Influence

Pregibon, D. (1981). Logistic regression diagnostics. The Annals of Statistics, 9(4), 705–724. [DOI](https://doi.org/10.1214/aos/1176345513)

**Why cite / caution:** Cook-type influence for binomial regression; consider deletion by country as well as individual rows.

## Study-specific denominator thresholds (method 15)

The thresholds 0, 20, 50, 100 decisions **in each destination** are pre-specified robustness checks, not universally prescribed values. Campbell (2007) is relevant to sparse 2×2 tables, but does not justify these particular cutoffs. Report retained country counts and changes in estimates at every threshold.

## How the 15 items map to references

| Item | Reference(s) |

|---|---|

1 Wilcoxon — Wilcoxon (1945); 2 bootstrap — Efron (1979, 1987); 3 quantiles — Hyndman & Fan (1996); 4 Newcombe — Newcombe (1998); 5 chi-square/Fisher — Campbell (2007); 6 Haldane–Anscombe — Gart & Zweifel (1967), Sweeting et al. (2004); 7 FDR — Benjamini & Hochberg (1995); 8 grouped GLM — Nelder & Wedderburn (1972); 9 separation — Albert & Anderson (1984); 10 CR1 — Cameron & Miller (2015), Liang & Zeger (1986); 11 margins — Muller & MacLehose (2014); 12 delta — Oehlert (1992); 13 overdispersion — Williams (1982); 14 influence — Pregibon (1981); 15 denominator thresholds — study-specific, Campbell (2007) as context.

## Suggested Methods language

> Paired approval-rate differences were evaluated using a two-sided Wilcoxon signed-rank test (Wilcoxon, 1945), with the Wilcox zero convention, tie-adjusted normal approximation, and continuity correction. Percentile bootstrap intervals for the median difference and Spearman correlation were estimated from 10,000 resamples (Efron, 1979) using type-7 quantiles (Hyndman and Fan, 1996). Country-specific independent proportion differences were summarized using Newcombe hybrid-score intervals (Newcombe, 1998). Pearson chi-square tests were applied when all expected 2×2 cell counts were at least five, and Fisher exact tests otherwise; this conventional cutoff was specified in advance, while acknowledging alternatives (Campbell, 2007). Country-specific p-values were adjusted using Benjamini–Hochberg FDR (Benjamini and Hochberg, 1995).

> A grouped binomial logistic regression included a destination indicator and origin-country fixed effects (Nelder and Wedderburn, 1972). Separation was assessed (Albert and Anderson, 1984). Cluster-robust standard errors were calculated by origin country (Cameron and Miller, 2015). Predictive margins were standardized by equally averaging predictions over retained origin countries (Muller and MacLehose, 2014), with delta-method uncertainty (Oehlert, 1992). Extra-binomial variation and influential observations were examined (Williams, 1982; Pregibon, 1981). Pre-specified minimum-denominator sensitivity analyses assessed stability.

**IMPORTANT:** Do not paste the sample paragraphs until they match your actual code, including retained sample, number of country tests, zero/tie conventions, year effects, CR1 factor, and model diagnostics.

## Implementation and interpretation cautions

- Campbell (2007) explicitly questions the expected-count-of-five rule; it does not prove that threshold optimal.

- The 0.5 zero-cell correction is pragmatic and can bias sparse, imbalanced comparisons.

- Individual Newcombe 95% intervals are not FDR-adjusted simultaneous intervals.

- Complete separation and outcome-invariant groups depend on estimator details; record exactly which groups are retained.

- CR1 requires explicit finite-sample factor and degrees-of-freedom specification.

- Equal-country standardization targets the equally weighted retained-country population, not the typical applicant.

- Bootstrap resampling for Spearman must preserve AU/NZ pairs.

- Report effect sizes, CIs, distributions, and denominators alongside p-values.

- Avoid causal claims about AU vs NZ decision systems from aggregate observational data.

## Verified source pages

- [Hyndman–Fan institutional record](https://research.monash.edu/en/publications/sample-quantiles-in-statistical-packages/)

- [Newcombe PubMed](https://pubmed.ncbi.nlm.nih.gov/9595617/)

- [Campbell PubMed](https://pubmed.ncbi.nlm.nih.gov/17315184/)

- [Sweeting et al. PubMed](https://pubmed.ncbi.nlm.nih.gov/15116347/)

- [Muller–MacLehose full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC4052139/)

- [Cameron–Miller publisher](https://doi.org/10.3368/jhr.50.2.317)

- [Albert–Anderson publisher](https://doi.org/10.1093/biomet/71.1.1)

- [Nelder–Wedderburn publisher](https://doi.org/10.2307/2344614)

## Codex instruction

Treat this file as a citation and methodological-justification reference, not an instruction to change the analysis. Verify that each implemented procedure matches its cited method; distinguish published statistical foundations from software conventions and study-specific choices. Flag discrepancies rather than silently rewriting the methods.