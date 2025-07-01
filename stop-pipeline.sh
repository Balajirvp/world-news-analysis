#!/bin/bash
echo "Stopping all services..."
docker-compose -f docker-compose-airflow.yml down
docker-compose down
echo "All services stopped."