import io

import boto3
import pandas as pd
from sqlalchemy import MetaData, Table, create_engine, inspect, select, text

SUPPORTED_S3_FORMATS = (".csv", ".parquet", ".json", ".xlsx", ".xls")


def read_uploaded_file(uploaded_file, sample_rows: int | None = None) -> pd.DataFrame:
    """Read a Streamlit UploadedFile into a DataFrame."""
    name = uploaded_file.name.lower()
    if name.endswith(".parquet"):
        df = pd.read_parquet(uploaded_file)
    elif name.endswith(".json"):
        df = pd.read_json(uploaded_file)
    elif name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(uploaded_file)
    else:
        df = pd.read_csv(uploaded_file)
    return (
        df.sample(sample_rows, random_state=42)
        if sample_rows and sample_rows < len(df)
        else df
    )


def create_postgres_engine(config: dict):
    """Create a SQLAlchemy engine from a user-supplied PostgreSQL config dict."""
    host = config["host"]
    port = config.get("port", 5432)
    dbname = config["dbname"]
    user = config["user"]
    password = config.get("password", "")
    sslmode = config.get("sslmode", "prefer")

    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"
    return create_engine(
        url,
        connect_args={"sslmode": sslmode, "connect_timeout": 10},
        pool_pre_ping=True,
        pool_recycle=3600,
    )


def check_postgres_connection(config: dict) -> tuple[bool, str]:
    """Return (success, message) after attempting a lightweight connection test."""
    try:
        engine = create_postgres_engine(config)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "Connection successful."
    except Exception as exc:
        return False, str(exc)


def list_postgres_tables(config: dict) -> list[str]:
    """Return all table names visible to the user in the connected database."""
    engine = create_postgres_engine(config)
    inspector = inspect(engine)
    return inspector.get_table_names()


def read_data_from_postgres(
    table_name: str, config: dict, sample_rows: int | None = None
) -> pd.DataFrame:
    """Read a table from PostgreSQL into a DataFrame, with optional row sampling."""
    engine = create_postgres_engine(config)
    metadata = MetaData()
    table = Table(table_name, metadata, autoload_with=engine)
    with engine.connect() as conn:
        query = select(table)
        if sample_rows:
            query = query.limit(sample_rows)
        result = conn.execute(query)
        return pd.DataFrame(result.fetchall(), columns=result.keys())


def _make_s3_client(config: dict):
    kwargs = {
        "aws_access_key_id": config["access_key_id"],
        "aws_secret_access_key": config["secret_access_key"],
        "region_name": config.get("region", "us-east-1"),
    }
    if config.get("session_token"):
        kwargs["aws_session_token"] = config["session_token"]
    return boto3.client("s3", **kwargs)


def check_s3_connection(config: dict) -> tuple[bool, str]:
    """Return (success, message) after attempting to list the configured bucket."""
    try:
        client = _make_s3_client(config)
        client.list_buckets()
        return True, "Connection successful."
    except Exception as exc:
        return False, str(exc)


def list_s3_objects(config: dict, bucket: str, prefix: str = "") -> list[str]:
    """Return object keys in *bucket* matching *prefix*."""
    client = _make_s3_client(config)
    paginator = client.get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            keys.append(obj["Key"])
    return keys


def read_data_from_s3(
    config: dict, bucket: str, key: str, sample_rows: int | None = None
) -> pd.DataFrame:
    """Read CSV, Parquet, JSON, or Excel from S3 into a DataFrame."""
    client = _make_s3_client(config)
    obj = client.get_object(Bucket=bucket, Key=key)
    body = obj["Body"].read()
    key_lower = key.lower()
    if key_lower.endswith(".parquet"):
        df = pd.read_parquet(io.BytesIO(body))
    elif key_lower.endswith(".json"):
        df = pd.read_json(io.BytesIO(body))
    elif key_lower.endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(body))
    else:
        df = pd.read_csv(io.BytesIO(body))
    return (
        df.sample(sample_rows, random_state=42)
        if sample_rows and sample_rows < len(df)
        else df
    )
