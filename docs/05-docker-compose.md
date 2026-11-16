# 5. Docker Compose

`docs/05-docker-compose.md`. Airflow 3.3.2 공식 `docker-compose.yaml`을 기반으로 프로젝트에 맞게 줄였습니다.

> **검증 범위**: `docker compose config` 문법과 의존 관계, `.env` 누락 시 실패 동작을 확인했습니다. 별도 가상환경의 Airflow 3.3.2에서 `pools.json` 가져오기, DAG 파싱, 수동 실행을 확인했습니다 (Python 3.13). Docker Hub에 접근할 수 없어 **이미지 빌드와 실제 기동은 미검증**입니다. `3.3.2-python3.12` 태그는 이슈 #4에서 확인합니다. Airflow 3.4.0은 RC 단계라 3.3.2에 고정합니다.

## 공식 파일 대비 변경점

| 변경 | 이유 |
|---|---|
| CeleryExecutor → LocalExecutor | 단일 머신이라 Redis, worker가 불필요 |
| flower, triggerer 제외 | deferrable operator 미사용. Sensor는 `reschedule` 모드 |
| Postgres 분리 (`airflow-db`, `warehouse-db`) | Airflow 메타 초기화가 수집 데이터에 영향 없음 |
| 커스텀 이미지 빌드 | `_PIP_ADDITIONAL_REQUIREMENTS`는 공식 문서상 빠른 확인 용도 |
| 시크릿 기본값 제거 | `.env` 누락 시 기본 비밀번호로 뜨지 않고 실패 |
| DB, UI 포트를 `127.0.0.1`에만 공개 | 외부 노출 방지 |
| `warehouse-migrate` 단발 서비스 추가 | initdb는 빈 볼륨에서 1회만 실행되어 V0002 이후를 적용할 수 없음 |
| `airflow-init`에서 pool 가져오기 | UI 수동 설정 제거, 재현 가능 |
| `chown`을 마지막에 실행 | root가 만든 설정·로그 파일의 소유권 문제 방지 (공식 파일과 같은 순서) |
| `backup` 프로파일 서비스 | raw는 다시 받을 수 없는 원본 |

## `docker-compose.yaml`

```yaml
x-airflow-common: &airflow-common
  build:
    context: .
    dockerfile: docker/airflow/Dockerfile
  image: kr-quant-airflow:3.3.2
  env_file:
    - .env
  environment: &airflow-common-env
    AIRFLOW__CORE__EXECUTOR: LocalExecutor
    AIRFLOW__CORE__PARALLELISM: '8'
    AIRFLOW__CORE__AUTH_MANAGER: airflow.providers.fab.auth_manager.fab_auth_manager.FabAuthManager
    AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:${AIRFLOW_DB_PASSWORD:?set in .env}@airflow-db/airflow
    AIRFLOW__CORE__FERNET_KEY: ${FERNET_KEY:?set in .env}
    AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION: 'true'
    AIRFLOW__CORE__LOAD_EXAMPLES: 'false'
    AIRFLOW__CORE__DEFAULT_TIMEZONE: Asia/Seoul
    AIRFLOW__CORE__EXECUTION_API_SERVER_URL: http://airflow-apiserver:8080/execution/
    AIRFLOW__API_AUTH__JWT_SECRET: ${AIRFLOW_JWT_SECRET:?set in .env}
    AIRFLOW__API_AUTH__JWT_ISSUER: airflow
    AIRFLOW__SCHEDULER__ENABLE_HEALTH_CHECK: 'true'
    AIRFLOW_CONN_WAREHOUSE: postgresql://quant:${WAREHOUSE_DB_PASSWORD:?set in .env}@warehouse-db:5432/quant
    WAREHOUSE_DSN: postgresql://quant:${WAREHOUSE_DB_PASSWORD:?set in .env}@warehouse-db:5432/quant
    AIRFLOW_CONFIG: /opt/airflow/config/airflow.cfg
    PYTHONPATH: /opt/airflow/src
  volumes:
    - ./dags:/opt/airflow/dags
    - ./logs:/opt/airflow/logs
    - ./config:/opt/airflow/config
    - ./plugins:/opt/airflow/plugins
    - ./src:/opt/airflow/src:ro
    - ./conf:/opt/airflow/conf:ro
    - ./sql:/opt/airflow/sql:ro
    - ./data:/opt/airflow/data
  user: "${AIRFLOW_UID:-50000}:0"
  depends_on: &airflow-common-depends-on
    airflow-db:
      condition: service_healthy
    warehouse-db:
      condition: service_healthy

services:
  airflow-db:
    image: postgres:16
    environment:
      POSTGRES_USER: airflow
      POSTGRES_PASSWORD: ${AIRFLOW_DB_PASSWORD:?set in .env}
      POSTGRES_DB: airflow
    volumes:
      - airflow-db-volume:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "airflow", "-d", "airflow"]
      interval: 10s
      retries: 5
      start_period: 5s
    restart: always

  warehouse-db:
    image: postgres:16
    command:
      - postgres
      - -c
      - shared_buffers=1GB
      - -c
      - effective_cache_size=3GB
      - -c
      - work_mem=64MB
      - -c
      - maintenance_work_mem=512MB
      - -c
      - max_wal_size=4GB
      - -c
      - timezone=Asia/Seoul
    environment:
      POSTGRES_USER: quant
      POSTGRES_PASSWORD: ${WAREHOUSE_DB_PASSWORD:?set in .env}
      POSTGRES_DB: quant
    ports:
      - "127.0.0.1:5433:5432"
    volumes:
      - warehouse-db-volume:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "quant", "-d", "quant"]
      interval: 10s
      retries: 5
      start_period: 5s
    restart: always

  warehouse-migrate:
    <<: *airflow-common
    entrypoint: ["python", "-m", "quantdata.common.migrate", "/opt/airflow/sql/ddl"]
    command: []
    restart: "no"

  airflow-init:
    <<: *airflow-common
    entrypoint: /bin/bash
    command:
      - -c
      - |
        set -e
        mkdir -p /opt/airflow/{logs,dags,plugins,config,data}
        /entrypoint airflow version
        /entrypoint airflow config list >/dev/null
        airflow pools import /opt/airflow/pools.json
        chown -R "${AIRFLOW_UID:-50000}:0" /opt/airflow/{logs,dags,plugins,config,data}
    environment:
      <<: *airflow-common-env
      _AIRFLOW_DB_MIGRATE: 'true'
      _AIRFLOW_WWW_USER_CREATE: 'true'
      _AIRFLOW_WWW_USER_USERNAME: ${AIRFLOW_ADMIN_USER:-airflow}
      _AIRFLOW_WWW_USER_PASSWORD: ${AIRFLOW_ADMIN_PASSWORD:?set in .env}
    user: "0:0"

  airflow-apiserver:
    <<: *airflow-common
    command: api-server
    ports:
      - "127.0.0.1:8080:8080"
    healthcheck:
      test: ["CMD", "curl", "--fail", "http://localhost:8080/api/v2/monitor/health"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 30s
    restart: always
    depends_on: &airflow-after-init
      <<: *airflow-common-depends-on
      airflow-init:
        condition: service_completed_successfully
      warehouse-migrate:
        condition: service_completed_successfully

  airflow-scheduler:
    <<: *airflow-common
    command: scheduler
    healthcheck:
      test: ["CMD-SHELL", 'airflow jobs check --job-type SchedulerJob --hostname "$${HOSTNAME}"']
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 30s
    restart: always
    depends_on: *airflow-after-init

  airflow-dag-processor:
    <<: *airflow-common
    command: dag-processor
    healthcheck:
      test: ["CMD-SHELL", 'airflow jobs check --job-type DagProcessorJob --hostname "$${HOSTNAME}"']
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 30s
    restart: always
    depends_on: *airflow-after-init

  backup:
    image: postgres:16
    profiles: ["ops"]
    environment:
      PGPASSWORD: ${WAREHOUSE_DB_PASSWORD:?set in .env}
    volumes:
      - ${BACKUP_DIR:?set in .env}:/backup
    entrypoint: /bin/bash
    command:
      - -c
      - |
        set -euo pipefail
        f=/backup/quant-$$(date +%Y%m%d-%H%M%S).dump
        pg_dump -h warehouse-db -U quant -d quant -Fc -f "$$f"
        pg_restore --list "$$f" >/dev/null
        sha256sum "$$f" > "$$f.sha256"
        echo "backup ok: $$f"
    depends_on:
      warehouse-db:
        condition: service_healthy

volumes:
  airflow-db-volume:
  warehouse-db-volume:
```

## `docker/airflow/Dockerfile`

```dockerfile
FROM apache/airflow:3.3.2-python3.12

COPY docker/airflow/requirements.txt /requirements.txt
COPY docker/airflow/pools.json /opt/airflow/pools.json
RUN pip install --no-cache-dir \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-3.3.2/constraints-3.12.txt" \
    -r /requirements.txt
```

## `docker/airflow/requirements.txt`

```text
apache-airflow-providers-postgres
pandas
pyarrow
requests
tenacity
duckdb==2.0.0
```

constraints 기준 버전: pandas 3.0.5, pyarrow 25.0.1, psycopg2-binary 2.9.13, requests 2.34.2, tenacity 9.1.4, providers-postgres 7.0.2. duckdb는 constraints에 없어 직접 고정합니다.

## `docker/airflow/pools.json`

```json
{
  "krx_api":  {"slots": 2, "description": "KRX Open API", "include_deferred": false},
  "dart_api": {"slots": 4, "description": "OpenDART", "include_deferred": false},
  "ecos_api": {"slots": 2, "description": "ECOS", "include_deferred": false}
}
```

## `.env.example`

```dotenv
# Linux/WSL: id -u 결과
AIRFLOW_UID=1000

# 영문, 숫자만 사용 (연결 URI에 그대로 들어감)
AIRFLOW_DB_PASSWORD=
WAREHOUSE_DB_PASSWORD=
AIRFLOW_ADMIN_USER=airflow
AIRFLOW_ADMIN_PASSWORD=

# openssl rand -base64 32 | tr '+/' '-_'
FERNET_KEY=
# openssl rand -hex 32
AIRFLOW_JWT_SECRET=

# API 키
KRX_API_KEY=
DART_API_KEY=
ECOS_API_KEY=
DATAGO_API_KEY=

# Docker 볼륨 밖의 절대 경로
BACKUP_DIR=
```

## 마이그레이션 실행기

`src/quantdata/common/migrate.py`. 적용 이력을 `public.schema_migration`에 남기고, 적용한 파일이 바뀌면 실패합니다. 동시 실행은 advisory lock으로 막습니다.

```python
"""sql/ddl/V*.sql을 순서대로 한 번씩 적용한다. 적용한 파일이 바뀌면 실패한다."""
import hashlib
import os
import pathlib
import re
import sys

import psycopg2

LEDGER = """
CREATE TABLE IF NOT EXISTS public.schema_migration (
    version    integer PRIMARY KEY,
    filename   text NOT NULL,
    sha256     char(64) NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
)"""
LOCK_KEY = 7461001


def migrate(dsn: str, ddl_dir: str) -> list[str]:
    files = sorted(pathlib.Path(ddl_dir).glob("V*__*.sql"))
    conn = psycopg2.connect(dsn)
    applied_now: list[str] = []
    try:
        with conn, conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK_KEY,))
            cur.execute(LEDGER)
            cur.execute("SELECT version, sha256 FROM public.schema_migration")
            applied = {v: s.strip() for v, s in cur.fetchall()}
            for f in files:
                m = re.fullmatch(r"V(\d{4})__.+\.sql", f.name)
                if not m:
                    raise SystemExit(f"bad migration name: {f.name}")
                version = int(m.group(1))
                body = f.read_text(encoding="utf-8")
                digest = hashlib.sha256(body.encode()).hexdigest()
                if version in applied:
                    if applied[version] != digest:
                        raise SystemExit(f"{f.name} changed after it was applied")
                    continue
                cur.execute(body)
                cur.execute(
                    "INSERT INTO public.schema_migration (version, filename, sha256)"
                    " VALUES (%s, %s, %s)",
                    (version, f.name, digest),
                )
                applied_now.append(f.name)
    finally:
        conn.close()
    return applied_now


if __name__ == "__main__":
    done = migrate(os.environ["WAREHOUSE_DSN"], sys.argv[1] if len(sys.argv) > 1 else "sql/ddl")
    print("applied:", done or "nothing")
```

## 기동 절차

```bash
cp .env.example .env              # 값 입력
mkdir -p dags logs config plugins data
docker compose build
docker compose up airflow-init    # exit 0 확인
docker compose up -d
docker compose ps
```

- Airflow UI: <http://localhost:8080>
- 웨어하우스: `psql -h localhost -p 5433 -U quant quant`
- 백업: `docker compose --profile ops run --rm backup`
- 웨어하우스 초기화: `docker compose down` 후 `docker volume rm <project>_warehouse-db-volume`. **수집 데이터가 삭제되고 `observed` 이력은 복구할 수 없습니다. 먼저 백업합니다.**

## 주의사항

- 공식 문서 기준 Docker 메모리는 최소 4GB, 권장 8GB입니다. WSL2는 `.wslconfig`도 확인합니다. `warehouse-db`의 메모리 설정은 RAM 8GB 기준입니다.
- `AIRFLOW__API_AUTH__JWT_SECRET`은 모든 Airflow 서비스에서 같아야 합니다.
- `AIRFLOW__CORE__DEFAULT_TIMEZONE`과 DAG의 `timezone`은 Asia/Seoul로 통일합니다.

## 스케줄 주의사항 (Airflow 3.3.2에서 확인)

| 항목 | 값 |
|---|---|
| import | `from airflow.sdk import DAG, Asset, Param, task` |
| 타임테이블 | `from airflow.timetables.trigger import CronTriggerTimetable` |
| `catchup_by_default` | `False` |
| `create_cron_data_intervals` | `False` |
| `logical_date` | SDK 타입이 `AwareDatetime \| None`. 대상 거래일 계산에 쓰지 않음 |

대상 거래일은 `params.target_date`를 우선하고, 없으면 실행 시각 기준 직전 개장일로 계산합니다.
