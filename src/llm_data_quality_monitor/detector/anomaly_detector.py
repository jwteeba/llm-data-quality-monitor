import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from openai import OpenAI


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
    for col in numeric_df.columns:
        Q1 = numeric_df[col].quantile(0.25)
        Q3 = numeric_df[col].quantile(0.75)
        IQR = Q3 - Q1
        outlier_mask = (numeric_df[col] < (Q1 - 1.5 * IQR)) | (
            numeric_df[col] > (Q3 + 1.5 * IQR)
        )
        outlier_counts[col] = int(outlier_mask.sum())
    anomalies["outliers"] = outlier_counts

    # 5. Skewness
    anomalies["skewness"] = numeric_df.skew().round(2).to_dict()

    # 6. Low cardinality
    anomalies["low_cardinality"] = {
        col: df[col].nunique() for col in df.columns if df[col].nunique() < 5
    }

    # 7. General info
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

    # Zero variance and low cardinality info
    if anomalies["zero_variance_columns"]:
        st.warning(f"⚠️ Zero Variance Columns: {anomalies['zero_variance_columns']}")
    if anomalies["low_cardinality"]:
        st.info(f"ℹ️ Low Cardinality Columns: {anomalies['low_cardinality']}")


# ============== Cached LLM Summary ==============
@st.cache_data(show_spinner=False, max_entries=20)
def summarize_anomalies_llm(anomalies: dict) -> str:
    """Use OpenAI to summarize anomalies in natural language.

    Cache LLM summaries based on anomalies hash.
    """

    client = OpenAI()

    prompt = f"""
    You are a senior data quality engineer.
    Analyze the following dataset anomaly report and produce a short,
    insightful summary:
    {anomalies}

    Include:
    - Key problems detected
    - Possible causes
    - Recommended next steps for data engineers
    Keep it concise and professional.
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a data quality expert."},
            {"role": "user", "content": prompt},
        ],
    )
    return str(response.choices[0].message.content)
