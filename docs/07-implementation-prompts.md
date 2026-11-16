# 7. 구현 프롬프트

`docs/07-implementation-prompts.md`. 이 프로젝트에 연결된 새 대화에 **공통 헤더 + 작업 프롬프트 1개**를 붙여 넣어 사용합니다. 프롬프트 하나가 PR 하나입니다.

## 실행 순서

| 순서 | ID | 프롬프트 | 이슈 | 마일스톤 | 선행 |
|---|---|---|---|---|---|
| 1 | P1 | 레포 구조 | #3 | v0.1.0 | - |
| 2 | P2 | Docker Compose | #4 | v0.1.0 | P1 |
| 3 | P3 | 게이트 실측 | #1, #2 | v0.1.0 | KRX 승인, P1 |
| 4 | P4 | DB 스키마 | #5 | v0.1.0 | P2, P3 |
| 5 | P5 | 공통 수집 기반 | #6 | v0.1.0 | P4 |
| 6 | P6 | KRX 수집 클라이언트 | #7 | v0.1.0 | P3, P5 |
| 7 | P7 | KRX DAG와 백필 | #8 | v0.1.0 | P2, P6 |
| 8 | P8 | 테스트와 CI | #9 | v0.1.0 | P5 |
| 9 | P9 | v0.1.0 릴리스 | #10 | v0.1.0 | 전부 |
| 10 | P10 | DART 수집 | #11 | v0.2.0 | P5, G2 |
| 11 | P11 | ECOS 수집 | #12 | v0.2.0 | P5, G3 |
| 12 | P12 | staging과 달력 | #13 | v0.3.0 | P7, P10, P11 |
| 13 | P13 | 품질 프레임워크 | #14 | v0.3.0 | P12 |
| 14 | P14 | 종목 마스터, 폐지 처리 | #15 | v0.4.0 | P13, G1, G4 |
| 15 | P15 | 기업 이벤트, 수정주가 | #16 | v0.4.0 | P14 |
| 16 | P16 | PIT 재무, TTM | #17 | v0.4.0 | P10, P14 |
| 17 | P17 | PIT 거시 | #18 | v0.4.0 | P11, P12 |
| 18 | P18 | 팩터, 노트북 | #19 | v1.0.0 | P15~P17 |
| 19 | P19 | 서빙, 발행 | #20 | v1.0.0 | P13, P18 |
| 상시 | P20 | PIT 감사 | PR마다 | - | - |
| 상시 | P21 | 장애 분석 | 장애 시 | - | - |
| 선택 | P22 | 일중 데이터 확장 설계 | - | v1 이후 | P19 |

## 공통 헤더

모든 작업 프롬프트 앞에 붙입니다.

```text
<role>
당신은 글로벌 헤지펀드에서 10년 이상 일한 시니어 퀀트 데이터 엔지니어다.
한국 시장 제도, point-in-time 설계, Python, PostgreSQL, Airflow 운영에 능숙하다.
요청의 전제까지 코드 리뷰어처럼 검토한다.
</role>

<context>
프로젝트: kr-quant-data-pipeline. KRX, OpenDART, ECOS 데이터를 look-ahead bias와
생존편향 없는 일별 데이터셋으로 만든다. 팩터 리서치, C++ 백테스터, VaR/ES 엔진에 공급한다.
스택: Python 3.12, Airflow 3.3.2 LocalExecutor, PostgreSQL 16, pandas 3, DuckDB, Parquet,
Docker Compose. 규모: 1~2인, 단일 머신. 코드만 공개하고 데이터는 공개하지 않는다.
기준 문서: 프로젝트의 docs/00~08과 docs/gate-results.md. 문서끼리 충돌하면 docs/00이 우선이다.
</context>

<rules>
1. 문서와 다르게 구현해야 하면 코드를 쓰기 전에 이유, 대안, 영향을 말하고 내 확인을 받는다.
2. API 엔드포인트, 파라미터, 호출 제한, 필드 의미를 추측하지 않는다. docs/03에서 🔵가 아니고
   gate-results.md에서 PASS가 아닌 값은 conf/sources.yaml로 분리하고 # UNVERIFIED를 붙인다.
3. docs/00 0.3의 시간 규약을 따른다. 날짜 이동은 달력 함수만 쓴다. look-ahead bias나
   생존편향 위험이 보이면 구현 전에 먼저 지적한다.
4. 모든 작업은 멱등이어야 한다. 같은 입력으로 두 번 실행하면 결과가 같아야 한다.
5. API 키, 원천 시세를 코드, 로그, 예외, fixture, 커밋, 대화에 넣지 않는다.
   fixture는 합성 데이터만 쓴다.
6. <scope> 밖 기능을 추가하지 않는다. 필요해 보이면 제안만 한다.
7. 비즈니스 로직은 src/에 둔다. DAG는 호출만 한다.
8. 임계값과 소스별 값은 conf/에 둔다. 코드에 숫자를 흩어 놓지 않는다.
9. 실행한 것과 실행하지 못한 것을 구분해 보고한다. 내 환경에서만 실행할 수 있는 명령은
   순서대로 안내하고 결과를 받아 다음을 판단한다. 실행하지 않은 테스트를 통과라고 쓰지 않는다.
</rules>

<error_handling>
외부 호출은 docs/00 0.4의 응답 분류표를 따른다. HTTP 200만으로 성공 처리하지 않는다.
- transient: 지수 백오프, 지터, 최대 5회. Retry-After를 따른다.
- not_ready: 실패로 기록하고 재시도 경로로 넘긴다. 성공이나 empty로 바꾸지 않는다.
- quota: 재시도하지 않고 해당 소스를 당일 중단한다.
- auth, bad_request, schema: 재시도하지 않는다. 원인을 민감 정보 없이 기록한다.
- 불확실하면 empty가 아니라 failed로 둔다. 데이터 누락은 조용히 넘어가면 안 된다.
- 부분 실패는 성공으로 합치지 않는다. 페이지 묶음은 전부 성공해야 완료다.
- 예외를 삼키지 않는다. catch하면 분류해서 ingest_run에 남기고 다시 던진다.
</error_handling>

<output_format>
다음 순서와 제목으로 답한다. 해당 없는 항목은 "없음"으로 쓴다.
## 1. 구현 전 점검: 문서 충돌, 게이트 미통과 전제, 퀀트 위험, 내가 결정할 사항
## 2. 변경 파일: 경로 | 신규/수정 | 한 줄 설명 (표)
## 3. 코드: 파일 경로를 제목으로. 신규 파일은 전체, 기존 파일은 변경 부분만
## 4. 검증: 명령 | 결과 | 실행 여부 (표)
## 5. 완료 기준 대조: <acceptance> 항목 | 충족 여부 | 근거 (표)
## 6. 남은 위험과 다음 단계
## 7. 커밋: Conventional Commits 메시지와 PR 설명
1번에서 내 결정이 필요하면 코드를 쓰기 전에 멈추고 질문한다.
</output_format>
```

## P1. 레포 구조

```text
<task id="P1" issue="#3">
<goal>다음 단계가 파일을 바로 추가할 수 있는 레포 골격을 만든다.</goal>
<inputs>docs/01, docs/02, docs/05의 .env.example</inputs>
<scope>
포함: 디렉토리, .gitignore, .env.example, pyproject.toml, Makefile, README.md, docs/ 이동
제외: Docker 파일, SQL, 수집 코드
</scope>
<steps>
1. docs/01의 구조를 만든다. 빈 디렉토리는 .gitkeep으로 유지한다.
2. docs/00~08을 레포 docs/로 옮기고 빈 docs/gate-results.md를 만든다.
3. pyproject.toml: src 레이아웃, 패키지 quantdata, Python 3.12, pytest, ruff, nbstripout.
   pytest marker: unit, integration, pit.
4. Makefile: lint, test, up, down, logs, psql, migrate, backup.
   데이터 볼륨을 지우는 타깃은 만들지 않는다.
5. docs/02를 루트 README.md로 옮긴다.
6. conf/ 아래 네 파일을 주석과 키 구조만 있는 초안으로 만든다.
</steps>
<acceptance>
- make lint, make test가 빈 프로젝트에서 성공한다.
- .env를 만들어도 git status에 나오지 않는다.
- import quantdata가 성공한다.
</acceptance>
브랜치 보호 설정은 내가 직접 실행하도록 명령만 안내한다.
</task>
```

## P2. Docker Compose

```text
<task id="P2" issue="#4">
<goal>클린 환경에서 README 절차만으로 전 서비스가 healthy가 되고 DAG가 warehouse에 연결된다.</goal>
<inputs>docs/05 전체</inputs>
<scope>
포함: docker-compose.yaml, docker/airflow/*, dags/healthcheck.py, 최소 migrate.py 연결
제외: 실제 수집 DAG, DDL 변경
</scope>
<steps>
1. docs/05의 파일을 그대로 추가한다.
2. apache/airflow:3.3.2-python3.12 태그 존재를 확인한다. 없으면 대안을 제시하고 멈춘다.
3. Airflow 3.3.2 공식 문서로 api-server, dag-processor, JWT 설정을 다시 대조한다.
4. dags/healthcheck.py: warehouse 연결로 SELECT 1만 실행한다.
5. docs/05 기동 절차를 실행하고 문제와 수정 내용을 문서에 반영한다.
</steps>
<edge_cases>
- 비밀번호에 URI 특수문자가 있으면 연결 문자열이 깨진다.
- WSL2 파일 권한과 메모리 제한
- airflow-init이 root로 만든 파일의 소유권
- warehouse-migrate가 airflow-db보다 먼저 끝나도 의존 순서가 깨지지 않아야 한다.
</edge_cases>
<acceptance>
- airflow-init, warehouse-migrate exit 0
- 전 서비스 healthy, UI 로그인, pool 3개 존재
- healthcheck DAG 성공
- src, conf, sql 읽기 전용, data, logs 쓰기 가능
- import quantdata 성공
- 재기동 후 warehouse 데이터 유지
- docker compose --profile ops run --rm backup이 복원 가능한 파일을 만든다
</acceptance>
docker compose config 출력을 공유할 때 비밀값이 드러나지 않게 안내한다.
</task>
```

## P3. 게이트 실측

키 원문을 대화에 붙여 넣지 말고 로컬에서 실행한 뒤 판정 요약만 공유합니다.

```text
<task id="P3" issue="#1, #2">
<goal>docs/06의 게이트 G1~G4를 실제 호출로 판정하고 결과를 docs/gate-results.md에 남긴다.</goal>
<inputs>docs/03, docs/06 설계 게이트</inputs>
<scope>
포함: scripts/verify_assumptions.py, G0 체크리스트, gate-results.md 템플릿
제외: raw 적재, 스키마 변경
</scope>
<steps>
1. 스크립트를 쓰기 전에 게이트별 호출 대상과 횟수 표를 보여준다. 총 60회 이내로 제한한다.
2. 키는 환경변수에서 읽는다. 키가 없는 소스는 건너뛰고 UNKNOWN으로 표시한다.
3. 응답 원본은 data/verify/에 저장하고 화면에는 요약만 출력한다.
4. 표본:
   - G1-1: 051170, 20180302, 코스피와 코스닥 모두
   - G1-2: 005930, 20180503, 20180504
   - G1-5: 주말, 평일 공휴일 1일, 미래 날짜
   - G1-6: 20091230, 20100104
   - G1-7: 거래정지 종목 1건 (거래량 0이고 전후로 거래가 있는 날을 응답에서 탐색)
   - G1-8: 2026-09-11, 2026-09-14 전후 대형주 거래량 비교
   - G1-13: 068270, 20180208, 20180209
   - G2-1: list.json에서 last_reprt_at=N, report_nm이 [기재정정]으로 시작하는
     사업보고서 1건. 원본과 정정 fnlttXbrl, fnlttSinglAcntAll을 같은 계정으로 비교
   - G2-6: 같은 회사의 1분기, 반기, 3분기, 사업보고서 손익과 현금흐름 필드 값 비교
5. 판정마다 아래 형식으로 출력한다.
   gate: G1-1
   verdict: PASS | FAIL | UNKNOWN
   evidence: 건수와 필드 이름만. 시세 값 금지
   calls: 사용한 호출 수
   action: 없음 또는 문서 변경 제안
6. 내가 공식 문서에서 확인할 G0 체크리스트를 만든다.
7. 결과를 받으면 docs/03 상태 표시와 스키마 변경안을 제안한다.
</steps>
<error_handling_extra>
quota 응답이면 스크립트를 즉시 멈추고 지금까지의 판정을 저장한다.
일부 소스가 실패해도 다른 소스 판정은 계속한다.
</error_handling_extra>
<stop_if>
- G1-1 FAIL: 구현 중단. G4-1과 수동 파일 대안을 비교해 추천한다.
- G2-1이 원본 수치를 얻을 수 없다고 나오면 영향 기간 추정과 pit_quality 운영안을 먼저 제시한다.
</stop_if>
<acceptance>
- 차단 게이트 G1-1, G1-2, G1-4, G1-5, G2-1, G2-6에 PASS 또는 FAIL 판정이 있다.
- gate-results.md에 원천 시세가 없다.
- 호출 수가 계획 이내다.
</acceptance>
</task>
```

## P4. DB 스키마

```text
<task id="P4" issue="#5">
<goal>게이트 결과를 반영한 스키마를 빈 볼륨에 자동 적용한다.</goal>
<inputs>docs/04 DDL, docs/05 migrate.py, docs/gate-results.md</inputs>
<scope>
포함: sql/ddl/V0001__init.sql, src/quantdata/common/migrate.py, tests/integration/test_schema.py
제외: mart 빌드 SQL, 계정 표준화 데이터
</scope>
<steps>
1. 게이트 결과로 DDL을 바꿀 내용을 표로 먼저 제시한다. ISU_CD 체계, 금액 필드, 종목 유형을 본다.
2. docs/04의 DDL과 migrate.py를 추가한다.
3. 프로젝트에 제공된 test_schema.py를 추가한다. 내용이 바뀌면 테스트를 약화하지 말고
   이유를 말한다.
4. 테스트는 임시 DB에서 실행한다. 운영 볼륨을 건드리지 않는다.
</steps>
<acceptance>
- 빈 볼륨 기동 시 스키마 4개와 as-of 함수 6개가 생성된다.
- migrate.py 재실행은 변경이 없고, 적용된 파일을 고치면 실패한다.
- test_schema.py 전체 통과.
- 역할별 권한 테스트 통과.
</acceptance>
</task>
```

## P5. 공통 수집 기반

```text
<task id="P5" issue="#6">
<goal>모든 소스가 재사용하는 수집 기반을 만든다. 호출, 판정, 저장, 기록을 한 경로로 통일한다.</goal>
<inputs>docs/00 0.4, docs/04 raw와 meta</inputs>
<scope>
포함: src/quantdata/common/, src/quantdata/ingest/contract.py, base.py
제외: 소스별 클라이언트, Airflow import
</scope>
<steps>
1. 설정: 환경변수 로드. 키 누락 시 키 이름만 표시하고 실패한다.
2. contract.py: docs/00의 BatchSource, RequestSpec, RawResponse, Outcome.
3. HTTP: requests + tenacity. 연결 5초, 읽기 30초 기본, 소스별 재정의.
4. 실행 흐름: 예산 예약 → 호출 → classify → canonicalize → raw.fn_record_fetch
   → ingest_run 종료. 호출 전 ingest_run을 running으로 만들고 긴 작업은 heartbeat를 갱신한다.
5. 호출 예산: meta.fn_reserve_quota. 재시도도 예약한다. 분당 상한은 소스별 토큰 버킷.
6. 정규화 해시: JSON, zip 멤버, NUL 처리. 변동 필드는 conf/sources.yaml.
7. request_key: 요청을 결정하는 파라미터만 정렬. 인증키 제외.
8. 마스킹: URL 경로의 ECOS 키, 쿼리의 DART 키, AUTH_KEY 헤더를 로그, 예외, DB에서 제거.
9. 대상 선정: new, recheck, backfill 계획 함수. recheck 범위는 conf 값.
10. 시작 시 하트비트 15분 초과 running을 failed(transient)로 정리한다.
</steps>
<tests>
- 같은 응답 2회: raw 1행, fetch_event 2행
- 내용 변경: raw 2행, v_revision 1행
- 키 순서만 변경: raw 1행
- 같은 zip 내용, 다른 타임스탬프: raw 1행
- NUL 포함 응답 적재 성공
- 동시 실행: raw 1행
- 예산 소진 시 호출 없이 quota
- 분류별 재시도 횟수 (transient만 재시도)
- 200 + 오류 본문이 success로 기록되지 않음
- 키 문자열이 로그, 예외, raw, ingest_run에 없음
- 프로세스 강제 종료 후 running 정리
</tests>
<acceptance>위 테스트 통과. src/quantdata/ingest가 airflow를 import하지 않는다.</acceptance>
</task>
```

## P6. KRX 수집 클라이언트

```text
<task id="P6" issue="#7">
<goal>거래일과 시장을 넣으면 일별매매가 raw에 멱등 적재된다.</goal>
<inputs>docs/03 KRX 상세, docs/gate-results.md의 G1 결과, docs/00 응답 분류표</inputs>
<scope>
포함: src/quantdata/ingest/krx.py, conf/sources.yaml의 KRX 항목, 단위 테스트
제외: 파싱, staging, DAG
</scope>
<steps>
1. KrxSource가 BatchSource를 구현한다. 대상: 코스피, 코스닥 일별매매, KOSPI 지수, 종목기본.
2. collect_daily(trade_date, market, mode)는 raw 적재와 run 기록까지만 한다.
3. 재실행 시 new 대상이 아니면 호출하지 않는다.
</steps>
<decision_table>
달력이 아직 없으므로 다음 순서로 판별한다. G1-5 결과가 다르면 먼저 수정안을 제시한다.
1. 주말: 호출 없이 empty
2. 시세 행 있음: success
3. 시세 행 없음, 같은 날 KOSPI 지수 행 있음: not_ready
4. 둘 다 없고 유예 시각 전: not_ready
5. 둘 다 없고 유예 시각 후: empty, 달력 후보를 휴장으로 기록
유예 시각은 conf 값이며 기본은 대상일 다음 평일 12:00 KST다.
지수 호출도 예산에 포함한다.
</decision_table>
<tests>
- 결정표 5개 분기
- 재실행 시 호출 0회
- 401, 429, 5xx, respCode 오류, 비JSON 200, 블록 없음
- 코드 앞자리 0과 영문 포함 코드가 문자열로 보존됨
</tests>
<acceptance>내가 실행한 특정 거래일 수집이 성공하고 재실행 시 추가 호출이 없다.</acceptance>
</task>
```

## P7. KRX DAG와 백필

```text
<task id="P7" issue="#8">
<goal>매일 전 개장일 시세를 자동 수집하고, 과거 구간은 예산 안에서 며칠에 걸쳐 채운다.</goal>
<inputs>docs/00 0.7, docs/05 스케줄 주의사항</inputs>
<scope>
포함: dags/krx_daily_ingest.py, dags/krx_backfill.py, 대상일 계산 함수
제외: staging 변환, 알림 연동
</scope>
<steps>
1. 스케줄은 CronTriggerTimetable("20 8 * * 1-5", timezone="Asia/Seoul"), catchup=False,
   max_active_runs=1. G1-12 결과가 다르면 조정안을 제시한다.
2. 대상일은 params.target_date 우선, 없으면 실행 시각 기준 직전 개장일이다.
   logical_date에 의존하지 않는다.
3. 시장별 태스크를 분리하고 pool krx_api를 쓴다. 완료 시 Asset을 갱신한다.
4. not_ready는 Sensor reschedule 모드로 5분 간격, 최대 3시간 재확인한다.
5. 놓친 날은 new 계획이 다음 실행에서 함께 잡는다. catchup으로 메우지 않는다.
6. krx_backfill: 매일 00:30. 과거 날짜 목록을 만들고 남은 예산만큼 진행한 뒤
   성공 종료한다. 다음 날 이어서 진행한다. 진행률을 로그에 남긴다.
</steps>
<edge_cases>
- 공휴일 실행 시 직전 개장일을 대상으로 한다.
- 실패한 날이 다음 날 성공으로 가려지지 않는다.
- 미갱신은 재시도 소진 시 실패로 남는다.
- 백필과 일별 수집이 같은 키를 동시에 잡으면 유일 인덱스 충돌을 건너뛰기로 처리한다.
- 일별 수집이 예산을 먼저 쓴다. 백필은 meta.fn_reserve_quota(source, 1, 0.7)로 호출한다.
</edge_cases>
<acceptance>
- 수동 실행으로 대상일 데이터가 raw에 적재된다.
- 재실행 시 raw 행 수가 같고 API 호출이 없다.
- 주말 target_date는 호출 없이 empty가 기록된다.
- 백필을 중단하고 다시 시작해도 중복 호출이 없다.
</acceptance>
</task>
```

## P8. 테스트와 CI

```text
<task id="P8" issue="#9">
<goal>회귀를 PR 단계에서 막는다. 실제 API 없이 깨끗한 환경에서 전부 실행된다.</goal>
<scope>
포함: pytest 구성, GitHub Actions, 저장소 안전 검사, PR 템플릿
제외: 실제 API 호출, 시크릿 사용
</scope>
<steps>
1. 기존 테스트의 누락을 표로 보고한 뒤 보강한다.
2. DAG import 테스트: 전 DAG 로드, import 오류 없음, 스케줄과 pool 존재.
3. 안전 검사: 키 패턴 스캔, tests/fixtures 합성 데이터 규칙, nbstripout --verify.
4. GitHub Actions: PR, main 푸시에서 ruff, unit, integration 실행. Postgres 16 서비스 컨테이너에
   migrate.py로 DDL 적용. Python 3.12, 의존성 캐시, Airflow constraints 사용.
5. PR 템플릿: 변경 내용, 검증 결과, look-ahead·생존편향 영향, 게이트 영향.
</steps>
<acceptance>
- CI가 깨끗한 환경에서 통과한다.
- 의도적으로 멱등성을 깨면 CI가 실패한다. 실패를 확인하고 되돌린다.
- 키 형태 문자열을 넣으면 안전 검사가 실패한다.
- CI 통과를 머지 조건으로 설정하는 방법을 안내한다.
</acceptance>
</task>
```

## P9. v0.1.0 릴리스

```text
<task id="P9" issue="#10">
<goal>처음 보는 사람이 README만으로 KRX 하루치를 raw에 적재할 수 있다.</goal>
<steps>
1. 클린 클론에서 README 절차를 처음부터 실행한다.
2. 실행 방법 TODO를 실제로 확인한 명령과 예상 출력으로 채운다.
3. 출처 표기 문구를 G0-2 결과로 확정한다. 미확정이면 TODO로 남기고 보고한다.
4. README 주장과 구현이 다른 부분을 표로 보고한다. mart, PIT, 수정주가는 v0.1.0에서
   스키마만 있고 데이터는 없다고 명시한다.
5. 완료 기준을 대조한다: Docker 환경, 스키마, KRX 시세 수집 DAG.
6. CHANGELOG와 태그 명령을 제시한다. 태그와 푸시는 내 확인 후 진행한다.
</steps>
<acceptance>
- 클린 환경 재현 성공.
- 아직 없는 기능을 완료처럼 쓴 문장이 없다.
- 이후 스키마 변경은 V0002부터 추가한다고 docs/04에 기록한다.
</acceptance>
</task>
```

## P10. DART 수집

```text
<task id="P10" issue="#11" milestone="v0.2.0">
<goal>공시 목록과 재무를 공시일 기준으로 증분 수집하고, 사후에 붙는 정정·철회 표시도 놓치지 않는다.</goal>
<inputs>docs/03 DART 상세, gate-results.md의 G0-3, G2 결과, docs/00 응답 분류표</inputs>
<scope>
포함: src/quantdata/ingest/dart.py, dags/dart_filing_ingest.py, dags/dart_backfill.py
제외: staging 파싱, 계정 표준화, 공시 원문 파싱
</scope>
<steps>
1. corpCode.xml: zip 멤버 해시. 내용이 같으면 raw 행을 늘리지 않는다.
2. list.json: 공시 유형별로 수집한다. corp_code 없는 조회는 3개월 이하로 나눈다.
   last_reprt_at=N으로 전 버전을 받는다. 한 기간의 전 페이지가 성공해야 완료다.
3. 재확인: 최근 14일 list.json을 매일 다시 받아 rm 변화를 감지한다.
4. 재무: 실제 정기공시가 있는 (회사, 연도, 보고서)만 호출한다.
   먼저 fnlttMultiAcnt 100개사 배치, 분석 유니버스만 fnlttSinglAcntAll을 fs_div별로 호출한다.
5. 정정이 있는 기간은 정정 전후 fnlttXbrl을 blob으로 저장한다.
6. 일정: 07:30, 18:30 KST. 백필은 일 예산의 70%까지.
</steps>
<edge_cases>
- 공시는 있는데 재무 API가 013: not_ready로 기록하고 다음 실행에서 재시도
- 021: 배치를 나눠 새 요청으로 처리
- 020: 당일 중단, 진행 위치 유지
- zip 응답 자리에 XML 오류: schema가 아니라 본문 status로 재분류
- 페이지 도중 신규 공시로 순서가 밀림: 묶음 재수집 후 건수 대조
- 014 파일 없음과 013 데이터 없음을 구분
</edge_cases>
<stop_if>G2-1, G2-6 판정이 없으면 재무 수집을 시작하지 않고 게이트 실행을 요청한다.</stop_if>
<tests>메시지 코드별 분류, 페이지 부분 실패, 재실행 호출 0회, zip 해시, rm 변화 감지, 배치 분할</tests>
<acceptance>
- 지정 기간 수집이 재실행에도 동일하다.
- 백필을 중단하고 재개해도 중복 호출이 없다.
- 호출 예산과 분당 상한을 넘지 않는다.
</acceptance>
</task>
```

## P11. ECOS 수집

```text
<task id="P11" issue="#12" milestone="v0.2.0">
<goal>등록된 거시 시리즈를 수집하고, 값이 바뀐 시점을 관측 이력으로 남긴다.</goal>
<inputs>docs/03 ECOS 상세, gate-results.md의 G3 결과</inputs>
<scope>
포함: src/quantdata/ingest/ecos.py, conf/ecos_series.yaml, dags/ecos_macro_ingest.py
제외: 공표일 처리, staging 파싱
</scope>
<steps>
1. conf/ecos_series.yaml: series_id, stat_code, cycle, item, 시차 기본값. 추측한 코드는 # UNVERIFIED.
2. 없는 시리즈는 StatisticTableList, StatisticItemList 탐색 스크립트로 찾아 제안한다.
3. 인증키가 URL 경로에 있으므로 URL 로깅을 금지한다. 마스킹 테스트를 추가한다.
4. list_total_count와 받은 행 수가 다르면 완료 처리하지 않는다.
5. ERROR-400은 기간을 나눠 새 요청으로 처리한다. ERROR-602는 quota다.
6. 전체 재수집은 주 1회다. 수집 시각이 곧 vintage 관측 시각이다.
7. 호출 간격은 300회/3분 보고값보다 보수적으로 둔다.
</steps>
<tests>
INFO-200, 200 + 오류 본문, 페이지 불일치, 키 마스킹, 시리즈 추가 시 DDL 변경 없음
</tests>
<acceptance>기준금리 시리즈 수집 성공, 재실행 시 raw 행 수 동일, fetch_event 증가</acceptance>
</task>
```

## P12. staging과 거래일 달력

```text
<task id="P12" issue="#13" milestone="v0.3.0">
<goal>raw에서 언제든 다시 만들 수 있는 정제 계층과 거래일 달력을 만든다.</goal>
<inputs>docs/04 staging, docs/gate-results.md</inputs>
<scope>
포함: src/quantdata/transform/, sql/staging/, dim_trading_calendar 빌드
제외: mart 사실 테이블, 품질 규칙
</scope>
<steps>
1. 입력은 raw.v_latest_response다. API를 호출하지 않는다.
2. 파서: 쉼표, 공백, '-', 빈 문자열을 처리한다. 코드는 문자열 dtype을 명시한다.
   staging은 소스 값을 유지한다. 0 가격을 NULL로 바꾸는 일은 mart에서 한다.
3. 재생성 단위는 request_key다. 한 트랜잭션에서 지우고 다시 넣는다.
4. dart_filing: is_correction, withdrawn_from을 rm과 보고서명에서 구한다.
   first_seen_at은 fetch_event 최초 시각이다. 재처리해도 바뀌면 안 된다.
5. ecos_observation: 직전 값과 다를 때만 행을 추가한다.
6. 달력: KOSPI 지수 존재일을 개장일로 확정한다. 미래는 주말과 공휴일 목록으로 provisional.
   실제 지수가 들어오면 confirmed로 바꾼다. 연말 폐장일, 임시공휴일을 지수 존재로 검증한다.
7. 스키마가 변한 응답은 건너뛰지 않고 실패시킨다.
</steps>
<tests>
- 같은 raw에서 두 번 빌드: 자연키 정렬 지문 동일
- 숫자 표기 변형, 코드 문자열 보존
- 철회 표시가 뒤늦게 붙은 경우
- provisional이 confirmed로 바뀌면 fn_next_open 결과 갱신
</tests>
<acceptance>재생성 지문 테스트 통과. staging 전체를 지우고 raw만으로 복구 가능.</acceptance>
</task>
```

## P13. 품질 프레임워크

```text
<task id="P13" issue="#14" milestone="v0.3.0">
<goal>품질 규칙을 코드가 아닌 선언으로 관리하고, 위반 데이터가 mart와 서빙으로 넘어가지 못하게 한다.</goal>
<inputs>docs/08 전체, docs/00 0.5</inputs>
<scope>
포함: src/quantdata/validate/, sql/checks/, conf/dq_rules.yaml, conf/market_regimes.yaml,
     dags/daily_build.py 뼈대
규칙 범위: R-IN, R-CP, R-PX, R-OPS. 나머지는 해당 마일스톤에서 추가
제외: mart 빌드 로직
</scope>
<steps>
1. 규칙 파일을 meta.dq_rule로 동기화한다.
2. 규칙은 sql/checks/<rule_id>.sql 하나이며 위반 행을 반환한다.
   반환 컬럼: entity_key, target_date, detail(jsonb)
3. 실행기는 meta.dq_exception을 제외하고 집계해 meta.dq_result에 기록한다. sample은 최대 20행.
4. quarantine 규칙은 위반 행을 meta.quarantine_row로 옮긴다. 재실행해도 중복되지 않는다.
   대상일 격리 비율이 0.5%를 넘으면 빌드를 막는다.
5. R-PX-20의 한도는 conf/market_regimes.yaml에서 날짜별로 읽는다. 상장 첫날,
   정리매매, 기준가 재설정일을 제외한다.
6. 이상치 3단계 값은 수정하지 않는다.
7. daily_build: staging → 검증 → (이후 단계 자리) 순서로 연결한다.
</steps>
<tests>
규칙마다 위반 fixture 1건과 정상 fixture 1건. 예외 등록 시 통과. 격리 재실행 중복 없음.
block 실패 시 빌드 중단. 2015-06-12와 2015-06-15의 가격제한폭 경계.
</tests>
<acceptance>
- 깨끗한 합성 데이터는 전 규칙 통과.
- 위반 fixture는 해당 규칙만 실패.
- 일별 검증 시간이 5분 이내다.
</acceptance>
</task>
```

## P14. 종목 마스터와 폐지 처리

```text
<task id="P14" issue="#15" milestone="v0.4.0">
<goal>폐지 종목과 티커 재사용을 포함한 종목 마스터와, 시점별 유니버스, 폐지 수익률을 완성한다.</goal>
<inputs>docs/00 생존편향 체인, docs/04 종목 키, gate-results.md의 G1-1, G1-3, G1-4, G1-9, G1-10, G1-13, G2-4, G2-7, G4</inputs>
<scope>
포함: src/quantdata/ingest/manual.py, src/quantdata/mart/security.py, fact_daily_price 적재,
     map_security_corp, fact_delisting, R-SB 규칙, conf/delist.yaml
제외: 기업 이벤트, 수정주가 계산
</scope>
<steps>
1. manual 어댑터: data/manual의 상장폐지 파일을 content hash와 함께 source='manual'로 raw에 적재한다.
2. docs/04의 식별 규칙을 구현한다. dim_security는 증분 갱신만 한다. truncate 금지.
3. fact_daily_price 적재: 거래 없는 날 OHLC NULL, 0 종가는 직전 종가, 날짜순 삽입.
   OHLC 위반은 R-PX-01에서 이미 격리된 상태여야 한다.
4. security_type을 SECUGRP_NM, KIND_STKCERT_TP_NM로 분류한다. 판정 불가는 other로 두고 보고한다.
5. delist_date: 공식 목록 우선. 없으면 fn_next_open(last_traded_date), source=last_seen.
   단, N개장일 이상 부재가 지속된 경우에만 부여한다. N은 conf 값이다.
6. 코드가 유지되는 시장 이전은 폐지로 처리하지 않는다.
7. map_security_corp: docs/00의 연결 순서를 따르고 method를 기록한다. 기간 겹침 금지.
8. fact_delisting: 사유 문자열을 reason_group으로 분류하고 수익률을 docs/00 표대로 계산한다.
   합병 대가를 찾지 못하면 unknown으로 두고 보고한다.
</steps>
<edge_cases>
티커 재사용, 이전상장, 장기 거래정지 후 재개, 분할 재상장, 스팩 합병, 외국 주권, 우선주.
동일 코드의 ISIN 변경.
</edge_cases>
<tests>
위 사례의 합성 fixture. 재실행 시 security_id 불변. 공식 목록 건수 대조. 연결률 리포트를
상장, 폐지 코호트로 분리.
</tests>
<acceptance>
- R-SB-01~04 통과.
- 2018-03-02 유니버스에 051170이 있고 폐지일 이후에는 없다.
- 재생성해도 security_id가 바뀌지 않는다.
</acceptance>
<stop_if>G1-1 FAIL이면 시작하지 않는다.</stop_if>
</task>
```

## P15. 기업 이벤트와 수정주가

```text
<task id="P15" issue="#16" milestone="v0.4.0">
<goal>분할, 증자, 감자, 현금배당을 이중 적용 없이 반영한 수익률 계열을 만든다.</goal>
<inputs>docs/00 수정주가와 수익률, gate-results.md의 G1-2, G1-11, G2-8</inputs>
<scope>
포함: src/quantdata/mart/corp_action.py, fact_corp_action, evidence, fact_dividend, ret_price, cum_factor,
     R-CA 규칙
제외: 팩터 계산
</scope>
<steps>
1. 후보 탐지: 기준가 <> 전일 종가인 날. 공차를 두지 않는다. 상장 첫날은 제외한다.
2. 종목·ex_date당 fact_corp_action 1행. 탐지 경로는 evidence에 추가한다.
3. DART 근거가 ±5개장일 안에 있으면 confirmed. 유형을 채운다.
4. candidate는 누적곱에 포함한다. rejected는 사람이 사유를 남길 때만 쓴다.
5. 변경된 종목만 mart.fn_refresh_cum_factor로 재계산한다.
6. 현금배당은 fact_dividend에 저장한다. ex_date = mart.fn_ex_date(기준일).
   known_from은 배당액 공시의 다음 개장일이다. 기준일을 12월 말로 가정하지 않는다.
   정정된 배당은 새 known_from 행이다.
7. 총수익은 mart.v_daily_return을 사용한다.
</steps>
<edge_cases>
같은 날 복합 이벤트, 장기 거래정지 뒤 기준가 재설정, 인적분할 재상장, 감자 후 재상장,
정리매매 기간의 기준가, 이벤트 후행 입력.
</edge_cases>
<tests>
- 2,650,000 × 0.02 = 53,000, as_of가 분할 전이면 미적용
- 탐지 경로 2개여도 1회 적용
- 이벤트를 늦게 입력해도 그 종목만 재계산되고 결과가 같음
- 수익률 복리와 수정 종가 비율 일치
- 현금배당은 ret_total에만 반영
</tests>
<acceptance>R-CA-04, R-CA-05 통과. candidate 잔량과 사유별 건수 리포트.</acceptance>
<stop_if>G1-2 FAIL이면 대안 비교 후 내 확인을 받는다.</stop_if>
</task>
```

## P16. PIT 재무와 TTM

```text
<task id="P16" issue="#17" milestone="v0.4.0">
<goal>공시 시점 기준으로 재현되는 재무 사실과 TTM을 만든다.</goal>
<inputs>docs/04 재무 절, 재무 금액 적재 규칙, gate-results.md의 G2-1, G2-2, G2-5, G2-6</inputs>
<scope>
포함: src/quantdata/mart/financial.py, fact_financial_pit, dim_account_std, map_account_std, R-PIT-01, 03, 05, R-FN
제외: 팩터 계산
</scope>
<steps>
1. 표준 계정 범위: revenue, operating_income, net_income, net_income_controlling,
   total_assets, total_liabilities, total_equity, equity_controlling, cfo.
2. 매핑은 account_id 우선, 없으면 계정명. 업종별(일반, 은행, 보험, 증권) 규칙을 분리한다.
   미매핑은 버리지 않고 비율을 리포트한다.
3. available_from = fn_next_open(값을 담은 공시의 rcept_dt). rcept_dt는 list.json에서 조인한다.
4. version_seq는 (rcept_dt, rcept_no) 순서로 결정적으로 부여한다.
5. pit_quality: 공시 후 7일 안에 수집하면 observed, XBRL 원본이면 xbrl_original,
   기간 공시가 1건뿐이면 single_version, 그 외 backfill_latest.
6. value_basis, fiscal_months, period_end를 docs/04 표대로 채운다. 12월 결산을 가정하지 않는다.
7. withdrawn_from을 반영한다.
8. fn_financial_asof, fn_financial_latest, fn_financial_ttm을 그대로 사용한다. 팩터가 직접 fact를 읽지 않는다.
</steps>
<edge_cases>
비12월 결산, 결산월 변경, 연결 전환, 별도만 있는 회사, 정정에서 계정 삭제, 철회, 같은 날 복수 공시,
금융업 계정, 금액 '-', 외화 표시 재무제표.
</edge_cases>
<tests>
docs/04의 재무 회귀 테스트 전체. 위 edge case fixture. 공시 전날 조회 시 값 없음.
</tests>
<acceptance>
- 연도별 pit_quality 비율 리포트가 나온다.
- backfill_latest 구간을 표시해 리서치에서 제외할 수 있다.
- 재생성 지문 동일.
</acceptance>
</task>
```

## P17. PIT 거시

```text
<task id="P17" issue="#18" milestone="v0.4.0">
<goal>거시 값을 대상 기간이 아니라 알 수 있었던 날 기준으로 조회한다.</goal>
<inputs>docs/00 0.3, docs/04 거시, staging.ecos_observation</inputs>
<scope>
포함: fact_macro_pit, fact_macro_release, dim_macro_series, 공표 일정 수동 파일 적재, R-MC 규칙
제외: 거시 팩터
</scope>
<steps>
1. obs_time을 obs_period_end로 변환한다. A, S, Q, M, SM, D 형식별 테스트를 둔다.
2. available_from 우선순위: 파이프라인 최초 관측 > 공표 일정 > lag_rule_days.
   최초 관측을 쓰려면 수집 시작 이후의 값이어야 한다. available_basis에 기록한다.
3. 공표일이 개장일이 아니거나 공표 시각이 장중이면 보수적으로 다음 개장일을 쓴다.
4. 첫 수집 이전 구간은 최종치이므로 원데이터가 아니다. 시차 규칙으로 시점만 보수화하고
   리포트에 표시한다.
5. 전 구간 값이 함께 바뀌면 기준연도 개편으로 보고 is_rebased를 표시한다.
6. 일별 시리즈는 관측일 다음 개장일부터 사용한다.
</steps>
<tests>
3월 CPI가 4월 공표 전에 안 보임. 수정치가 수정 시점 이후에만 보임. 기준연도 개편 처리.
주기별 period_end 변환.
</tests>
<acceptance>전 시리즈 fn_macro_asof 조회 가능. available_basis 비율 리포트.</acceptance>
</task>
```

## P18. 팩터와 분석 노트북

```text
<task id="P18" issue="#19" milestone="v1.0.0">
<goal>PIT가 검증된 팩터 테이블과 재현 가능한 분석 노트북을 만든다.</goal>
<inputs>docs/00 신호·체결 규약, 시장 구조 변화, 앞선 mart 함수</inputs>
<scope>
포함: src/quantdata/mart/factor.py, sql/mart/, mart.factor_daily, tests/pit/, notebooks/factor_analysis.ipynb
제외: 전략 추천, 주문, 투자 조언
</scope>
<definitions>
모든 값은 signal_date = T 기준이다.
- size = ln(회사 전 종목 시가총액)
- ep = TTM 지배주주 순이익 / 회사 전 종목 시가총액. 없으면 TTM 순이익
- bp = 최신 지배주주 자본 / 회사 전 종목 시가총액
- per = 1 / ep, pbr = 1 / bp. ep, bp가 양수일 때만 표시
- roe = TTM 지배주주 순이익 / 최근 두 결산 지배주주 자본 평균
- mom_12_1 = t-252부터 t-21까지 ret_total 복리. 유효 관측 200일 미만이면 NULL
- vol_60 = 60개장일 ret_price 표준편차
- liq_60 = 60개장일 거래대금 중앙값. KRX 기준임을 표시
</definitions>
<steps>
1. 리밸런스는 월말 개장일 신호, 다음 개장일 시가 체결이다.
2. 유니버스: fn_universe 보통주, 상장 후 60개장일 이상, T일 거래 존재.
   지수 편입 여부로 과거 유니버스를 만들지 않는다.
3. 날짜별로 fn_financial_asof를 반복 호출하지 말고, 공시 버전을 유효 구간으로 펼쳐 조인한다.
   결과는 표본 날짜에서 as-of 함수와 일치해야 한다.
4. winsorize는 단면 1%/99%, 표준화는 날짜별로 한다. 원값도 저장한다.
5. 노트북: 커버리지, IC, 5분위 수익률, 회전율, 거래 비용 가정 민감도.
6. 강건성: 2016년 이후, 2025-03-04 전후 분리, 공매도 금지 기간 표시, backfill_latest 제외,
   폐지 수익률 가정 변경, 은행·보험·증권 제외.
7. 코드와 집계 차트만 공개한다. 원천 시세 행을 출력하지 않고 출처를 표기한다.
</steps>
<tests>
- Truncation: T까지 자른 DB와 전체 DB의 T일 팩터 일치. 표본은 정정, 분할, 폐지 사례를 포함
- 팩터가 신호 다음 날 수익률을 미리 쓰지 않음을 시프트 테스트로 확인
- 재생성 지문 동일
</tests>
<acceptance>
- R-PIT-02 통과.
- 노트북이 build_id를 입력으로 재실행된다.
- 결과에 표본 기간, 유니버스, 비용 가정, 한계를 적는다. 과거 성과를 전략 추천으로 쓰지 않는다.
</acceptance>
</task>
```

## P19. 서빙과 발행

```text
<task id="P19" issue="#20" milestone="v1.0.0">
<goal>사용처가 PostgreSQL 없이 불변 스냅샷을 읽고, 품질을 통과한 빌드만 발행되게 한다.</goal>
<inputs>docs/00 0.6</inputs>
<scope>
포함: src/quantdata/serving/, daily_build 완성, docs/data-contract.md, 로더 예제
제외: C++ 엔진 구현
</scope>
<steps>
1. build_id = data_cutoff + git_sha. meta.build를 building으로 만든다.
2. docs/00의 폴더 구조로 Parquet을 쓴다. zstd, 날짜·종목 정렬, 행 그룹 25만.
   임시 폴더에 쓰고 검증 후 원자적으로 이름을 바꾼다.
3. manifest: 행 수, 파일 해시, schema_version, dq 요약, pit_quality 비율.
4. 스냅샷 행 수와 합계를 mart와 대조한 뒤 validated로 바꾼다.
5. meta.fn_publish_build로 발행한다. 실패하면 직전 빌드를 유지한다.
6. live는 매일 전진, research는 수동 전진이다.
7. 보관: 발행 빌드 최근 30개와 월말 빌드 유지. 팩터는 PostgreSQL에 최근 2개 빌드만 둔다.
8. docs/data-contract.md: 컬럼, 타입, 단위, NULL 의미, 시간 규약, schema_version 변경 규칙.
9. Python 로더 예제: pointer를 읽고 manifest 해시와 data_cutoff를 검증한다.
</steps>
<edge_cases>
빌드 도중 실패, 디스크 부족, 같은 build_id 재실행, 발행 중 사용처가 읽는 경우,
data_cutoff가 직전 개장일이 아닌 경우.
</edge_cases>
<tests>
block 실패 시 발행 안 됨. 빌드 실패 시 포인터 불변. 같은 입력의 파일 해시 동일. manifest 변조 탐지.
</tests>
<acceptance>
- 개장일 08:45 전 발행을 3일 연속 달성하거나 병목을 측정해 보고한다.
- 전체 패널 Arrow 로드 시간을 실제 데이터로 측정해 docs/00에 갱신한다.
</acceptance>
</task>
```

## P20. PIT 감사 (PR마다)

```text
<task id="P20">
<goal>이 변경이 look-ahead bias, 생존편향, 멱등성을 깨는지 리뷰한다. 코드를 고치지 않는다.</goal>
<inputs>[PR diff 또는 변경 파일 붙여 넣기]</inputs>
<checklist>
1. 시간: 대상 시점으로 조인하는 곳, + 1 day, 미래 값을 쓰는 window, 전체 기간 통계로 계산한 임계값
2. 재무: rcept_dt 대신 period_end, 정정 소급, 철회 무시, 누적과 분기 혼동, CFS 고정
3. 가격: 수정 종가 저장, 이벤트 이중 적용, T일 종가 체결, 0 가격, 거래정지일
4. 생존편향: 현재 상장 목록, 폐지 종목 필터, inner join으로 사라지는 행, 폐지 수익률 누락
5. 식별: 티커 조인, 코드 숫자 변환, security_id 재생성, 기간 겹침
6. 멱등: 실행 시각 의존, 순서 의존, 재실행 시 행 증가
7. 운영: 예외 삼킴, 빈 응답 성공 처리, 부분 실패 합치기, 키 노출
</checklist>
<output_format>
발견 사항만 심각도순 표로 쓴다: 심각도 | 파일:줄 | 문제 | 실패 시나리오 | 수정 제안
심각도: 차단, 높음, 보통. 추측이면 "확인 필요"로 표시한다.
발견이 없으면 "차단 항목 없음"과 확인한 범위를 쓴다. 공통 헤더의 output_format은 쓰지 않는다.
</output_format>
</task>
```

## P21. 장애 분석

```text
<task id="P21">
<goal>실패 원인을 좁히고 데이터 영향 범위를 확정한 뒤 복구 절차를 제시한다.</goal>
<inputs>
증상: [DAG, 태스크, 시각]
로그: [키와 시세를 제거한 로그]
조회 결과: [meta.v_pipeline_health, ingest_run, dq_result 요약]
</inputs>
<steps>
1. 가설을 가능성순으로 쓰고 각각을 가르는 확인 명령을 제시한다.
2. docs/00 응답 분류표와 장애 표에 대응시킨다.
3. 영향 범위: 어떤 날짜, 소스, 빌드, 발행물이 오염됐는가.
4. 복구: raw에서 재처리로 끝나는지, 재호출이 필요한지, 호출 수는 얼마인지.
5. 재발 방지 테스트와 품질 규칙을 제안한다.
</steps>
<constraints>
파괴적 명령은 실행하지 말고 영향과 롤백을 함께 제시해 내 확인을 받는다.
raw를 수정하는 복구는 제안하지 않는다.
</constraints>
</task>
```

## P22. 일중 데이터 확장 설계

```text
<task id="P22">
<goal>분봉 또는 틱 데이터 추가가 타당한지 판단하고 설계안을 낸다. 코드는 쓰지 않는다.</goal>
<inputs>docs/00 0.4 StreamSource 계약, [필요한 전략과 주기]</inputs>
<steps>
1. 일중 데이터가 필요한 연구 질문을 먼저 정의한다. 일별로 답할 수 있으면 그렇게 결론 낸다.
2. 소스 후보를 공식 문서로 비교한다: 제공 범위, 과거 이력, 호출 제한, 비용, 이용 조건,
   KRX와 NXT 포함 여부. 추측 값은 미확인으로 표시한다.
3. 저장 추정: 일 메시지 수, 압축 후 크기, 1년 보관 비용.
4. 수집 설계: 상시 컨테이너, 이벤트 시각과 수신 시각, seq 공백 탐지, 재연결 복구, 장애 시 일별 대조.
5. 일중 봉을 KRX 일별 시세와 대조하는 품질 규칙을 정의한다.
6. 이행 비용과 대안을 비교해 진행, 보류, 중단 중 하나를 추천한다.
</steps>
<output_format>결론 먼저, 근거 표, 미확인 사항 순서로 쓴다. 공통 헤더의 코드 항목은 생략한다.</output_format>
</task>
```

## 사용 시 주의사항

- API 키와 응답 원본은 대화에 붙여 넣지 않습니다. 게이트 결과는 판정, 필드 이름, 건수만 공유합니다.
- 게이트 결과로 문서가 바뀌면 다음 프롬프트 전에 프로젝트 문서도 갱신합니다.
- `<stop_if>`에 걸리면 다음 프롬프트로 넘어가지 않습니다.
- PR마다 P20을 실행합니다. 작성한 대화와 다른 새 대화에서 실행해야 자기 코드를 검토하는 편향이 줄어듭니다.
