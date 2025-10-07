import os
import sys
from unittest.mock import MagicMock, patch

import pandas as pd

from llm_data_quality_monitor.utils.utils import (
    create_db_engine,
    get_db_credentials,
    read_data_from_mysql,
    read_data_from_s3,
)

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))


@patch("llm_data_quality_monitor.utils.utils.boto3.client")
def test_get_db_credentials(mock_boto_client):
    """Test getting database credentials from AWS Secrets Manager"""
    mock_client = MagicMock()
    mock_boto_client.return_value = mock_client
    mock_client.get_secret_value.return_value = {
        "SecretString": '{"username": "testuser", "password": "testpass"}'
    }

    user, password = get_db_credentials()

    assert user == "testuser"
    assert password == "testpass"
    mock_boto_client.assert_called_once_with("secretsmanager", region_name="us-east-1")


@patch("llm_data_quality_monitor.utils.utils.MYSQL_HOST", "localhost")
@patch("llm_data_quality_monitor.utils.utils.MYSQL_DB_NAME", "testdb")
@patch("llm_data_quality_monitor.utils.utils.get_db_credentials")
@patch("llm_data_quality_monitor.utils.utils.create_engine")
def test_create_db_engine(mock_create_engine, mock_get_credentials):
    """Test creating SQLAlchemy engine"""
    mock_get_credentials.return_value = ("testuser", "testpass")
    mock_engine = MagicMock()
    mock_create_engine.return_value = mock_engine

    engine = create_db_engine()

    mock_create_engine.assert_called_once_with(
        "mysql+pymysql://testuser:testpass@localhost:3306/testdb",
        connect_args={"connect_timeout": 30, "read_timeout": 30, "write_timeout": 30},
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    assert engine == mock_engine


@patch("llm_data_quality_monitor.utils.utils.MetaData")
@patch("llm_data_quality_monitor.utils.utils.Table")
@patch("llm_data_quality_monitor.utils.utils.select")
def test_read_data_from_mysql(mock_select, mock_table, mock_metadata):
    """Test reading data from MySQL database"""
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    mock_result = MagicMock()
    mock_result.fetchall.return_value = [("row1",), ("row2",)]
    mock_result.keys.return_value = ["column1"]
    mock_conn.execute.return_value = mock_result

    df = read_data_from_mysql("test_table", mock_engine)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    mock_table.assert_called_once()
    mock_select.assert_called_once()


@patch("llm_data_quality_monitor.utils.utils.boto3.client")
@patch("llm_data_quality_monitor.utils.utils.pd.read_csv")
def test_read_data_from_s3(mock_read_csv, mock_boto_client):
    """Test reading data from S3 bucket"""
    mock_s3_client = MagicMock()
    mock_boto_client.return_value = mock_s3_client
    mock_s3_client.get_object.return_value = {"Body": "csv_content"}

    mock_df = pd.DataFrame({"col1": [1, 2]})
    mock_read_csv.return_value = mock_df

    result = read_data_from_s3("test-bucket", "test-key")

    mock_s3_client.get_object.assert_called_once_with(
        Bucket="test-bucket", Key="test-key"
    )
    mock_read_csv.assert_called_once_with("csv_content")
    assert result.equals(mock_df)
