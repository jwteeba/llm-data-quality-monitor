import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from detector.anomaly_detector import (
    detect_anomalies,
    plot_anomalies_interactive,
    summarize_anomalies_llm,
)
from utils.utils import create_db_engine, read_data_from_mysql, read_data_from_s3


def check_passcode():
    if "auth" not in st.session_state:
        st.session_state.auth = False

    if not st.session_state.auth:
        st.title("🔐 Passcode Required")
        code = st.text_input("Enter Passcode", type="password")

        if st.button("Submit"):
            if code == st.secrets.get("app-key").get("passcode"):
                st.session_state.auth = True
            else:
                st.error("Invalid passcode")
        st.stop()


check_passcode()


st.title("🧠 LLM Data Quality Dashboard")

data_source = st.selectbox("Select data source:", ["MySQL", "S3"])

df = None

if data_source == "MySQL":
    table_name = st.text_input("Enter MySQL table name:")
elif data_source == "S3":
    s3_bucket = st.text_input("Enter S3 bucket name:")
    s3_key = st.text_input("Enter S3 object key (e.g. data/myfile.csv):")

if st.button("Run Data Quality Check"):
    try:
        if data_source == "MySQL":
            engine = create_db_engine()
            df = read_data_from_mysql(table_name, engine)
        elif data_source == "S3":
            df = read_data_from_s3(s3_bucket, s3_key)

        if df is None or df.empty:
            st.warning(f"No data found in selected source: {data_source}")
        else:
            anomalies = detect_anomalies(df)
            plot_anomalies_interactive(anomalies)

            with st.spinner("🧠 Generating AI summary..."):
                summary = summarize_anomalies_llm(anomalies)

            st.subheader("📋 Anomaly Summary")
            st.write(summary)

            st.subheader("🧩 Raw Anomalies")
            st.json(anomalies)

            st.subheader("🧾 Sample Data")
            st.dataframe(df.head())

    except Exception as err:
        st.error(f"Error: {err}")
