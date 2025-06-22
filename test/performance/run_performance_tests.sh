#!/bin/bash

# Ensure we're in the project root directory
cd "$(dirname "$0")/../.." || exit 1

echo "======================================================="
echo "       Sovereign Discovery Performance Tests"
echo "======================================================="

echo -e "\n📦 Installing required packages..."
pip install pytest httpx statistics

echo -e "\n🐋 Starting Docker services..."
make clean build run-daemon

# Run the performance tests
echo -e "\n🚀 Running performance tests..."
echo "======================================================="

# Choose one of these options:

# Option 1: Run directly (shows more detailed timing information)
# Add --single-line if your terminal supports escape codes for cleaner output
python test/performance/test_discovery_performance.py "$@"

# Option 2: Run with pytest (shows more structured test results)
# pytest test/performance/test_discovery_performance.py -v "$@"

echo -e "\n======================================================="
echo "Performance test run completed!"
echo "======================================================="
