#!/bin/bash
# run-and-shutdown.sh - Start containers, wait for DAG to complete, then shut down

echo "=== Running Reddit WorldNews Analytics Pipeline ==="

# Start all services using your existing script
./start-pipeline.sh redditworldnewspipeline

# Wait for Airflow webserver to be fully available
echo "Waiting for Airflow to be fully available..."
while ! curl --output /dev/null --silent --head --fail http://localhost:8080; do
  echo "Waiting for Airflow to be available..."
  sleep 5
done
echo "Airflow is ready!"

# Monitor the DAG execution
echo "Monitoring for DAG execution..."
MAX_WAIT_TIME=900  # 15 mins maximum wait time
start_time=$(date +%s)

while true; do
  # Generate the run_id for the scheduled run at 6 PM UTC
  run_date=$(date -u -d "yesterday 18:00" +%Y-%m-%dT%H:%M:%S)
  run_id="scheduled__${run_date}+00:00"

  # Get the state of the DAG run
  state=$(docker-compose -f docker-compose-airflow.yml exec -T airflow-scheduler airflow dags list-runs -d reddit_worldnews_daily | grep "$run_id" | awk '{print $5}')

  # Calculate elapsed time
  current_time=$(date +%s)
  elapsed=$((current_time - start_time))

  # If max time exceeded, exit the loop
  if [ $elapsed -gt $MAX_WAIT_TIME ]; then
    echo "Maximum wait time exceeded."
    break
  fi

  # Check the state of the DAG run
  if [ "$state" = "running" ]; then
    echo "DAG run $run_id is still RUNNING ⏳ ($elapsed seconds elapsed)"
    sleep 30
  elif [ "$state" = "success" ]; then
    echo "DAG run $run_id finished SUCCESSFULLY ✅"
    break
  else
    echo "DAG run $run_id status UNKNOWN ❓($elapsed seconds elapsed)"
    sleep 30
  fi
done

# Stop all containers
echo "Shutting down all containers..."
./stop-pipeline.sh

echo "=== Pipeline run complete ==="