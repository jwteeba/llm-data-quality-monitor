import streamlit as st

from llm_data_quality_monitor.detector.anomaly_detector import (
    detect_anomalies,
    plot_anomalies_interactive,
    summarize_anomalies_llm,
)
from llm_data_quality_monitor.utils.profiler import profile_dataframe
from llm_data_quality_monitor.utils.report import build_report_csv
from llm_data_quality_monitor.utils.rules import Rule, evaluate_rules
from llm_data_quality_monitor.utils.utils import (
    check_postgres_connection,
    check_s3_connection,
    list_postgres_tables,
    list_s3_objects,
    read_data_from_postgres,
    read_data_from_s3,
    read_uploaded_file,
)

# ── Session state ─────────────────────────────────────────────────────────────

if "pg_connections" not in st.session_state:
    st.session_state.pg_connections = {}

if "s3_connections" not in st.session_state:
    st.session_state.s3_connections = {}

if "rules" not in st.session_state:
    st.session_state.rules = []


# ── Helpers ───────────────────────────────────────────────────────────────────


def _run_quality_check(df):
    import pandas as pd

    anomalies = detect_anomalies(df)
    profile = profile_dataframe(df)
    violations = evaluate_rules(
        st.session_state.rules, anomalies, anomalies["row_count"]
    )

    plot_anomalies_interactive(anomalies)

    # Flagged rows
    if anomalies.get("flagged_rows"):
        with st.expander(
            f"🚩 Flagged Rows ({anomalies['flagged_row_count']} total, showing up to 100)"
        ):
            st.dataframe(df.loc[anomalies["flagged_rows"]])

    # Rule violations
    if st.session_state.rules:
        st.subheader("📏 Rule Violations")
        if violations:
            st.error(f"{len(violations)} rule(s) violated.")
            st.dataframe(violations)
        else:
            st.success("All rules passed.")

    # Data profile
    with st.expander("🔬 Column Profile"):
        profile_rows = []
        for col, stats in profile.items():
            row = {"column": col}
            row.update({k: v for k, v in stats.items() if k != "sample_values"})
            profile_rows.append(row)
        st.dataframe(pd.DataFrame(profile_rows))

    # AI summary
    if not openai_api_key:
        st.warning(
            "Enter your OpenAI API key in the sidebar to generate an AI summary."
        )
    else:
        with st.spinner("🧠 Generating AI summary..."):
            summary = summarize_anomalies_llm(anomalies, openai_api_key)
        st.subheader("📋 Anomaly Summary")
        st.write(summary)

    st.subheader("🧩 Raw Anomalies")
    st.json(anomalies)

    st.subheader("🧾 Sample Data")
    st.dataframe(df.head())

    # Download report
    csv_bytes = build_report_csv(anomalies, violations, profile)
    st.download_button(
        label="⬇️ Download Report (CSV)",
        data=csv_bytes,
        file_name="dq_report.csv",
        mime="text/csv",
    )


# ── App ───────────────────────────────────────────────────────────────────────

st.title("🧠 LLM Data Quality Dashboard")

with st.sidebar:
    st.header("🔑 OpenAI API Key")
    openai_api_key = st.text_input(
        "Enter your OpenAI API key:",
        type="password",
        placeholder="sk-...",
        help="Held in memory for this session only — never stored.",
    )
    st.caption("[Get an API key](https://platform.openai.com/api-keys)")

    st.divider()
    st.header("⚙️ Options")
    sample_rows = st.number_input(
        "Row limit (0 = all rows)",
        min_value=0,
        value=0,
        step=1000,
        help="Limit rows loaded to avoid memory issues on large datasets.",
    )
    sample_rows = int(sample_rows) or None

    st.divider()
    st.header("📏 Custom Rules")
    with st.expander("Add a rule"):
        rule_name = st.text_input("Rule name", key="rule_name")
        rule_check = st.selectbox(
            "Check",
            ["missing_pct", "duplicate_rows", "outlier_count"],
            key="rule_check",
        )
        needs_column = rule_check in ("missing_pct", "outlier_count")
        rule_column = (
            st.text_input("Column (if applicable)", key="rule_col")
            if needs_column
            else None
        )
        rule_op = st.selectbox("Operator", [">", ">=", "<", "<="], key="rule_op")
        rule_threshold = st.number_input("Threshold", value=5.0, key="rule_thresh")

        if st.button("Add rule"):
            if not rule_name:
                st.warning("Please enter a rule name.")
            else:
                st.session_state.rules.append(
                    Rule(
                        name=rule_name,
                        check=rule_check,
                        column=rule_column or None,
                        operator=rule_op,
                        threshold=rule_threshold,
                    )
                )
                st.success(f"Rule '{rule_name}' added.")
                st.rerun()

    if st.session_state.rules:
        st.caption(f"{len(st.session_state.rules)} rule(s) active")
        if st.button("Clear all rules"):
            st.session_state.rules = []
            st.rerun()

    st.divider()
    st.caption(
        "📖 [View full documentation](https://github.com/jwteeba/llm-data-quality-monitor/blob/main/README.md)"
    )

data_source = st.selectbox("Select data source:", ["File Upload", "PostgreSQL", "S3"])

# ══════════════════════════════════════════════════════════════════════════════
# File Upload panel
# ══════════════════════════════════════════════════════════════════════════════
if data_source == "File Upload":
    uploaded = st.file_uploader(
        "Upload a file",
        type=["csv", "parquet", "json", "xlsx", "xls"],
        help="Supported formats: CSV, Parquet, JSON, Excel",
    )
    if uploaded and st.button("Run Data Quality Check", key="file_run"):
        try:
            df = read_uploaded_file(uploaded, sample_rows)
            if df.empty:
                st.warning("The uploaded file is empty.")
            else:
                _run_quality_check(df)
        except Exception as err:
            st.error(f"Error: {err}")

# ══════════════════════════════════════════════════════════════════════════════
# PostgreSQL panel
# ══════════════════════════════════════════════════════════════════════════════
elif data_source == "PostgreSQL":
    pg_names = list(st.session_state.pg_connections.keys())
    selected_pg = st.selectbox("Saved connections:", pg_names) if pg_names else None

    if not pg_names:
        st.info("No connections yet. Add one below.")

    with st.expander("➕ Add / update PostgreSQL connection", expanded=not selected_pg):
        conn_name = st.text_input("Connection name", key="pg_name")
        host = st.text_input("Host", key="pg_host")
        port = st.number_input(
            "Port", value=5432, min_value=1, max_value=65535, key="pg_port"
        )
        dbname = st.text_input("Database name", key="pg_dbname")
        user = st.text_input("Username", key="pg_user")
        password = st.text_input("Password", type="password", key="pg_password")
        sslmode = st.selectbox(
            "SSL mode",
            ["prefer", "require", "disable", "verify-ca", "verify-full"],
            key="pg_ssl",
        )

        pg_cfg = {
            "host": host,
            "port": int(port),
            "dbname": dbname,
            "user": user,
            "password": password,
            "sslmode": sslmode,
        }

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Test connection", key="pg_test"):
                if not all([host, dbname, user]):
                    st.warning("Host, database name, and username are required.")
                else:
                    ok, msg = check_postgres_connection(pg_cfg)
                    (st.success if ok else st.error)(msg)
        with col2:
            if st.button("Save connection", key="pg_save"):
                if not conn_name:
                    st.warning("Please enter a connection name.")
                elif not all([host, dbname, user]):
                    st.warning("Host, database name, and username are required.")
                else:
                    st.session_state.pg_connections[conn_name] = pg_cfg
                    st.success(f"Connection '{conn_name}' saved for this session.")
                    st.rerun()

    if selected_pg:
        if st.button(f"🗑 Remove '{selected_pg}'", key="pg_delete"):
            del st.session_state.pg_connections[selected_pg]
            st.rerun()

        pg_config = st.session_state.pg_connections[selected_pg]

        try:
            tables = list_postgres_tables(pg_config)
        except Exception as exc:
            st.error(f"Could not fetch tables: {exc}")
            tables = []

        table_name = (
            st.selectbox("Select table:", tables)
            if tables
            else st.text_input("Table name:")
        )

        if st.button("Run Data Quality Check", key="pg_run"):
            if not table_name:
                st.warning("Please select or enter a table name.")
            else:
                try:
                    df = read_data_from_postgres(table_name, pg_config, sample_rows)
                    if df.empty:
                        st.warning("No data found in the selected table.")
                    else:
                        _run_quality_check(df)
                except Exception as err:
                    st.error(f"Error: {err}")

# ══════════════════════════════════════════════════════════════════════════════
# S3 panel
# ══════════════════════════════════════════════════════════════════════════════
elif data_source == "S3":
    s3_names = list(st.session_state.s3_connections.keys())
    selected_s3 = st.selectbox("Saved connections:", s3_names) if s3_names else None

    if not s3_names:
        st.info("No connections yet. Add one below.")

    with st.expander("➕ Add / update S3 connection", expanded=not selected_s3):
        conn_name = st.text_input("Connection name", key="s3_name")
        access_key_id = st.text_input("AWS Access Key ID", key="s3_aki")
        secret_access_key = st.text_input(
            "AWS Secret Access Key", type="password", key="s3_sak"
        )
        region = st.text_input("AWS Region", value="us-east-1", key="s3_region")
        session_token = st.text_input(
            "Session token (optional)", type="password", key="s3_token"
        )

        s3_cfg = {
            "access_key_id": access_key_id,
            "secret_access_key": secret_access_key,
            "region": region,
            "session_token": session_token or None,
        }

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Test connection", key="s3_test"):
                if not all([access_key_id, secret_access_key]):
                    st.warning("Access Key ID and Secret Access Key are required.")
                else:
                    ok, msg = check_s3_connection(s3_cfg)
                    (st.success if ok else st.error)(msg)
        with col2:
            if st.button("Save connection", key="s3_save"):
                if not conn_name:
                    st.warning("Please enter a connection name.")
                elif not all([access_key_id, secret_access_key]):
                    st.warning("Access Key ID and Secret Access Key are required.")
                else:
                    st.session_state.s3_connections[conn_name] = s3_cfg
                    st.success(f"Connection '{conn_name}' saved for this session.")
                    st.rerun()

    if selected_s3:
        if st.button(f"🗑 Remove '{selected_s3}'", key="s3_delete"):
            del st.session_state.s3_connections[selected_s3]
            st.rerun()

        s3_config = st.session_state.s3_connections[selected_s3]

        bucket = st.text_input("S3 bucket name:", key="s3_bucket")
        prefix = st.text_input("Key prefix (optional):", key="s3_prefix")

        s3_key = None
        if bucket:
            if st.button("Browse objects", key="s3_browse"):
                try:
                    st.session_state.s3_keys = list_s3_objects(
                        s3_config, bucket, prefix
                    )
                except Exception as exc:
                    st.error(f"Could not list objects: {exc}")

            if st.session_state.get("s3_keys"):
                s3_key = st.selectbox("Select object:", st.session_state.s3_keys)
            else:
                s3_key = st.text_input(
                    "Object key (e.g. data/myfile.csv):", key="s3_key_manual"
                )

        if st.button("Run Data Quality Check", key="s3_run"):
            if not bucket or not s3_key:
                st.warning("Please provide a bucket name and object key.")
            else:
                try:
                    df = read_data_from_s3(s3_config, bucket, s3_key, sample_rows)
                    if df.empty:
                        st.warning("No data found in the selected object.")
                    else:
                        _run_quality_check(df)
                except Exception as err:
                    st.error(f"Error: {err}")
