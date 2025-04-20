#!/bin/bash
# start-pipeline.sh - One command to rule them all

echo "=== Reddit WorldNews Analytics Pipeline ==="

# Create shared network
echo "Setting up Docker network..."
docker network create reddit_network 2>/dev/null || true

# Start Elasticsearch
echo "Starting Elasticsearch..."
docker-compose up -d
echo "Waiting for Elasticsearch to be ready..."
until $(curl --output /dev/null --silent --head --fail http://localhost:9200); do
  printf '.'
  sleep 5
done
echo -e "\nElasticsearch is ready!"

# Initialize Airflow DB if needed
echo "Checking Airflow database..."
if [ ! -f ".airflow_initialized" ]; then
  echo "Initializing Airflow database..."
  docker-compose -f docker-compose-airflow.yml run --rm airflow-webserver airflow db init
  
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

echo -e "\n=== All Services Running ==="
echo "- Elasticsearch: http://localhost:9200"
echo "- Airflow: http://localhost:8080 (login: admin/admin)"
echo -e "\nTo stop all services run: ./stop-pipeline.sh"