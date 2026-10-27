#!/usr/bin/env Rscript

# Base-R fitting backend for src.analysis_07_binomial_regression.
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 5) stop("usage: fit_binomial_models.R INPUT MODEL OUTPUT_DIR CONFIDENCE REFERENCE")
input_path <- args[[1]]
model_name <- args[[2]]
output_dir <- args[[3]]
confidence <- as.numeric(args[[4]])
reference <- args[[5]]
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

wide <- read.csv(input_path, check.names = FALSE, stringsAsFactors = FALSE)
annual <- identical(model_name, "country_year_fixed_effects")
required <- c("country", "au_number_approved", "au_number_declined", "nz_number_approved", "nz_number_declined")
if (annual) required <- c(required, "year")
if (!all(required %in% names(wide))) stop("input does not satisfy the matched-table contract")

make_long <- function(code, prefix) {
  data.frame(
    country = wide$country,
    year = if (annual) wide$year else "2022-2025",
    destination = code,
    approved = wide[[paste0(prefix, "_number_approved")]],
    declined = wide[[paste0(prefix, "_number_declined")]],
    stringsAsFactors = FALSE
  )
}
dat <- rbind(make_long("AU", "au"), make_long("NZ", "nz"))
totals <- aggregate(cbind(approved, declined) ~ country, dat, sum)
eligible <- totals$country[totals$approved > 0 & totals$declined > 0]
excluded <- sort(setdiff(unique(dat$country), eligible))
dat <- dat[dat$country %in% eligible, ]
dat <- dat[order(dat$country, dat$year, dat$destination), ]
dat$destination <- relevel(factor(dat$destination), ref = reference)
dat$country <- droplevels(factor(dat$country))
if (annual) dat$year <- factor(dat$year)
formula <- if (annual) cbind(approved, declined) ~ destination + country + year else cbind(approved, declined) ~ destination + country

captured_warnings <- character()
fit <- withCallingHandlers(
  glm(formula, family = binomial(link = "logit"), data = dat, control = glm.control(maxit = 100, epsilon = 1e-10)),
  warning = function(w) captured_warnings <<- c(captured_warnings, conditionMessage(w))
)
if (!isTRUE(fit$converged)) stop(paste(model_name, "did not converge"))
if (any(!is.finite(coef(fit)))) stop(paste(model_name, "has non-finite coefficients"))

X <- model.matrix(fit)
p_hat <- fitted(fit)
n_total <- dat$approved + dat$declined
information <- crossprod(X, X * as.vector(n_total * p_hat * (1 - p_hat)))
bread <- solve(information)
score <- dat$approved - n_total * p_hat
clusters <- split(seq_len(nrow(dat)), dat$country)
meat <- matrix(0, ncol(X), ncol(X))
for (indices in clusters) {
  cluster_score <- colSums(X[indices, , drop = FALSE] * score[indices])
  meat <- meat + tcrossprod(cluster_score)
}
G <- length(clusters)
correction <- (G / (G - 1)) * ((nrow(dat) - 1) / (nrow(dat) - ncol(X)))
V <- correction * bread %*% meat %*% bread
covariance_method <- "country-cluster-robust sandwich (CR1)"
se <- sqrt(diag(V))
if (any(!is.finite(se))) stop(paste(model_name, "has non-finite standard errors"))
if (any(abs(coef(fit)) > 25) || any(se > 25)) stop(paste(model_name, "has unresolved separation or unstable fixed effects"))
zcrit <- qnorm(0.5 + confidence / 2)
zvalue <- coef(fit) / se
coefficients <- data.frame(
  model = model_name, term = names(coef(fit)), estimate = unname(coef(fit)),
  standard_error = se, ci_lower = unname(coef(fit)) - zcrit * se,
  ci_upper = unname(coef(fit)) + zcrit * se,
  p_value = 2 * pnorm(-abs(zvalue)), odds_ratio = exp(unname(coef(fit))),
  odds_ratio_ci_lower = exp(unname(coef(fit)) - zcrit * se),
  odds_ratio_ci_upper = exp(unname(coef(fit)) + zcrit * se),
  covariance_method = covariance_method,
  stringsAsFactors = FALSE
)
write.csv(coefficients, file.path(output_dir, paste0(model_name, "_coefficients.csv")), row.names = FALSE, quote = TRUE)

# Standardize predictions over exactly the retained matched countries or country-years.
grid <- unique(dat[c("country", "year")])
grid$country <- factor(grid$country, levels = levels(dat$country))
if (annual) grid$year <- factor(grid$year, levels = levels(dat$year))
prediction_summary <- function(destination_code) {
  newdata <- grid
  newdata$destination <- factor(destination_code, levels = levels(dat$destination))
  design <- model.matrix(delete.response(terms(fit)), newdata)
  eta <- as.vector(design %*% coef(fit))
  probability <- plogis(eta)
  gradient <- colMeans(design * as.vector(probability * (1 - probability)))
  variance <- as.numeric(t(gradient) %*% V %*% gradient)
  list(probability = mean(probability), gradient = gradient, se = sqrt(max(0, variance)))
}
au <- prediction_summary("AU")
nz <- prediction_summary("NZ")
contrast_gradient <- au$gradient - nz$gradient
contrast_se <- sqrt(max(0, as.numeric(t(contrast_gradient) %*% V %*% contrast_gradient)))
contrast <- au$probability - nz$probability
contrasts <- data.frame(
  model = model_name,
  au_standardized_probability = au$probability,
  au_ci_lower = max(0, au$probability - zcrit * au$se),
  au_ci_upper = min(1, au$probability + zcrit * au$se),
  nz_standardized_probability = nz$probability,
  nz_ci_lower = max(0, nz$probability - zcrit * nz$se),
  nz_ci_upper = min(1, nz$probability + zcrit * nz$se),
  au_minus_nz_probability_contrast = contrast,
  contrast_standard_error = contrast_se,
  contrast_ci_lower = contrast - zcrit * contrast_se,
  contrast_ci_upper = contrast + zcrit * contrast_se,
  standardization_population = if (annual) "retained matched country-year pairs" else "retained matched countries",
  stringsAsFactors = FALSE
)
write.csv(contrasts, file.path(output_dir, paste0(model_name, "_contrasts.csv")), row.names = FALSE, quote = TRUE)

pearson <- sum(residuals(fit, type = "pearson")^2)
fit_statistics <- data.frame(
  model = model_name,
  observations = nrow(dat), countries = nlevels(dat$country),
  matched_units = nrow(grid), decisions = sum(n_total), parameters = length(coef(fit)),
  log_likelihood = as.numeric(logLik(fit)), aic = AIC(fit),
  residual_deviance = deviance(fit), residual_degrees_of_freedom = df.residual(fit),
  pearson_chi_square = pearson, pearson_dispersion = pearson / df.residual(fit),
  stringsAsFactors = FALSE
)
write.csv(fit_statistics, file.path(output_dir, paste0(model_name, "_fit.csv")), row.names = FALSE, quote = TRUE)

diagnostics <- data.frame(
  model = model_name,
  diagnostic = c("converged", "iterations", "covariance_method", "reference_destination", "outcome_invariant_countries_excluded", "excluded_country_names", "extreme_fitted_probabilities", "captured_warnings", "separation_check", "overdispersion_ratio"),
  value = c("true", fit$iter, covariance_method, reference, length(excluded), paste(excluded, collapse = ";"), sum(p_hat < 1e-6 | p_hat > 1 - 1e-6), if (length(captured_warnings)) paste(unique(captured_warnings), collapse = "; ") else "none", "passed: finite coefficients and SEs; absolute values <= 25", pearson / df.residual(fit)),
  interpretation = c("IRLS convergence status", "IRLS iterations", "coefficient uncertainty estimator", "factor reference level", "countries with all approvals or all declines across included observations", "auditable list of outcome-invariant exclusions", "fitted values outside [1e-6, 1-1e-6]", "all model warnings captured during fitting", "unresolved complete or quasi-complete separation screen", "Pearson chi-square divided by residual degrees of freedom"),
  stringsAsFactors = FALSE
)
write.csv(diagnostics, file.path(output_dir, paste0(model_name, "_diagnostics.csv")), row.names = FALSE, quote = TRUE)

cook <- cooks.distance(fit)
leverage <- hatvalues(fit)
deviance_residual <- residuals(fit, type = "deviance")
order_index <- head(order(cook, decreasing = TRUE), 20)
influence <- data.frame(
  model = model_name, rank = seq_along(order_index), country = as.character(dat$country[order_index]),
  year = as.character(dat$year[order_index]), destination_code = as.character(dat$destination[order_index]),
  number_approved = dat$approved[order_index], number_declined = dat$declined[order_index],
  decision_total = n_total[order_index], fitted_probability = p_hat[order_index],
  deviance_residual = deviance_residual[order_index], leverage = leverage[order_index],
  cooks_distance = cook[order_index],
  stringsAsFactors = FALSE
)
write.csv(influence, file.path(output_dir, paste0(model_name, "_influence.csv")), row.names = FALSE, quote = TRUE)
