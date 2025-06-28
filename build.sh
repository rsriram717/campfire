#!/bin/bash
echo "Installing dependencies..."
pip install -r requirements.txt

echo "Running database migrations..."
PYTHONPATH=. FLASK_ENV=production flask db upgrade

echo "Build completed!" 