#!/usr/bin/env python3
"""
Script to run UI tests for the Streamlit application
"""
import subprocess
import sys
import os

def run_streamlit_tests():
    """Run streamlit-testing tests"""
    print("Running Streamlit-Testing tests...")
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        "tests/test_streamlit_ui.py", 
        "-v"
    ], cwd=os.path.dirname(__file__))
    return result.returncode == 0

def run_selenium_tests():
    """Run Selenium integration tests"""
    print("Running Selenium integration tests...")
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        "tests/test_selenium_integration.py", 
        "-v", "-s"
    ], cwd=os.path.dirname(__file__))
    return result.returncode == 0

def main():
    """Run all UI tests"""
    print("Starting UI test suite...")
    
    # Check dependencies
    try:
        import streamlit
        from selenium import webdriver
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Install with: pip install streamlit-testing selenium")
        return False
    
    success = True
    
    # Run streamlit-testing tests
    if not run_streamlit_tests():
        success = False
        print("❌ Streamlit-testing tests failed")
    else:
        print("✅ Streamlit-testing tests passed")
    
    # Run Selenium tests
    if not run_selenium_tests():
        success = False
        print("❌ Selenium tests failed")
    else:
        print("✅ Selenium tests passed")
    
    if success:
        print("🎉 All UI tests passed!")
    else:
        print("💥 Some UI tests failed")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)