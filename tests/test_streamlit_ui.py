from streamlit.testing.v1 import AppTest


class TestStreamlitApp:
    """Test Streamlit UI using streamlit-testing library"""

    def test_app_initialization(self):
        """Test that the app initializes correctly"""
        at = AppTest.from_file(
            "src/llm_data_quality_monitor/dashboard/streamlit_app.py",
            default_timeout=120,
        )

        # Check title is displayed
        assert len(at.title) > 0
        assert "LLM Data Quality Dashboard" in at.title[0].value

        # Check selectbox exists
        assert len(at.selectbox) > 0
        assert at.selectbox[0].options == ["PostgreSQL", "S3"]

    def test_s3_input_fields(self):
        """Test S3 input fields appear correctly"""
        at = AppTest.from_file(
            "src/llm_data_quality_monitor/dashboard/streamlit_app.py",
            default_timeout=120,
        )

        at.selectbox[0].select("S3")
        at.run(timeout=120)

        input_labels = [inp.label.lower() for inp in at.text_input]
        assert any("bucket" in label for label in input_labels)

    def test_postgres_input_fields(self):
        """Test PostgreSQL input fields appear correctly"""
        at = AppTest.from_file(
            "src/llm_data_quality_monitor/dashboard/streamlit_app.py",
            default_timeout=120,
        )

        at.selectbox[0].select("PostgreSQL")
        at.run(timeout=120)

        input_labels = [inp.label.lower() for inp in at.text_input]
        assert any("host" in label for label in input_labels)

    def test_button_exists(self):
        """Test that the run button exists"""
        at = AppTest.from_file(
            "src/llm_data_quality_monitor/dashboard/streamlit_app.py",
            default_timeout=120,
        )

        # Check button exists
        assert len(at.button) > 0
        assert any("Run Data Quality Check" in b.label for b in at.button)
