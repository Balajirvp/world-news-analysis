#!/bin/bash
# start-pipeline.sh - Enhanced with VPS mode support

echo "=== Reddit WorldNews Analytics Pipeline ==="

# Check for local development flag
LOCAL_MODE=false
if [[ "$1" == "--local" ]]; then
    LOCAL_MODE=true
    echo "🔧 Running in local development mode (Airflow + Elasticsearch + Kibana)"
else
    echo "🚀 Running in production mode (Airflow only - data goes to VPS)"
fi

# Create shared network
echo "Setting up Docker network..."
docker network create reddit_network 2>/dev/null || true

if [ "$LOCAL_MODE" = true ]; then
    # Local development mode - start Elasticsearch + Kibana + Airflow
    echo "Starting Elasticsearch..."
    docker-compose up -d elasticsearch
    echo "Waiting for Elasticsearch to be ready..."
    until $(curl --output /dev/null --silent --head --fail http://localhost:9200); do
      printf '.'
      sleep 5
    done
    echo -e "\nElasticsearch is ready!"
    
    echo "Starting Kibana..."
    docker-compose up -d kibana
else
    # Production mode (default) - skip Elasticsearch and Kibana
    echo "Skipping Elasticsearch and Kibana (Production mode - data goes directly to VPS)"
fi

# Initialize Airflow DB if needed
echo "Checking Airflow database..."
if [ ! -f ".airflow_initialized" ]; then
  echo "Initializing Airflow database..."
  docker-compose -f docker-compose-airflow.yml run --rm airflow-webserver airflow db migrate
  
  echo "Creating Airflow admin user..."
  docker-compose -f docker-compose-airflow.yml run --rm airflow-webserver airflow users create \
    --username admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com \
    --password admin
    
  touch .airflow_initialized
  echo "Airflow database initialized!"
else
  echo "Airflow database already initialized."
fi

# Start Airflow services
echo "Starting Airflow services..."
docker-compose -f docker-compose-airflow.yml up -d

echo -e "\n=== Services Status ==="
if [ "$LOCAL_MODE" = true ]; then
    echo "🔧 Local Development Mode Active:"
    echo "- Local Elasticsearch: http://localhost:9200"
    echo "- Local Kibana: http://localhost:5601"
    echo "- Airflow: http://localhost:8080 (login: admin/admin)"
    echo "- Data destination: Local Elasticsearch"
else
    echo "🚀 Production Mode Active (Default):"
    echo "- Airflow: http://localhost:8080 (login: admin/admin)"
    echo "- Data destination: VPS Elasticsearch (140.238.103.154:9200)"
    echo "- Dashboard: https://reddit-worldnews.duckdns.org"
fi

echo -e "\nTo stop all services run: ./stop-pipeline.sh"