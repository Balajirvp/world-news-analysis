from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'reddit_worldnews_daily',
    default_args=default_args,
    description='Collect daily data from r/worldnews',
    schedule_interval='0 0 * * *',  # Run at midnight every day
    start_date=datetime(2025, 4, 20),
    catchup=False,
    tags=['reddit', 'elasticsearch'],
)

run_pipeline_task = BashOperator(
    task_id='run_reddit_pipeline',
    bash_command='cd /opt/airflow && python -u main.py > /opt/airflow/logs/main_output.log 2>&1',
    dag=dag,
)