from unittest.mock import MagicMock, patch

import pandas as pd

from llm_data_quality_monitor.utils.utils import (
    check_postgres_connection,
    check_s3_connection,
    create_postgres_engine,
    list_postgres_tables,
    list_s3_objects,
    read_data_from_postgres,
    read_data_from_s3,
)

PG_CFG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "testdb",
    "user": "testuser",
    "password": "testpass",
    "sslmode": "prefer",
}

S3_CFG = {
    "access_key_id": "AKIATEST",
    "secret_access_key": "secret",
    "region": "us-east-1",
    "session_token": None,
}


@patch("llm_data_quality_monitor.utils.utils.create_engine")
def test_create_postgres_engine(mock_create_engine):
    mock_engine = MagicMock()
    mock_create_engine.return_value = mock_engine

    engine = create_postgres_engine(PG_CFG)

    mock_create_engine.assert_called_once()
    call_url = mock_create_engine.call_args[0][0]
    assert "postgresql+psycopg2" in call_url
    assert "localhost" in call_url
    assert engine == mock_engine


@patch("llm_data_quality_monitor.utils.utils.create_postgres_engine")
def test_postgres_connection_success(mock_engine_fn):
    mock_engine = MagicMock()
    mock_engine_fn.return_value = mock_engine
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    ok, msg = check_postgres_connection(PG_CFG)

    assert ok is True
    assert "successful" in msg.lower()


@patch("llm_data_quality_monitor.utils.utils.create_postgres_engine")
def test_postgres_connection_failure(mock_engine_fn):
    mock_engine_fn.side_effect = Exception("connection refused")

    ok, msg = check_postgres_connection(PG_CFG)

    assert ok is False
    assert "connection refused" in msg


@patch("llm_data_quality_monitor.utils.utils.inspect")
@patch("llm_data_quality_monitor.utils.utils.create_postgres_engine")
def test_list_postgres_tables(mock_engine_fn, mock_inspect):
    mock_inspector = MagicMock()
    mock_inspect.return_value = mock_inspector
    mock_inspector.get_table_names.return_value = ["users", "orders"]

    tables = list_postgres_tables(PG_CFG)

    assert tables == ["users", "orders"]


@patch("llm_data_quality_monitor.utils.utils.MetaData")
@patch("llm_data_quality_monitor.utils.utils.Table")
@patch("llm_data_quality_monitor.utils.utils.select")
@patch("llm_data_quality_monitor.utils.utils.create_postgres_engine")
def test_read_data_from_postgres(
    mock_engine_fn, mock_select, mock_table, mock_metadata
):
    mock_engine = MagicMock()
    mock_engine_fn.return_value = mock_engine
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [("val1",), ("val2",)]
    mock_result.keys.return_value = ["col1"]
    mock_conn.execute.return_value = mock_result

    df = read_data_from_postgres("users", PG_CFG)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2


@patch("llm_data_quality_monitor.utils.utils.boto3.client")
def test_s3_connection_success(mock_boto):
    mock_client = MagicMock()
    mock_boto.return_value = mock_client

    ok, msg = check_s3_connection(S3_CFG)

    assert ok is True
    mock_client.list_buckets.assert_called_once()


@patch("llm_data_quality_monitor.utils.utils.boto3.client")
def test_s3_connection_failure(mock_boto):
    mock_boto.side_effect = Exception("invalid credentials")

    ok, msg = check_s3_connection(S3_CFG)

    assert ok is False
    assert "invalid credentials" in msg


@patch("llm_data_quality_monitor.utils.utils.boto3.client")
def test_list_s3_objects(mock_boto):
    mock_client = MagicMock()
    mock_boto.return_value = mock_client
    paginator = MagicMock()
    mock_client.get_paginator.return_value = paginator
    paginator.paginate.return_value = [
        {"Contents": [{"Key": "data/file1.csv"}, {"Key": "data/file2.csv"}]}
    ]

    keys = list_s3_objects(S3_CFG, "my-bucket", "data/")

    assert keys == ["data/file1.csv", "data/file2.csv"]


@patch("llm_data_quality_monitor.utils.utils.boto3.client")
@patch("llm_data_quality_monitor.utils.utils.pd.read_csv")
def test_read_data_from_s3(mock_read_csv, mock_boto):
    mock_client = MagicMock()
    mock_boto.return_value = mock_client
    mock_body = MagicMock()
    mock_body.read.return_value = b"col1,col2\n1,A\n2,B"
    mock_client.get_object.return_value = {"Body": mock_body}
    expected_df = pd.DataFrame({"col1": [1, 2]})
    mock_read_csv.return_value = expected_df

    df = read_data_from_s3(S3_CFG, "my-bucket", "data/file.csv")

    mock_client.get_object.assert_called_once_with(
        Bucket="my-bucket", Key="data/file.csv"
    )
    assert df.equals(expected_df)
