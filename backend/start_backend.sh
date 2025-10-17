#!/bin/bash

# Start Backend Script
# Automatically activates virtual environment and logs to logs/ folder

echo "🚀 Starting Tau Dashboard Backend..."

# Activate virtual environment
source ../.venv/bin/activate

# Create logs directory if it doesn't exist
mkdir -p logs

# Get timestamp for log file
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="logs/backend_${TIMESTAMP}.log"

echo "📝 Logging to: ${LOG_FILE}"

# Start uvicorn with reload
uvicorn main:app --reload > "${LOG_FILE}" 2>&1 &

BACKEND_PID=$!
echo "✅ Backend started with PID: ${BACKEND_PID}"
echo "📊 View logs: tail -f ${LOG_FILE}"
echo "🛑 Stop backend: kill ${BACKEND_PID}"
echo ""
echo "Press Ctrl+C to stop watching logs (backend will continue running)"

# Follow the log file
tail -f "${LOG_FILE}"

