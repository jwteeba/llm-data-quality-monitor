import os
import sys
from unittest.mock import MagicMock, patch

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))


def test_data_processing_logic():
    """Test the core data processing logic without Streamlit UI"""
    from llm_data_quality_monitor.detector.anomaly_detector import \
        detect_anomalies

    test_df = pd.DataFrame({"col1": [1, 2, 3, 4, 5], "col2": ["A", "B", "C", "D", "E"]})

    anomalies = detect_anomalies(test_df)

    assert "row_count" in anomalies
    assert "column_count" in anomalies
    assert anomalies["row_count"] == 5
    assert anomalies["column_count"] == 2


@patch("llm_data_quality_monitor.utils.utils.boto3.client")
def test_s3_integration_logic(mock_boto):
    """Test S3 data reading logic"""
    from llm_data_quality_monitor.utils.utils import read_data_from_s3

    mock_s3_client = MagicMock()
    mock_boto.return_value = mock_s3_client
    mock_s3_client.get_object.return_value = {"Body": "col1,col2\n1,A\n2,B"}

    with patch("pandas.read_csv") as mock_read_csv:
        mock_read_csv.return_value = pd.DataFrame({"col1": [1, 2], "col2": ["A", "B"]})

        df = read_data_from_s3("test-bucket", "test-key")

        assert len(df) == 2
        mock_s3_client.get_object.assert_called_once_with(
            Bucket="test-bucket", Key="test-key"
        )


def test_error_handling_logic():
    """Test error handling in data processing"""
    from llm_data_quality_monitor.detector.anomaly_detector import \
        detect_anomalies

    empty_df = pd.DataFrame()
    anomalies = detect_anomalies(empty_df)

    assert anomalies["row_count"] == 0
    assert anomalies["column_count"] == 0


def test_mysql_connection_logic():
    """Test MySQL connection logic (mocked)"""
    with patch("llm_data_quality_monitor.utils.utils.get_db_credentials") as mock_creds:
        with patch("llm_data_quality_monitor.utils.utils.create_engine") as mock_engine:
            from llm_data_quality_monitor.utils.utils import create_db_engine

            mock_creds.return_value = ("testuser", "testpass")
            mock_engine_instance = MagicMock()
            mock_engine.return_value = mock_engine_instance

            engine = create_db_engine()

            assert engine == mock_engine_instance
            assert mock_creds.call_count == 2
