from dataclasses import asdict, dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from jinja2 import Template
from openai import OpenAI
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential


class AnomalySummary(BaseModel):
    """Structured anomaly summary from LLM."""

    problems: list[str]
    causes: list[str]
    recommendations: list[str]
    summary: str


ANOMALY_PROMPT = Template("""
You are a senior data quality engineer analyzing dataset anomalies.

Dataset Anomaly Report:
{{ anomalies | tojson }}

Provide a structured analysis with:
1. **Critical Issues**: List only anomalies that impact data usability (missing >10%, duplicates, type mismatches, zero-variance columns)
2. **Root Causes**: Identify likely causes (data pipeline errors, schema changes, upstream failures)
3. **Immediate Actions**: Prioritized steps for data engineers (validation, remediation, escalation)
4. **Executive Summary**: One to Three sentence impact statement

Be concise, technical, and actionable. Focus on severity and business impact. Never invent facts.
""")


@dataclass
class AnomalyReport:
    dataset_level: dict[str, Any] = field(default_factory=dict)
    column_level: dict[str, Any] = field(default_factory=dict)
    row_level: dict[str, Any] = field(default_factory=dict)
    quality_score: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _iqr_outlier_mask(series: pd.Series, multiplier: float = 1.5) -> pd.Series:
    """Return boolean mask for outliers using IQR rule."""
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    if pd.isna(iqr) or iqr == 0:
        return pd.Series(False, index=series.index)
    lower, upper = q1 - multiplier * iqr, q3 + multiplier * iqr
    return (series < lower) | (series > upper)


def _modified_zscore_outlier_mask(
    series: pd.Series, threshold: float = 3.5
) -> pd.Series:
    """Return boolean mask for outliers using Modified Z-Score (MAD-based)."""
    median = series.median()
    mad = (series - median).abs().median()
    if pd.isna(mad) or mad == 0:
        return pd.Series(False, index=series.index)
    mz = 0.6745 * (series - median) / mad
    return mz.abs() > threshold


def _zscore_outlier_mask(series: pd.Series, threshold: float = 3.0) -> pd.Series:
    """Return boolean mask for outliers using standard z-score."""
    std = series.std()
    if pd.isna(std) or std == 0:
        return pd.Series(False, index=series.index)
    z = (series - series.mean()) / std
    return z.abs() > threshold


_OUTLIER_METHODS = {
    "iqr": _iqr_outlier_mask,
    "zscore": _zscore_outlier_mask,
    "modified_zscore": _modified_zscore_outlier_mask,
}


def detect_anomalies(
    df: pd.DataFrame,
    *,
    iqr_multiplier: float = 1.5,
    outlier_method: str = "iqr",
    outlier_threshold: Optional[float] = None,
    low_cardinality_threshold: int = 5,
    high_cardinality_ratio: float = 0.95,
    rare_category_threshold: float = 0.01,
    correlation_threshold: float = 0.95,
    max_flagged_rows: int = 100,
    exclude_columns: Optional[list[str]] = None,
    compute_quality_score: bool = True,
) -> dict[str, Any]:
    """
    Detects anomalies in a DataFrame and returns a structured summary.

    Parameters
    ----------
    df : pd.DataFrame
        The dataframe to analyze.
    iqr_multiplier : float
        Multiplier used for IQR-based outlier bounds (only used if
        outlier_method="iqr").
    outlier_method : {"iqr", "zscore", "modified_zscore"}
        Strategy used to flag numeric outliers. "modified_zscore" (MAD-based)
        is more robust to skewed distributions than IQR or plain z-score.
    outlier_threshold : float, optional
        Threshold for zscore/modified_zscore methods. Defaults to 3.0 for
        zscore and 3.5 for modified_zscore if not provided.
    low_cardinality_threshold : int
        Columns with fewer distinct values than this are flagged as
        low-cardinality (likely categorical / possibly constant-ish).
    high_cardinality_ratio : float
        Columns whose nunique()/row_count exceeds this ratio are flagged as
        likely identifier columns.
    rare_category_threshold : float
        Categories making up less than this fraction of rows in a
        categorical column are flagged as rare (possible typos / bad data).
    correlation_threshold : float
        Absolute pairwise correlation above this value is flagged as
        potential multicollinearity.
    max_flagged_rows : int
        Cap on how many row indices are returned in flagged_rows.
    exclude_columns : list[str], optional
        Columns to skip entirely (e.g. free-text or known-noisy columns).
    compute_quality_score : bool
        Whether to compute an overall 0-100 data quality score.

    Returns
    -------
    dict
        Structured summary with "dataset_level", "column_level",
        "row_level", and "quality_score" keys.
    """
    report = AnomalyReport()

    if exclude_columns:
        df = df.drop(columns=[c for c in exclude_columns if c in df.columns])

    # Guard: empty dataframe
    if df.shape[0] == 0 or df.shape[1] == 0:
        report.dataset_level = {
            "row_count": df.shape[0],
            "column_count": df.shape[1],
            "warning": "DataFrame is empty; no anomaly checks were run.",
        }
        report.quality_score = None
        return report.to_dict()

    n_rows = len(df)
    col_level: dict[str, Any] = {}
    row_level: dict[str, Any] = {}
    dataset_level: dict[str, Any] = {"row_count": n_rows, "column_count": df.shape[1]}

    # Duplicate column names
    dup_cols = df.columns[df.columns.duplicated()].tolist()
    dataset_level["duplicate_column_names"] = dup_cols

    # Missing values (counts + percentage)
    missing_counts = df.isna().sum()
    col_level["missing_values"] = {
        col: {"count": int(cnt), "pct": round(float(cnt) / n_rows * 100, 2)}
        for col, cnt in missing_counts.items()
        if cnt > 0
    }

    # All-null columns
    col_level["all_null_columns"] = missing_counts[
        missing_counts == n_rows
    ].index.tolist()

    # Duplicate rows
    dup_mask = df.duplicated()
    dataset_level["duplicate_rows"] = {
        "count": int(dup_mask.sum()),
        "pct": round(float(dup_mask.sum()) / n_rows * 100, 2),
    }

    # Cardinality (computed once, reused)
    nunique = df.nunique(dropna=True)

    col_level["zero_variance_columns"] = nunique[nunique <= 1].index.tolist()

    col_level["low_cardinality"] = {
        col: int(nunique[col])
        for col in df.columns
        if nunique[col] < low_cardinality_threshold
    }

    col_level["high_cardinality_columns"] = [
        col
        for col in df.columns
        if n_rows > 0 and (nunique[col] / n_rows) >= high_cardinality_ratio
    ]

    # Infinite values (numeric)
    numeric_df = df.select_dtypes(include=np.number)
    inf_counts = {}
    for col in numeric_df.columns:
        n_inf = int(np.isinf(numeric_df[col]).sum())
        if n_inf > 0:
            inf_counts[col] = n_inf
    col_level["infinite_values"] = inf_counts

    # Outliers
    if outlier_method not in _OUTLIER_METHODS:
        raise ValueError(
            f"Unknown outlier_method '{outlier_method}'. "
            f"Choose from: {list(_OUTLIER_METHODS)}"
        )
    outlier_fn = _OUTLIER_METHODS[outlier_method]

    outlier_counts: dict[str, int] = {}
    unreliable_outlier_cols: list[str] = []
    outlier_row_indices: set = set()

    for col in numeric_df.columns:
        series = numeric_df[col].replace([np.inf, -np.inf], np.nan).dropna()
        if series.empty:
            unreliable_outlier_cols.append(col)
            outlier_counts[col] = 0
            continue

        if outlier_method == "iqr":
            mask = _iqr_outlier_mask(series, multiplier=iqr_multiplier)
        else:
            kwargs = {}
            if outlier_threshold is not None:
                kwargs["threshold"] = outlier_threshold
            mask = outlier_fn(series, **kwargs)

        outlier_counts[col] = int(mask.sum())
        outlier_row_indices.update(series.index[mask].tolist())

    col_level["outliers"] = {
        "method": outlier_method,
        "counts": outlier_counts,
        "unreliable_columns": unreliable_outlier_cols,  # all-NaN/all-inf, no valid data to check
    }

    # Skewness
    with np.errstate(all="ignore"):
        skew_vals = numeric_df.replace([np.inf, -np.inf], np.nan).skew(
            numeric_only=True
        )
    col_level["skewness"] = skew_vals.round(2).dropna().to_dict()

    # Type inconsistencies (mixed numeric/string in object columns)
    type_issues = []
    for col in df.select_dtypes(include=["object", "string"]).columns:
        non_null = df[col].dropna()
        if non_null.empty:
            continue
        numeric_mask = pd.to_numeric(non_null, errors="coerce").notna()
        if numeric_mask.any() and (~numeric_mask).any():
            type_issues.append(col)
    col_level["type_inconsistencies"] = type_issues

    # Whitespace / casing issues in string columns
    whitespace_issues = []
    casing_issues = []
    for col in df.select_dtypes(include=["object", "string"]).columns:
        non_null = df[col].dropna().astype(str)
        if non_null.empty:
            continue
        if (non_null != non_null.str.strip()).any():
            whitespace_issues.append(col)
        # flag if collapsing case reduces distinct value count (dup categories)
        if non_null.str.lower().nunique() < non_null.nunique():
            casing_issues.append(col)
    col_level["whitespace_issues"] = whitespace_issues
    col_level["inconsistent_casing"] = casing_issues

    # Rare categories
    rare_categories: dict[str, list[str]] = {}
    for col in df.select_dtypes(include=["object", "string", "category"]).columns:
        counts = df[col].value_counts(normalize=True, dropna=True)
        rare = counts[counts < rare_category_threshold].index.tolist()
        if rare:
            rare_categories[col] = rare[:20]  # cap to avoid huge payloads
    col_level["rare_categories"] = rare_categories

    # Multicollinearity (high pairwise correlation)
    high_corr_pairs = []
    if numeric_df.shape[1] >= 2:
        corr = numeric_df.corr(numeric_only=True).abs()
        cols = corr.columns
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                val = corr.iloc[i, j]
                if pd.notna(val) and val >= correlation_threshold:
                    high_corr_pairs.append(
                        {
                            "columns": [cols[i], cols[j]],
                            "correlation": round(float(val), 3),
                        }
                    )
    col_level["high_correlation_pairs"] = high_corr_pairs

    # Datetime checks
    datetime_issues: dict[str, Any] = {}
    now = pd.Timestamp.now()
    for col in df.select_dtypes(include=["datetime64[ns]", "datetimetz"]).columns:
        series = df[col].dropna()
        if series.empty:
            continue
        future_count = int((series > now).sum())
        issues = {}
        if future_count > 0:
            issues["future_dates"] = future_count
        datetime_issues_range = series.max() - series.min()
        issues["min_date"] = str(series.min())
        issues["max_date"] = str(series.max())
        issues["range_days"] = (
            datetime_issues_range.days if pd.notna(datetime_issues_range) else None
        )
        datetime_issues[col] = issues
    col_level["datetime_issues"] = datetime_issues

    # Row-level anomaly flags
    missing_row_indices = set(df.index[df.isna().any(axis=1)].tolist())
    flagged_indices = missing_row_indices | outlier_row_indices
    row_level["flagged_rows"] = sorted(flagged_indices)[:max_flagged_rows]
    row_level["flagged_row_count"] = len(flagged_indices)
    row_level["flagged_row_pct"] = round(len(flagged_indices) / n_rows * 100, 2)

    # Assemble report
    dataset_level["numeric_column_count"] = numeric_df.shape[1]
    dataset_level["categorical_column_count"] = df.select_dtypes(
        include=["object", "string", "category"]
    ).shape[1]

    report.dataset_level = dataset_level
    report.column_level = col_level
    report.row_level = row_level

    # Quality score (simple weighted heuristic, 0-100)
    if compute_quality_score:
        penalties = 0.0
        total_cells = n_rows * df.shape[1]
        missing_cells = int(missing_counts.sum())
        penalties += (missing_cells / total_cells) * 40 if total_cells else 0
        penalties += (dup_mask.sum() / n_rows) * 15
        penalties += (len(flagged_indices) / n_rows) * 20
        penalties += min(len(col_level["zero_variance_columns"]), 5) * 2
        penalties += min(len(type_issues), 5) * 2
        penalties += min(len(high_corr_pairs), 5) * 1
        report.quality_score = round(max(0.0, 100.0 - penalties), 1)

    return report.to_dict()


def plot_anomalies_interactive(anomalies: dict):
    """
    Render an interactive anomaly report using Plotly and Streamlit.

    Expects the structured dict produced by detect_anomalies(), i.e. a dict
    with "dataset_level", "column_level", "row_level", and "quality_score"
    keys.
    """
    dataset = anomalies.get("dataset_level", {})
    columns = anomalies.get("column_level", {})
    rows = anomalies.get("row_level", {})
    quality_score = anomalies.get("quality_score")

    if dataset.get("warning"):
        st.warning(f"⚠️ {dataset['warning']}")
        return

    _render_summary(dataset, rows, quality_score)

    left, right = st.columns(2)
    _render_missing_values(columns, container=left)
    _render_outliers(columns, container=right)

    _render_skewness(columns)
    _render_column_flags(columns)
    _render_categorical_issues(columns)
    _render_correlation(columns)
    _render_datetime_issues(columns)
    _render_row_flags(rows)


def _render_summary(dataset: dict, rows: dict, quality_score):

    st.subheader("📊 Dataset Summary")

    cols = st.columns(4 if quality_score is not None else 3)
    cols[0].metric("Rows", dataset.get("row_count", 0))
    cols[1].metric("Columns", dataset.get("column_count", 0))
    dup = dataset.get("duplicate_rows", {})
    dup_count = dup.get("count", dup) if isinstance(dup, dict) else dup
    dup_pct = dup.get("pct") if isinstance(dup, dict) else None
    cols[2].metric(
        "Duplicate Rows",
        dup_count,
        delta=f"{dup_pct}%" if dup_pct is not None else None,
        delta_color="inverse",
    )

    if quality_score is not None:
        cols[3].metric("Quality Score", f"{quality_score}/100")
        fig = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=quality_score,
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": "darkblue"},
                    "steps": [
                        {"range": [0, 50], "color": "#f8d7da"},
                        {"range": [50, 80], "color": "#fff3cd"},
                        {"range": [80, 100], "color": "#d4edda"},
                    ],
                },
                title={"text": "Data Quality Score"},
            )
        )
        fig.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig, use_container_width=True)

    if dataset.get("duplicate_column_names"):
        st.warning(f"⚠️ Duplicate Column Names: {dataset['duplicate_column_names']}")


def _render_missing_values(columns: dict, container=None):
    target = container if container is not None else st

    missing = columns.get("missing_values", {})
    if not missing:
        return
    df = pd.DataFrame(
        [
            {"column": col, "count": v["count"], "pct": v["pct"]}
            for col, v in missing.items()
        ]
    ).sort_values("count", ascending=False)

    fig = px.bar(
        df,
        x="column",
        y="count",
        title="🧩 Missing Values per Column",
        labels={"column": "Column", "count": "Missing Count"},
        color="pct",
        color_continuous_scale="Reds",
        hover_data={"pct": ":.1f"},
    )
    target.plotly_chart(fig, use_container_width=True)

    if columns.get("all_null_columns"):
        target.error(f"🚫 Entirely Empty Columns: {columns['all_null_columns']}")


def _render_outliers(columns: dict, container=None):
    target = container if container is not None else st

    outlier_info = columns.get("outliers", {})
    counts = outlier_info.get("counts", {})
    method = outlier_info.get("method", "iqr")
    if counts and sum(counts.values()) > 0:
        outliers = pd.Series(counts)
        fig = px.bar(
            outliers,
            x=outliers.index,
            y=outliers.values,
            title=f"📉 Outlier Count per Numeric Column ({method})",
            labels={"x": "Column", "y": "Outlier Count"},
            color=outliers.values,
            color_continuous_scale="Blues",
        )
        target.plotly_chart(fig, use_container_width=True)

    if outlier_info.get("unreliable_columns"):
        target.info(
            "ℹ️ Columns skipped for outlier detection (no valid numeric data): "
            f"{outlier_info['unreliable_columns']}"
        )

    if columns.get("infinite_values"):
        target.warning(f"⚠️ Infinite Values Found: {columns['infinite_values']}")


def _render_skewness(columns: dict):
    skew = pd.Series(columns.get("skewness", {}))
    if skew.empty:
        return
    fig = px.bar(
        skew,
        x=skew.index,
        y=skew.values,
        title="📈 Skewness per Numeric Column",
        labels={"x": "Column", "y": "Skewness"},
        color=skew.values,
        color_continuous_scale="Viridis",
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_column_flags(columns: dict):
    if columns.get("zero_variance_columns"):
        st.warning(f"⚠️ Zero Variance Columns: {columns['zero_variance_columns']}")
    if columns.get("low_cardinality"):
        st.info(f"ℹ️ Low Cardinality Columns: {columns['low_cardinality']}")
    if columns.get("high_cardinality_columns"):
        st.info(
            "ℹ️ High Cardinality Columns (likely IDs): "
            f"{columns['high_cardinality_columns']}"
        )
    if columns.get("type_inconsistencies"):
        st.warning(f"⚠️ Mixed-Type Columns: {columns['type_inconsistencies']}")


def _render_categorical_issues(columns: dict):
    whitespace = columns.get("whitespace_issues", [])
    casing = columns.get("inconsistent_casing", [])
    rare = columns.get("rare_categories", {})

    if not (whitespace or casing or rare):
        return

    with st.expander("🔤 Categorical Data Issues"):
        if whitespace:
            st.warning(f"⚠️ Columns with Leading/Trailing Whitespace: {whitespace}")
        if casing:
            st.warning(f"⚠️ Columns with Inconsistent Casing: {casing}")
        if rare:
            st.info("ℹ️ Rare Categories (possible typos/data entry errors):")
            for col, cats in rare.items():
                st.write(f"- **{col}**: {cats}")


def _render_correlation(columns: dict):
    pairs = columns.get("high_correlation_pairs", [])
    if not pairs:
        return
    with st.expander("🔗 Highly Correlated Column Pairs (possible multicollinearity)"):
        df = pd.DataFrame(pairs)
        df["columns"] = df["columns"].apply(lambda c: " ↔ ".join(c))
        st.dataframe(df, use_container_width=True, hide_index=True)


def _render_datetime_issues(columns: dict):
    dt_issues = columns.get("datetime_issues", {})
    if not dt_issues:
        return
    with st.expander("📅 Datetime Column Checks"):
        for col, info in dt_issues.items():
            st.write(f"**{col}**")
            st.json(info)
            if info.get("future_dates"):
                st.warning(f"⚠️ {info['future_dates']} future-dated values in '{col}'")


def _render_row_flags(rows: dict):
    flagged_count = rows.get("flagged_row_count", 0)
    if flagged_count <= 0:
        return
    st.metric(
        "Flagged Rows (missing or outlier)",
        flagged_count,
        delta=f"{rows.get('flagged_row_pct', 0)}%",
        delta_color="inverse",
    )
    if rows.get("flagged_rows"):
        with st.expander(
            f"🔎 View Flagged Row Indices (showing up to {len(rows['flagged_rows'])})"
        ):
            st.write(rows["flagged_rows"])


@st.cache_data(show_spinner=False, max_entries=20)
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def summarize_anomalies_llm(anomalies: dict, api_key: str) -> str:
    """Use OpenAI to summarize anomalies in natural language.

    Cache LLM summaries based on anomalies hash.
    Retries up to 3 times with exponential backoff on failure.
    """
    client = OpenAI(api_key=api_key)
    prompt = ANOMALY_PROMPT.render(anomalies=anomalies)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a senior data quality engineer. Analyze anomalies with focus on severity, business impact, and actionable remediation. Be concise and technical.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )
    return str(response.choices[0].message.content)
