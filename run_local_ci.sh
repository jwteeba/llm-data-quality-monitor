#!/bin/bash
# Local CI script to run all checks before pushing to GitHub

set -e

# Add bin directory to PATH
export PATH="$PWD/bin:$PATH"

echo "🚀 Running local CI checks..."

# Install act
if ! command -v act &> /dev/null; then
    echo "Installing act..."
    curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
fi

# Run GitHub Actions locally
echo "📋 Running tests..."
act -j test

echo "🎨 Running linting..."
act -j lint

echo "🔒 Running security checks..."
act -j security

bin/act  -l

echo "✅ All local CI checks passed!"