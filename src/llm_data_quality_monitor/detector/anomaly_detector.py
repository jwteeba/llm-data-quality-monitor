import numpy as np
import pandas as pd
import plotly.express as px
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


def detect_anomalies(df: pd.DataFrame):
    """
    Detects anomalies and returns a structured summary.
    """
    anomalies = {}

    # 1. Missing values
    anomalies["missing_values"] = df.isna().sum().to_dict()

    # 2. Duplicate rows
    anomalies["duplicate_rows"] = int(df.duplicated().sum())

    # 3. Zero variance columns
    anomalies["zero_variance_columns"] = df.columns[df.nunique() <= 1].tolist()

    # 4. Outliers (IQR method)
    numeric_df = df.select_dtypes(include=np.number)
    outlier_counts = {}
    outlier_row_indices = set()
    for col in numeric_df.columns:
        Q1 = numeric_df[col].quantile(0.25)
        Q3 = numeric_df[col].quantile(0.75)
        IQR = Q3 - Q1
        outlier_mask = (numeric_df[col] < (Q1 - 1.5 * IQR)) | (
            numeric_df[col] > (Q3 + 1.5 * IQR)
        )
        outlier_counts[col] = int(outlier_mask.sum())
        outlier_row_indices.update(numeric_df.index[outlier_mask].tolist())
    anomalies["outliers"] = outlier_counts

    # 5. Skewness
    anomalies["skewness"] = numeric_df.skew().round(2).to_dict()

    # 6. Low cardinality
    anomalies["low_cardinality"] = {
        col: df[col].nunique() for col in df.columns if df[col].nunique() < 5
    }

    # 7. Type inconsistencies (mixed numeric/string in object columns)
    type_issues = []
    for col in df.select_dtypes(include=object).columns:
        non_null = df[col].dropna()
        numeric_mask = pd.to_numeric(non_null, errors="coerce").notna()
        if numeric_mask.sum() > 0 and numeric_mask.sum() < len(numeric_mask):
            type_issues.append(col)
    anomalies["type_inconsistencies"] = type_issues

    # 8. Row-level anomaly flags (rows with any missing value or outlier)
    missing_row_indices = set(df.index[df.isna().any(axis=1)].tolist())
    flagged_indices = missing_row_indices | outlier_row_indices
    anomalies["flagged_rows"] = sorted(flagged_indices)[:100]  # cap at 100
    anomalies["flagged_row_count"] = len(flagged_indices)

    # 9. General info
    anomalies["row_count"] = len(df)
    anomalies["column_count"] = len(df.columns)

    return anomalies


def plot_anomalies_interactive(anomalies: dict):
    """
    Create interactive anomaly charts using Plotly and Streamlit.
    """

    st.subheader("📊 Dataset Summary")
    st.metric("Rows", anomalies["row_count"])
    st.metric("Columns", anomalies["column_count"])
    st.metric("Duplicate Rows", anomalies["duplicate_rows"])

    # Missing values chart
    missing = pd.Series(anomalies["missing_values"])
    if missing.sum() > 0:
        fig = px.bar(
            missing,
            x=missing.index,
            y=missing.values,
            title="🧩 Missing Values per Column",
            labels={"x": "Column", "y": "Missing Count"},
            color=missing.values,
            color_continuous_scale="Reds",
        )
        st.plotly_chart(fig, use_container_width=True)

    # Outliers
    outliers = pd.Series(anomalies["outliers"])
    if outliers.sum() > 0:
        fig = px.bar(
            outliers,
            x=outliers.index,
            y=outliers.values,
            title="📉 Outlier Count per Numeric Column",
            labels={"x": "Column", "y": "Outlier Count"},
            color=outliers.values,
            color_continuous_scale="Blues",
        )
        st.plotly_chart(fig, use_container_width=True)

    # Skewness
    skew = pd.Series(anomalies["skewness"])
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

    # Zero variance, low cardinality, and type inconsistency info
    if anomalies["zero_variance_columns"]:
        st.warning(f"⚠️ Zero Variance Columns: {anomalies['zero_variance_columns']}")
    if anomalies["low_cardinality"]:
        st.info(f"ℹ️ Low Cardinality Columns: {anomalies['low_cardinality']}")
    if anomalies.get("type_inconsistencies"):
        st.warning(f"⚠️ Mixed-Type Columns: {anomalies['type_inconsistencies']}")
    if anomalies.get("flagged_row_count", 0) > 0:
        st.metric("Flagged Rows (missing or outlier)", anomalies["flagged_row_count"])


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
