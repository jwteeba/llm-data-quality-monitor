import os
import sys
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))


class TestStreamlitApp:
    """Test Streamlit UI using streamlit-testing library"""

    def test_app_initialization(self):
        """Test that the app initializes correctly"""
        at = AppTest.from_file(
            "src/llm_data_quality_monitor/dashboard/streamlit_app.py"
        )
        at.run()

        # Check title is displayed
        assert len(at.title) > 0
        assert "LLM Data Quality Dashboard" in at.title[0].value

        # Check selectbox exists
        assert len(at.selectbox) > 0
        assert at.selectbox[0].options == ["MySQL", "S3"]

    @patch("utils.utils.read_data_from_s3")
    @patch("detector.anomaly_detector.detect_anomalies")
    @patch("detector.anomaly_detector.summarize_anomalies_llm")
    def test_s3_workflow(self, mock_summarize, mock_detect, mock_read_s3):
        """Test S3 data processing workflow"""
        # Mock data
        mock_df = pd.DataFrame({"col1": [1, 2, 3], "col2": ["A", "B", "C"]})
        mock_read_s3.return_value = mock_df
        mock_detect.return_value = {
            "row_count": 3,
            "column_count": 2,
            "missing_values": {},
            "duplicate_rows": 0,
            "outliers": {},
            "skewness": {},
            "zero_variance_columns": [],
            "low_cardinality": {},
        }
        mock_summarize.return_value = "Test summary"

        at = AppTest.from_file(
            "src/llm_data_quality_monitor/dashboard/streamlit_app.py"
        )
        at.run()

        # Select S3 as data source
        at.selectbox[0].select("S3")
        at.run()

        # Fill in S3 details
        at.text_input[0].input("test-bucket")
        at.text_input[1].input("test-data.csv")
        at.run()

        # Click the button
        at.button[0].click()
        at.run()

        # Verify functions were called
        mock_read_s3.assert_called_once_with("test-bucket", "test-data.csv")
        mock_detect.assert_called_once()

    def test_mysql_input_fields(self):
        """Test MySQL input fields appear correctly"""
        at = AppTest.from_file(
            "src/llm_data_quality_monitor/dashboard/streamlit_app.py"
        )
        at.run()

        # Select MySQL
        at.selectbox[0].select("MySQL")
        at.run()

        # Check MySQL input field appears
        assert len(at.text_input) >= 1
        assert "table name" in at.text_input[0].label.lower()

    def test_error_handling_display(self):
        """Test error message display"""
        with patch("utils.utils.read_data_from_s3") as mock_read:
            mock_read.side_effect = Exception("S3 connection failed")

            at = AppTest.from_file(
                "src/llm_data_quality_monitor/dashboard/streamlit_app.py"
            )
            at.run()

            # Select S3 and trigger error
            at.selectbox[0].select("S3")
            at.run()
            at.text_input[0].input("bad-bucket")
            at.text_input[1].input("bad-key")
            at.run()
            at.button[0].click()
            at.run()

            # Check error is displayed
            assert len(at.error) > 0
            assert "Error:" in at.error[0].value
