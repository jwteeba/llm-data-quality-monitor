import streamlit as st

from llm_data_quality_monitor.detector.anomaly_detector import (
    detect_anomalies,
    plot_anomalies_interactive,
    summarize_anomalies_llm,
)
from llm_data_quality_monitor.utils.utils import (
    check_postgres_connection,
    check_s3_connection,
    list_postgres_tables,
    list_s3_objects,
    read_data_from_postgres,
    read_data_from_s3,
)

# ── Session state initialisation ──────────────────────────────────────────────

if "pg_connections" not in st.session_state:
    st.session_state.pg_connections = {}  # {name: config_dict}

if "s3_connections" not in st.session_state:
    st.session_state.s3_connections = {}  # {name: config_dict}


# ── Helpers ───────────────────────────────────────────────────────────────────


def _run_quality_check(df):
    anomalies = detect_anomalies(df)
    plot_anomalies_interactive(anomalies)

    if not openai_api_key:
        st.warning(
            "Enter your OpenAI API key in the sidebar to generate an AI summary."
        )
        return

    with st.spinner("🧠 Generating AI summary..."):
        summary = summarize_anomalies_llm(anomalies, openai_api_key)

    st.subheader("📋 Anomaly Summary")
    st.write(summary)

    st.subheader("🧩 Raw Anomalies")
    st.json(anomalies)

    st.subheader("🧾 Sample Data")
    st.dataframe(df.head())


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
    st.caption("📖 [View full documentation](https://github.com/jwteeba/llm-data-quality-monitor/blob/main/README.md)")

data_source = st.selectbox("Select data source:", ["PostgreSQL", "S3"])

# ══════════════════════════════════════════════════════════════════════════════
# PostgreSQL panel
# ══════════════════════════════════════════════════════════════════════════════
if data_source == "PostgreSQL":
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
                    df = read_data_from_postgres(table_name, pg_config)
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
                    df = read_data_from_s3(s3_config, bucket, s3_key)
                    if df.empty:
                        st.warning("No data found in the selected object.")
                    else:
                        _run_quality_check(df)
                except Exception as err:
                    st.error(f"Error: {err}")
