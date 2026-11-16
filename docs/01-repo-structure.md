# 1. 레포 디렉토리 구조

`docs/01-repo-structure.md`. 레포 이름 `kr-quant-data-pipeline`, 패키지 이름 `quantdata`는 가칭입니다.

```text
kr-quant-data-pipeline/
├── dags/                        # 스케줄과 의존성만 정의 (비즈니스 로직 금지)
│   ├── healthcheck.py
│   ├── krx_daily_ingest.py
│   ├── krx_backfill.py
│   ├── dart_filing_ingest.py    # v0.2.0
│   ├── dart_backfill.py         # v0.2.0
│   ├── ecos_macro_ingest.py     # v0.2.0
│   ├── weekly_recheck.py        # v0.2.0
│   └── daily_build.py           # v0.3.0
├── conf/                        # 커밋하는 프로젝트 설정 (비밀값 없음)
│   ├── sources.yaml             # 엔드포인트, 호출 상한, 변동 필드, 미확정 표시
│   ├── dq_rules.yaml            # 규칙 ID, 심각도, 임계값
│   ├── market_regimes.yaml      # 가격제한폭 등 날짜별 제도
│   └── delist.yaml              # 폐지 수익률 가정값
├── src/quantdata/
│   ├── common/                  # 설정, DB 연결, HTTP, 호출 예산, 달력, migrate.py
│   ├── ingest/                  # contract.py, base.py, krx.py, dart.py, ecos.py, manual.py
│   ├── transform/               # raw → staging 파서
│   ├── mart/                    # 종목 식별, 기업 이벤트, PIT 재무, 거시, 팩터
│   ├── validate/                # 규칙 실행, dq_result 기록, 격리
│   └── serving/                 # Parquet 스냅샷, manifest, 발행
├── sql/
│   ├── ddl/                     # V0001__init.sql부터. migrate.py만 적용
│   ├── staging/
│   ├── mart/
│   └── checks/                  # 품질 검증 SQL
├── scripts/
│   └── verify_assumptions.py    # 게이트 실측
├── docker/airflow/              # Dockerfile, requirements.txt, pools.json
├── docs/                        # 00~08, gate-results.md
├── notebooks/                   # 탐색, 팩터 분석. 파이프라인이 의존하면 안 됨
├── tests/
│   ├── unit/
│   ├── integration/             # DB가 필요한 테스트
│   ├── pit/                     # truncation, 재생성 지문 테스트
│   └── fixtures/                # 합성 응답만 저장. 원천 데이터 커밋 금지
├── data/                        # gitignore. raw_blob/, manual/, serving/, verify/
├── logs/  config/  plugins/     # Airflow 마운트. gitignore
├── docker-compose.yaml
├── .env.example                 # 값 없이 키 이름만
├── .gitignore
├── pyproject.toml
├── Makefile
└── README.md
```

`config/`는 Airflow가 쓰는 폴더라 gitignore 대상입니다. 커밋할 설정은 `conf/`에 둡니다.

## 분리 원칙

| 경계 | 규칙 | 이유 |
|---|---|---|
| `dags/` ↔ `src/` | DAG는 함수를 호출만 함 | Airflow 없이 단위 테스트 가능 |
| `ingest` ↔ `transform` | 수집은 raw에만 쓰고 파싱하지 않음 | 파싱 버그가 나도 API 재호출 없이 재처리 |
| `validate` | 원본을 고치지 않고 판정과 격리만 수행 | 검증이 데이터를 바꾸지 않음 |
| `mart` ↔ 날짜 계산 | 달력 함수만 사용 | 휴장일 오류로 인한 look-ahead 방지 |
| `serving` | 발행된 스냅샷은 불변 | 백테스트 재현성 |
| `notebooks/` | `src/`, `sql/`이 import 금지 | 재현 안 되는 코드의 유입 차단 |

## `.gitignore` 필수 항목

```gitignore
.env
data/
logs/
config/
plugins/
__pycache__/
.ipynb_checkpoints/
```

`notebooks/`는 커밋 전 출력을 지웁니다 (`nbstripout`). 출력 셀에 원천 시세가 남으면 KRX 재배포 제한에 걸릴 수 있습니다.
