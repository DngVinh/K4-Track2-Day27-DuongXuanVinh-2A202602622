# Reflection (≤1 page)

## 1. Which fault types were hardest to catch, and why?

The hardest fault types to detect were the **subtle-tier faults** that sit entirely within the natural variance bounds of clean batches:

1. **Subtle `distribution_shift`, `null_spike`, and `volume_drop` (`data_batch`)**:
   - In subtle cases, metrics like `null_rate` (~0.0076–0.0083) or `mean_amount` (~85–86) remain below the static 3σ baseline thresholds (`null_rate_max: 0.0109`, `mean_amount_max: 90.60`). In fact, some subtle fault values overlap directly with typical clean values (clean null rates reach up to 0.0105, clean means span 74.98–88.55).
   - Attempting to catch these with simple one-dimensional static threshold tightening immediately risks false positives, which carry a heavy scoring penalty (-30 × FPR).

2. **Subtle `runtime_anomaly` (`lineage_run`)**:
   - Subtle duration anomalies executed in 4,480–4,740 ms, which is well below the calibrated baseline limit (`lineage_duration_ms_max: 5134.98 ms`) and indistinguishable from clean runs (clean durations range from 3,471 to 4,805 ms). Without external host or worker cluster contention telemetry, duration alone has overlapping distributions.

3. **Subtle `corpus_staleness` and `embedding_drift` (`embedding_batch`)**:
   - Subtle centroid shifts (~0.028–0.031) and doc ages (~31–37 days) stayed well below the baseline ceilings (0.0435 and 49.8 days) and inside the clean empirical bounds (clean shifts up to 0.0388, doc ages up to 41.0 days).

In contrast, **ODCS contract violations** (schema mismatches, type corruption, SLA freshness breaches) and obvious AI skew/volume spikes were trivial to detect with 100% precision and zero false alarms by evaluating structural violations and explicit SLA contracts.

---

## 2. What would you change about your cost/coverage tradeoff, if you had another pass?

1. **Dynamic Adaptive Sampling under Budget Constraints**:
   - In the private phase, the 320-credit budget accommodates single-pass auditing across all 200 events (300 credits spend, 0.0 overage). However, in tight-budget streams (like public: 220 budget vs 240 cost for full coverage), metered tools charging 2.0 credits (`feature_drift`, `embedding_drift`) create a minor overage penalty.
   - With another pass, I would implement adaptive auditing: track running drift variance across events in `ctx.state`, and conditionally skip high-cost tool calls when consecutive historical windows exhibit near-zero drift variance, preserving budget headroom.

2. **Stateful Multivariate & Cumulative Sum (CUSUM) Detectors**:
   - Rather than relying on memoryless per-event evaluation, I would maintain stateful sliding windows (Exponential Moving Average and CUSUM) in `ctx.state`. Subtle shifts in distribution or volume that mimic normal noise on a single sample produce a consistent directional bias over consecutive events. Tracking multi-step cumulative deviations would allow catching subtle faults without compromising the zero false positive rate.
