# Known limitations

1. **Everything is synthetic.** The scenario is useful for demonstrating analytics decisions and
   engineering controls, not for inferring anything about a real retailer, market, or child.
2. **Generator v1 SizePath exposure is incomplete.** It records `size_path_open`, answers, and a
   recommendation but no separate CTA impression/assignment. Product views are the documented
   eligibility proxy in the observational study. The dataLayer prototype shows the corrected target
   contract.
3. **Residual confounding is intentional.** The adjusted observed SizePath association is 1.59 pp
   versus a 1.20 pp hidden structural truth. Observable balance is excellent; latent intent still
   demonstrates why a randomized test is required.
4. **Return comparisons are survivor-conditioned.** The lower observed size-return rate among
   SizePath users is descriptive among mature purchasers. It is not a total causal effect because
   purchase occurs after exposure.
5. **Inventory does not suppress demand in generator v1.** The planted Comet 16 stockout strongly
   changes the operational availability table but does not causally reduce generated sales. Stockout
   evidence therefore supports an operations investigation, not lost-sales estimation.
6. **Acquisition economics are deliberately extreme.** Paid-media spend is calibrated to create a
   visible profitability decision. CAC in the executive mart is an aggregate proxy; cohort
   acquisition and incrementality would be needed in a real system.
7. **Cohort behavior is simplified.** Realized 90/365-day contribution is observed, not predictive;
   repeat purchasing and cross-device identity are intentionally limited. Newer cohorts are censored.
8. **GA4 shape is partial.** The nested event representation covers fields used by this project but is
   neither an exact export replica nor a claim that GA4 UI and BigQuery exports should match.
9. **One serverless demo environment.** Cloud Run/Cloud SQL services are single-instance portfolio
   resources in a shared GCP host. There is no multi-region HA, custom domain, enterprise SSO for
   Metabase public links, or formal SLO.
10. **Shared-project isolation has limits.** Names, labels, identities, state, datasets, and databases
    are isolated, but project-level quota, inherited IAM, billing, and logs remain shared with
    TraceGate until migration to the dedicated Rider project.
11. **Metabase is a serving copy.** PostgreSQL is intentionally replaceable and may lag BigQuery
    until a successful publication. The current contract reconciles exact table counts; richer
    cross-engine checksums and additive-total manifests are a production-hardening opportunity.
12. **Portfolio credentials and retention.** Public URLs may be retired when trial credit expires.
    Screenshots preserve the walkthrough; application state and synthetic data are not business
    records and have no production retention guarantee.
13. **Backfill optimizes correctness before transfer volume.** A date-range raw backfill replaces
    only selected BigQuery partitions atomically, but the portfolio-scale loader uploads each
    consolidated source Parquet file to a temporary table first. Downstream dbt tables rebuild in
    full at the current 450,000-session scale. Production scale would use date-partitioned source
    objects and incremental `insert_overwrite` models to reduce transfer and scan volume.
