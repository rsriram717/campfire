#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

# Install dependencies
echo "Installing dependencies..."
python -m pip install -r requirements.txt

# Verify that all required environment variables are set
required_vars=("POSTGRES_URL" "SUPABASE_URL" "SUPABASE_KEY" "FLASK_ENV" "OPENAI_API_KEY")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "Error: Environment variable $var is not set."
        exit 1
    fi
done
echo "All required environment variables are set."

# Run database migrations
echo "Running database migrations..."
# Use POSTGRES_URL if it exists, otherwise use DATABASE_URL
DB_URL_TO_USE="${POSTGRES_URL:-$DATABASE_URL}"
DATABASE_URL=$DB_URL_TO_USE PYTHONPATH=. FLASK_APP=app.py flask db upgrade

echo "Build finished successfully!" 