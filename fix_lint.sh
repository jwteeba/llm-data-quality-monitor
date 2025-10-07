#!/bin/bash
# Auto-fix linting issues

echo "🔧 Auto-fixing linting issues..."

# Install tools
pip install black isort autopep8 

# Fix formatting with Black
echo "  - Running Black..."
black src/ tests/

# Fix import sorting
echo "  - Running isort..."
isort src/ tests/

# Fix PEP8 issues
echo "  - Running autopep8..."
autopep8 --in-place --recursive src/ tests/

echo "✅ Linting issues fixed! Run flake8 to check remaining issues."