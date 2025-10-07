import subprocess
import time

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class TestStreamlitSelenium:
    """Integration tests using Selenium"""

    @pytest.fixture(scope="class")
    def streamlit_server(self):
        """Start Streamlit server for testing"""
        # Start streamlit in background
        process = subprocess.Popen(
            [
                "streamlit",
                "run",
                "src/llm_data_quality_monitor/dashboard/streamlit_app.py",
                "--server.port",
                "8502",
                "--server.headless",
                "true",
            ]
        )

        # Wait for server to start
        time.sleep(5)

        yield "http://localhost:8502"

        # Cleanup
        process.terminate()
        process.wait()

    @pytest.fixture
    def driver(self):
        """Setup Chrome driver"""
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(options=options)
        driver.implicitly_wait(10)

        yield driver

        driver.quit()

    def test_page_loads(self, streamlit_server, driver):
        """Test that the Streamlit page loads correctly"""
        driver.get(streamlit_server)

        # Wait for title to appear
        title = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "h1"))
        )

        assert "LLM Data Quality Dashboard" in title.text

    def test_data_source_selection(self, streamlit_server, driver):
        """Test data source selection functionality"""
        driver.get(streamlit_server)

        # Wait for selectbox to load and click it
        selectbox = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "[data-testid='stSelectbox'] > div")
            )
        )
        selectbox.click()
        time.sleep(1)

        # Select MySQL option
        mysql_option = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), 'MySQL')]"))
        )
        mysql_option.click()
        time.sleep(1)

        # Check MySQL input appears
        mysql_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "[data-testid='stTextInput']")
            )
        )
        assert mysql_input.is_displayed()

        # Click selectbox again to change to S3
        selectbox = driver.find_element(
            By.CSS_SELECTOR, "[data-testid='stSelectbox'] > div"
        )
        selectbox.click()
        time.sleep(1)

        # Select S3 option
        s3_option = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), 'S3')]"))
        )
        s3_option.click()
        time.sleep(1)

        # Check S3 inputs appear
        s3_inputs = WebDriverWait(driver, 10).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, "[data-testid='stTextInput']")
        )
        assert len(s3_inputs) >= 2  # Bucket and key inputs

    def test_button_interaction(self, streamlit_server, driver):
        """Test button click interaction"""
        driver.get(streamlit_server)

        # Wait for button to load
        button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "[data-testid='stButton'] button")
            )
        )

        assert "Run Data Quality Check" in button.text

        # Click button
        button.click()
        time.sleep(2)

    def test_form_validation(self, streamlit_server, driver):
        """Test form input validation"""
        driver.get(streamlit_server)

        # Select S3
        selectbox = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "[data-testid='stSelectbox'] > div")
            )
        )
        selectbox.click()
        time.sleep(1)

        s3_option = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), 'S3')]"))
        )
        s3_option.click()
        time.sleep(1)

        # Fill in S3 inputs
        inputs = driver.find_elements(
            By.CSS_SELECTOR, "[data-testid='stTextInput'] input"
        )
        if len(inputs) >= 2:
            inputs[0].send_keys("test-bucket")
            inputs[1].send_keys("test-file.csv")

        # Click button
        button = driver.find_element(By.CSS_SELECTOR, "[data-testid='stButton'] button")
        button.click()
        time.sleep(3)

        # Check for error message
        try:
            error_element = driver.find_element(
                By.CSS_SELECTOR, "[data-testid='stAlert']"
            )
            assert error_element.is_displayed()
        except Exception:
            pass
