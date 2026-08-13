#!/usr/bin/env bash
set -e

echo "QSIP Agent launcher"

if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from example. Edit it to add API keys if needed."
fi

echo "Building and starting services..."
docker compose up -d

echo "Waiting for infrastructure..."
sleep 10

echo "Dashboard: http://localhost:3001"
echo "API: http://localhost:8083"
echo "Grafana: http://localhost:3000"
