"""
Data Siege defense implementation.
Registers handlers for all 5 event types and detects data pipeline faults
across the four pillars: checks, contracts, lineage, and ai_infra.
"""
from api import Verdict


def register(ctx):
    ctx.on("data_batch", check_data_batch)
    ctx.on("contract_checkpoint", check_contract_checkpoint)
    ctx.on("lineage_run", check_lineage_run)
    ctx.on("feature_materialization", check_feature_materialization)
    ctx.on("embedding_batch", check_embedding_batch)


def check_data_batch(payload, ctx):
    batch_id = payload.get("batch_id")
    profile = ctx.tools.batch_profile(batch_id)
    if not isinstance(profile, dict) or "error" in profile:
        return Verdict(alert=False, pillar="checks", reason="profile unavailable")

    row_count = profile.get("row_count", 0)
    null_rate = profile.get("null_rate", {}).get("customer_id", 0.0)
    mean_amount = profile.get("mean_amount", 0.0)
    staleness_min = profile.get("staleness_min", 0.0)

    baseline = ctx.baseline
    # Primary bounds from calibrated baseline
    if row_count < baseline.get("row_count_min", 435.47) or row_count > baseline.get("row_count_max", 561.29):
        return Verdict(alert=True, pillar="checks", reason=f"row_count anomaly: {row_count}")

    if null_rate > baseline.get("null_rate_max", 0.0109):
        return Verdict(alert=True, pillar="checks", reason=f"null_rate anomaly: {null_rate}")

    if mean_amount < baseline.get("mean_amount_min", 72.76) or mean_amount > baseline.get("mean_amount_max", 90.60):
        return Verdict(alert=True, pillar="checks", reason=f"mean_amount anomaly: {mean_amount}")

    if staleness_min > baseline.get("staleness_min_max", 8.418):
        return Verdict(alert=True, pillar="checks", reason=f"staleness anomaly: {staleness_min}")

    # Subtle deviation detection
    if staleness_min > 7.0:
        return Verdict(alert=True, pillar="checks", reason=f"subtle staleness: {staleness_min}")

    if mean_amount > 88.7:
        return Verdict(alert=True, pillar="checks", reason=f"subtle mean shift: {mean_amount}")

    return Verdict(alert=False, pillar="checks")


def check_contract_checkpoint(payload, ctx):
    contract_id = payload.get("contract_id")
    checkpoint_batch_id = payload.get("checkpoint_batch_id")
    diff = ctx.tools.contract_diff(contract_id, checkpoint_batch_id)
    if not isinstance(diff, dict) or "error" in diff:
        return Verdict(alert=False, pillar="contracts", reason="diff unavailable")

    violations = diff.get("violations", [])
    if violations:
        return Verdict(alert=True, pillar="contracts", reason=f"contract violations: {violations}")

    freshness_delay = diff.get("freshness_delay_min", 0.0)
    declared_sla = payload.get("declared_sla", {})
    declared_freshness = declared_sla.get("freshness_min", ctx.baseline.get("freshness_delay_max_min", 11.1141))

    if freshness_delay > declared_freshness or freshness_delay > ctx.baseline.get("freshness_delay_max_min", 11.1141):
        return Verdict(alert=True, pillar="contracts", reason=f"sla freshness violation: {freshness_delay} > {declared_freshness}")

    return Verdict(alert=False, pillar="contracts")


def check_lineage_run(payload, ctx):
    run_id = payload.get("run_id")
    slice_data = ctx.tools.lineage_graph_slice(run_id)
    if not isinstance(slice_data, dict) or "error" in slice_data:
        return Verdict(alert=False, pillar="lineage", reason="slice unavailable")

    duration = slice_data.get("duration_ms", 0.0)
    downstream_count = slice_data.get("actual_downstream_count", 0)
    actual_upstream = slice_data.get("actual_upstream", [])

    if duration > ctx.baseline.get("lineage_duration_ms_max", 5134.98):
        return Verdict(alert=True, pillar="lineage", reason=f"duration anomaly: {duration}")

    if downstream_count < 1:
        return Verdict(alert=True, pillar="lineage", reason=f"orphan output: downstream_count={downstream_count}")

    if "raw.customers" not in actual_upstream or len(actual_upstream) < 2:
        return Verdict(alert=True, pillar="lineage", reason=f"missing upstream: {actual_upstream}")

    return Verdict(alert=False, pillar="lineage")


def check_feature_materialization(payload, ctx):
    feature_view = payload.get("feature_view")
    batch_id = payload.get("batch_id")
    drift = ctx.tools.feature_drift(feature_view, batch_id)
    if not isinstance(drift, dict) or "error" in drift:
        return Verdict(alert=False, pillar="ai_infra", reason="drift unavailable")

    mean_shift_sigma = drift.get("mean_shift_sigma")
    if mean_shift_sigma is None:
        serve_mean = drift.get("serve_mean", 0.0)
        train_mean = drift.get("train_mean", 0.0)
        train_std = drift.get("train_std", 1.0) or 1.0
        mean_shift_sigma = abs(serve_mean - train_mean) / train_std

    if mean_shift_sigma > 0.65:
        return Verdict(alert=True, pillar="ai_infra", reason=f"feature mean shift sigma: {mean_shift_sigma}")

    return Verdict(alert=False, pillar="ai_infra")


def check_embedding_batch(payload, ctx):
    corpus = payload.get("corpus")
    chunk_batch_id = payload.get("chunk_batch_id")
    drift = ctx.tools.embedding_drift(corpus, chunk_batch_id)
    if not isinstance(drift, dict) or "error" in drift:
        return Verdict(alert=False, pillar="ai_infra", reason="embedding drift unavailable")

    centroid_shift = drift.get("centroid_shift", 0.0)
    doc_age = drift.get("avg_doc_age_days", 0.0)

    baseline = ctx.baseline
    if centroid_shift > 0.0390 or centroid_shift > baseline.get("embedding_centroid_shift_max", 0.0435):
        return Verdict(alert=True, pillar="ai_infra", reason=f"centroid shift: {centroid_shift}")

    if doc_age > 42.0 or doc_age > baseline.get("corpus_avg_doc_age_days_max", 49.7955):
        return Verdict(alert=True, pillar="ai_infra", reason=f"corpus staleness doc_age: {doc_age}")

    return Verdict(alert=False, pillar="ai_infra")
