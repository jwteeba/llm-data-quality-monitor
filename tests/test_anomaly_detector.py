import os
import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

# Mock Streamlit secrets before importing anomaly_detector
with patch("streamlit.secrets") as mock_secrets:
    mock_secrets.openai.api_key = "test_api_key"

    from llm_data_quality_monitor.detector.anomaly_detector import (
        detect_anomalies,
        summarize_anomalies_llm,
    )


def test_detect_anomalies():
    """Test anomaly detection with sample data"""
    df = pd.DataFrame(
        {
            "col1": [1, 2, 3, np.nan, 100],  # has missing value and outlier
            "col2": [1, 1, 1, 1, 1],  # zero variance
            "col3": ["A", "B", "A", "B", "A"],  # low cardinality
            "col4": [1, 2, 3, 4, 5],  # normal
        }
    )

    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)

    anomalies = detect_anomalies(df)

    # Test structure
    assert "missing_values" in anomalies
    assert "duplicate_rows" in anomalies
    assert "zero_variance_columns" in anomalies
    assert "outliers" in anomalies
    assert "skewness" in anomalies
    assert "low_cardinality" in anomalies
    assert "row_count" in anomalies
    assert "column_count" in anomalies

    # Test values
    assert anomalies["missing_values"]["col1"] == 1
    assert anomalies["duplicate_rows"] == 1
    assert "col2" in anomalies["zero_variance_columns"]
    assert anomalies["row_count"] == 6
    assert anomalies["column_count"] == 4
    assert "col3" in anomalies["low_cardinality"]


def test_detect_anomalies_empty_dataframe():
    """Test anomaly detection with empty dataframe"""
    df = pd.DataFrame()

    anomalies = detect_anomalies(df)

    assert anomalies["row_count"] == 0
    assert anomalies["column_count"] == 0
    assert anomalies["duplicate_rows"] == 0
    assert anomalies["missing_values"] == {}
    assert anomalies["outliers"] == {}


def test_detect_anomalies_no_numeric_columns():
    """Test anomaly detection with no numeric columns"""
    df = pd.DataFrame({"text1": ["A", "B", "C"], "text2": ["X", "Y", "Z"]})

    anomalies = detect_anomalies(df)

    assert anomalies["outliers"] == {}
    assert anomalies["skewness"] == {}
    assert anomalies["row_count"] == 3


@patch("streamlit.secrets")
@patch("llm_data_quality_monitor.detector.anomaly_detector.OpenAI")
def test_summarize_anomalies_llm(mock_openai, mock_secrets):
    """Test LLM anomaly summarization"""
    # Mock Streamlit secrets
    mock_secrets.openai.api_key = "test_api_key"

    # Mock OpenAI response
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Test summary of anomalies"
    mock_client.chat.completions.create.return_value = mock_response

    anomalies = {
        "missing_values": {"col1": 5},
        "duplicate_rows": 2,
        "outliers": {"col2": 3},
    }

    result = summarize_anomalies_llm(anomalies)

    assert result == "Test summary of anomalies"
    mock_client.chat.completions.create.assert_called_once()
    call_args = mock_client.chat.completions.create.call_args
    assert call_args[1]["model"] == "gpt-4o-mini"
    assert len(call_args[1]["messages"]) == 2


def test_outlier_detection():
    """Test outlier detection logic specifically"""
    df = pd.DataFrame({"normal": [1, 2, 3, 4, 5], "with_outliers": [1, 2, 3, 4, 100]})

    anomalies = detect_anomalies(df)

    assert anomalies["outliers"]["normal"] == 0
    assert anomalies["outliers"]["with_outliers"] == 1


def test_skewness_calculation():
    """Test skewness calculation"""
    df = pd.DataFrame({"symmetric": [1, 2, 3, 4, 5], "skewed": [1, 1, 1, 1, 10]})

    anomalies = detect_anomalies(df)

    assert "symmetric" in anomalies["skewness"]
    assert "skewed" in anomalies["skewness"]
    assert abs(anomalies["skewness"]["symmetric"]) < 1
    assert anomalies["skewness"]["skewed"] > 1
