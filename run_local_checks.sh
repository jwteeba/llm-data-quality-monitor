#!/bin/bash
# Run all CI checks manually without GitHub Actions

set -e

echo "🚀 Running local checks..."

# Install dependencies
echo "📦 Installing dependencies..."
poetry install

# Run tests
echo "🧪 Running tests..."
poetry run pytest tests/test_utils.py tests/test_anomaly_detector.py tests/test_streamlit_app.py -v --cov=src --cov-report=xml

# Run linting
echo "🎨 Running linting checks..."
pip install black flake8 isort

echo "  - Running Black..."
black --check src/ tests/

echo "  - Running isort..."
isort --check-only src/ tests/

echo "  - Running flake8..."
flake8 src/ tests/

# Run security checks
echo "🔒 Running security checks..."
pip install bandit safety

echo "  - Running Bandit..."
bandit -r src/

echo "  - Running Safety..."
safety check

# Run UI tests (optional)
echo "🖥️  Running UI tests..."
python run_ui_tests.py

echo "✅ All local checks passed! Ready to push to GitHub."