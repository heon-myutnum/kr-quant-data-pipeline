# 데이터 볼륨을 지우는 타깃은 만들지 않는다 (down -v, volume rm 금지).
# raw와 observed 이력은 API로 다시 받을 수 없다. docs/00 0.7 백업 참고.

PYTHON  ?= python3
COMPOSE ?= docker compose
# 기본은 DB가 필요 없는 테스트. 예: make test MARK=integration
MARK    ?= not integration and not pit
# 예: make logs SERVICE=airflow-scheduler
SERVICE ?=

.PHONY: lint test up down logs psql migrate backup

lint:
	$(PYTHON) -m ruff check .

test:
	$(PYTHON) -m pytest -m "$(MARK)"

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=200 $(SERVICE)

psql:
	$(COMPOSE) exec warehouse-db psql -U quant -d quant

migrate:
	$(COMPOSE) run --rm warehouse-migrate

backup:
	$(COMPOSE) --profile ops run --rm backup
