import os
import sys

from streamlit.testing.v1 import AppTest

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))


class TestStreamlitApp:
    """Test Streamlit UI using streamlit-testing library"""

    def test_app_initialization(self):
        """Test that the app initializes correctly"""
        at = AppTest.from_file(
            "src/llm_data_quality_monitor/dashboard/streamlit_app.py"
        )
        at.run(timeout=120)

        # Check title is displayed
        assert len(at.title) > 0
        assert "LLM Data Quality Dashboard" in at.title[0].value

        # Check selectbox exists
        assert len(at.selectbox) > 0
        assert at.selectbox[0].options == ["MySQL", "S3"]

    def test_s3_input_fields(self):
        """Test S3 input fields appear correctly"""
        at = AppTest.from_file(
            "src/llm_data_quality_monitor/dashboard/streamlit_app.py"
        )
        at.run(timeout=10)

        # Select S3
        at.selectbox[0].select("S3")
        at.run(timeout=10)

        # Check S3 input fields appear
        assert len(at.text_input) >= 2
        # Check for bucket and key inputs
        input_labels = [inp.label.lower() for inp in at.text_input]
        assert any("bucket" in label for label in input_labels)
        assert any("key" in label for label in input_labels)

    def test_mysql_input_fields(self):
        """Test MySQL input fields appear correctly"""
        at = AppTest.from_file(
            "src/llm_data_quality_monitor/dashboard/streamlit_app.py"
        )
        at.run(timeout=10)

        # Select MySQL
        at.selectbox[0].select("MySQL")
        at.run(timeout=10)

        # Check MySQL input field appears
        assert len(at.text_input) >= 1
        assert "table name" in at.text_input[0].label.lower()

    def test_button_exists(self):
        """Test that the run button exists"""
        at = AppTest.from_file(
            "src/llm_data_quality_monitor/dashboard/streamlit_app.py"
        )
        at.run(timeout=10)

        # Check button exists
        assert len(at.button) > 0
        assert "Run Data Quality Check" in at.button[0].label
