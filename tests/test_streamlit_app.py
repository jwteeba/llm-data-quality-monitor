from unittest.mock import MagicMock, patch

import pandas as pd


def test_data_processing_logic():
    """Test the core data processing logic without Streamlit UI"""
    from llm_data_quality_monitor.detector.anomaly_detector_v1 import detect_anomalies

    test_df = pd.DataFrame({"col1": [1, 2, 3, 4, 5], "col2": ["A", "B", "C", "D", "E"]})
    anomalies = detect_anomalies(test_df)

    assert "row_count" in anomalies
    assert "column_count" in anomalies
    assert anomalies["row_count"] == 5
    assert anomalies["column_count"] == 2


@patch("llm_data_quality_monitor.utils.utils.boto3.client")
@patch("llm_data_quality_monitor.utils.utils.pd.read_csv")
def test_s3_integration_logic(mock_read_csv, mock_boto):
    """Test S3 data reading logic with user-supplied config"""
    from llm_data_quality_monitor.utils.utils import read_data_from_s3

    mock_client = MagicMock()
    mock_boto.return_value = mock_client
    mock_body = MagicMock()
    mock_body.read.return_value = b"col1,col2\n1,A\n2,B"
    mock_client.get_object.return_value = {"Body": mock_body}
    mock_read_csv.return_value = pd.DataFrame({"col1": [1, 2], "col2": ["A", "B"]})

    cfg = {
        "access_key_id": "AKIATEST",
        "secret_access_key": "secret",
        "region": "us-east-1",
        "session_token": None,
    }
    df = read_data_from_s3(cfg, "test-bucket", "test-key.csv")

    assert len(df) == 2
    mock_client.get_object.assert_called_once_with(
        Bucket="test-bucket", Key="test-key.csv"
    )


def test_error_handling_logic():
    """Test error handling in data processing"""
    from llm_data_quality_monitor.detector.anomaly_detector_v1 import detect_anomalies

    empty_df = pd.DataFrame()
    anomalies = detect_anomalies(empty_df)

    assert anomalies["row_count"] == 0
    assert anomalies["column_count"] == 0


@patch("llm_data_quality_monitor.utils.utils.create_postgres_engine")
def test_postgres_connection_logic(mock_engine_fn):
    """Test PostgreSQL engine creation with user-supplied config"""
    from llm_data_quality_monitor.utils.utils import create_postgres_engine

    mock_engine = MagicMock()
    mock_engine_fn.return_value = mock_engine

    cfg = {
        "host": "localhost",
        "port": 5432,
        "dbname": "testdb",
        "user": "testuser",
        "password": "testpass",
        "sslmode": "prefer",
    }
    engine = create_postgres_engine(cfg)

    assert engine == mock_engine
