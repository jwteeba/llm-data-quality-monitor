import io

import pandas as pd


def build_report_csv(anomalies: dict, violations: list[dict], profile: dict) -> bytes:
    """Return a CSV report as bytes combining anomaly summary, rule violations, and profile."""
    buf = io.StringIO()

    # ── Summary ───────────────────────────────────────────────────────────────
    summary = pd.DataFrame(
        [
            {"metric": "row_count", "value": anomalies["row_count"]},
            {"metric": "column_count", "value": anomalies["column_count"]},
            {"metric": "duplicate_rows", "value": anomalies["duplicate_rows"]},
            {
                "metric": "zero_variance_columns",
                "value": ", ".join(anomalies.get("zero_variance_columns", [])),
            },
        ]
    )
    buf.write("## Summary\n")
    summary.to_csv(buf, index=False)

    # ── Missing values ────────────────────────────────────────────────────────
    buf.write("\n## Missing Values\n")
    pd.DataFrame(
        anomalies["missing_values"].items(), columns=["column", "missing_count"]
    ).to_csv(buf, index=False)

    # ── Outliers ──────────────────────────────────────────────────────────────
    buf.write("\n## Outliers\n")
    pd.DataFrame(
        anomalies["outliers"].items(), columns=["column", "outlier_count"]
    ).to_csv(buf, index=False)

    # ── Rule violations ───────────────────────────────────────────────────────
    if violations:
        buf.write("\n## Rule Violations\n")
        pd.DataFrame(violations).to_csv(buf, index=False)

    # ── Column profile ────────────────────────────────────────────────────────
    buf.write("\n## Column Profile\n")
    profile_rows = []
    for col, stats in profile.items():
        row = {"column": col}
        row.update({k: v for k, v in stats.items() if k != "sample_values"})
        profile_rows.append(row)
    pd.DataFrame(profile_rows).to_csv(buf, index=False)

    return buf.getvalue().encode()
