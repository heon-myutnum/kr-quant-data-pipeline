"""warehouse 연결 확인. 수동 실행 전용이며 SELECT 1만 실행한다."""

from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.sdk import DAG, task

WAREHOUSE_CONN_ID = "warehouse"


@task
def select_one() -> None:
    row = PostgresHook(postgres_conn_id=WAREHOUSE_CONN_ID).get_first("SELECT 1")
    if row is None or row[0] != 1:
        raise RuntimeError("warehouse SELECT 1 returned an unexpected result")


with DAG(
    dag_id="healthcheck",
    schedule=None,
    catchup=False,
    tags=["ops"],
    doc_md=__doc__,
):
    select_one()
