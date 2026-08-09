# SizePath randomized experiment specification

## Decision and hypothesis

The decision is whether to make the SizePath CTA more prominent for eligible product-detail users.
The primary hypothesis is that assignment to the prominent CTA increases purchase conversion. The
current observational association is not the treatment effect: starting the flow is self-selected
and remains confounded by shopping intent.

## Design

- **Unit:** persistent anonymous user ID; known logged-in IDs may be mapped before assignment but
  must never receive conflicting variants.
- **Population:** consented users who render an eligible bike product detail page in the six included
  markets. Exclude internal/test/bot traffic and users already assigned in the prior 30 days.
- **Variants:** control = current CTA presentation; treatment = pre-specified prominent placement.
  The recommendation algorithm and catalog remain identical.
- **Allocation:** 50/50, deterministic persistent assignment, analyzed by assignment
  (intent-to-treat). `size_path_start` and completion are mediators, not treatment definitions.
- **Primary outcome:** operational purchase within the pre-specified attribution window divided by
  assigned eligible users.
- **Secondary outcomes:** CTA start, completion, recommendation click, add-to-cart, contribution per
  eligible user.
- **Guardrails:** mature size-related return rate, overall returns, checkout failure, page performance,
  assignment/CTA logging coverage, sample-ratio mismatch, and customer-support escalation.

## Power and duration

The observed non-starter baseline is 5.36%. With a two-sided 5% alpha, 80% power, a 0.6 percentage
point minimum detectable effect, and a 10% allowance for repeated-session clustering/attrition, the
planning calculation requires **25,602 users per arm (51,204 total)**. Duration must cover at least
one full business cycle and continue until the sample and minimum duration are both met. Do not stop
early on a transient p-value.

## Analysis plan

1. Validate assignment logging and run a sample-ratio-mismatch test before reading outcomes.
2. Estimate the unadjusted ITT risk difference and relative risk with user-level robust confidence
   intervals. Report absolute effects first.
3. Use a pre-specified covariate-adjusted model only for precision; include market, device, channel,
   visitor status, product family, and pre-period behavior. The unadjusted ITT remains primary.
4. Limit heterogeneity to pre-specified market and device interactions. Treat all other segments as
   exploratory with multiplicity caveats.
5. Analyze completion as a mediator/descriptive outcome; do not compare completers as if randomized.
6. Freeze return guardrail analysis until every included order has at least 60 days of observation.

## Decision rule

Recommend rollout only if the primary ITT interval excludes a practically unacceptable decline, the
point estimate supports the pre-agreed commercial threshold, instrumentation is healthy, and no
mature fit/return guardrail breaches. Otherwise keep or revert control and retain the learning. The
1.59 pp adjusted observational estimate and 1.20 pp synthetic truth are planning references, not a
promise about the experiment.
