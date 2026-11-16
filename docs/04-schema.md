# 4. DB 스키마

`docs/04-schema.md`. PostgreSQL 16 기준입니다. 아래 DDL은 `sql/ddl/V0001__init.sql`로 옮겨 사용합니다.

> **검증 범위**: PostgreSQL 16.15에서 DDL 적용과 합성 데이터 회귀 테스트 75개를 통과했습니다. 동시 적재, 호출 예산 경합, 파티션 가지치기, 권한, 마이그레이션 재실행을 포함합니다. 실제 API 데이터로는 검증하지 않았습니다.

> KRX, DART 필드는 게이트 통과 전입니다. 결과에 따라 컬럼과 키가 바뀔 수 있습니다. 코드 작성 전이므로 바뀌면 `V0001`을 직접 고칩니다. **v0.1.0 태그 이후에는 `V0002`부터 추가만 합니다.**

## 계층 구조

| 스키마 | 역할 | 쓰기 방식 | 키 |
|---|---|---|---|
| `meta` | 실행 이력, 호출 예산, 품질 결과, 빌드 | append 위주 | `run_id`, `build_id` |
| `raw` | API 응답 원본과 관측 로그 | append-only (트리거로 강제) | 요청 + 내용 해시 |
| `staging` | 타입 정제 | 멱등 재생성 | 소스 자연키 |
| `mart` | 분석용 조회 | 멱등 재생성 | `security_id` + 날짜 |

## 설계 결정

### raw: 내용 불변 + 관측 로그

| 대안 | 장점 | 단점 |
|---|---|---|
| **응답 테이블 + `fetch_event` (채택)** | 내용 행이 불변이고 A→B→A 재출현도 정확 | 테이블 1개 추가 |
| 응답 테이블에 `last_fetched_at` 갱신 | 단순 | 불변성 포기, `response_id` 기준 최신 판단이 틀림 |

- 현재 내용은 `raw.v_latest_response`, 정정 시점은 `raw.v_revision`으로 조회합니다.
- 적재는 `raw.fn_record_fetch` 하나로만 합니다. 동시 호출에서도 내용 행은 1개입니다.
- `request_params`에 인증키가 들어가면 CHECK가 적재를 실패시킵니다.

### 종목 키: 내부 `security_id`

티커는 재사용되고 ISIN도 변경 가능성을 배제할 수 없어(G1-10) `dim_security`의 키로 쓰지 않습니다. 시점별 코드, ISIN, 시장, 종목 유형은 `dim_security_history`에 두고 두 가지 겹침을 DB 제약으로 막습니다.

| 제약 | 막는 문제 |
|---|---|
| 같은 코드의 기간 겹침 금지 | 티커 재사용 시 한 코드가 두 종목으로 해석 |
| 같은 종목의 기간 겹침 금지 | 시점 조인에서 행이 2배로 증가 |

**`security_id`는 재생성하지 않습니다.** `dim_security`는 증분 갱신만 하며, truncate하면 하위 모든 키가 바뀝니다.

식별 규칙: 입력 `(trade_date, market, isu_cd)`

1. 해당 날짜에 유효한 코드가 있으면 그 `security_id`
2. 코드가 과거에 있었고 ISIN이 같거나, 공백이 공식 폐지 없이 거래정지로 설명되면 같은 종목. 코드가 같고 시장만 바뀌면 이력 행만 추가
3. 공식 폐지 후 코드가 다시 쓰이면 새 `security_id`
4. 처음 보는 코드면 새 `security_id`
5. 판정 불가면 격리

### 재무: 공시 단위 스냅샷

as-of 조회는 계정별 최신이 아니라 **기간별 최신 공시를 고른 뒤 그 공시의 행 전체**를 돌려줍니다. 정정에서 사라진 계정이 이전 값으로 남지 않습니다. 철회된 공시는 `withdrawn_from`부터 제외되어 이전 버전이 다시 유효해집니다.

| `pit_quality` | 의미 | 신뢰도 |
|---|---|---|
| `observed` | 파이프라인이 공시 직후 수집 | 높음 |
| `xbrl_original` | 해당 접수번호의 XBRL 원본 | 높음 |
| `single_version` | 백필이지만 해당 기간 공시가 1건뿐이라 정정 없음 | 높음 |
| `backfill_latest` | 정정이 있는 기간의 최신값. 원본 미확보 | 낮음 |

`backfill_latest`의 `available_from`은 **그 값을 담은 공시**의 다음 개장일입니다. 정정 수치를 원본 공시일로 소급하지 않습니다. 대가로 원본 공시일부터 정정일까지 값이 비고, 이 구간은 XBRL 수집으로 메웁니다.

## point-in-time 처리

| 데이터 | 기준 컬럼 | 규칙 | 강제 수단 |
|---|---|---|---|
| 재무 | `available_from` | `rcept_dt` 다음 개장일 이후 | CHECK + 달력 트리거 |
| 수정주가 | `ex_date` | `(t, as_of]` 이벤트만 반영 | `fn_adj_price` |
| 배당 | `known_from` | 신호는 공시 이후, P&L은 ex_date | 규약 + R-PIT-02 |
| 유니버스 | `list_date`, `delist_date` | 시점별 상장 종목. 마지막 거래일까지 포함 | `fn_universe`, CHECK |
| 거시 | `available_from` | 관측 스냅샷 > 공표 일정 > 보수적 시차 | `fn_macro_asof` |
| 팩터 | `trade_date`, `build_id` | 빌드별 불변 | truncation 테스트 |

## DDL

```sql
-- sql/ddl/V0001__init.sql
-- PostgreSQL 16. 적용은 quantdata.common.migrate만 수행한다 (initdb 마운트 금지).
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE SCHEMA meta;
CREATE SCHEMA raw;
CREATE SCHEMA staging;
CREATE SCHEMA mart;

-- 역할: 로그인 없는 그룹 역할. 로그인 사용자는 배포 시 부여한다.
DO $$
DECLARE r text;
BEGIN
    FOREACH r IN ARRAY ARRAY['quant_ingest', 'quant_transform', 'quant_research'] LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
            EXECUTE format('CREATE ROLE %I NOLOGIN', r);
        END IF;
    END LOOP;
END $$;

-- ===== meta: 실행 이력 =====
CREATE TABLE meta.ingest_run (
    run_id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dag_id         text,
    airflow_run_id text,
    task_try       integer,
    source         text NOT NULL CHECK (source IN ('krx', 'dart', 'ecos', 'datago', 'manual')),
    endpoint       text NOT NULL,
    request_key    text NOT NULL,
    mode           text NOT NULL DEFAULT 'new' CHECK (mode IN ('new', 'recheck', 'backfill')),
    status         text NOT NULL CHECK (status IN ('running', 'success', 'empty', 'failed')),
    error_class    text CHECK (error_class IN
        ('auth', 'quota', 'transient', 'not_ready', 'schema', 'bad_request', 'unknown')),
    row_count      integer,
    error          text,
    started_at     timestamptz NOT NULL DEFAULT now(),
    heartbeat_at   timestamptz NOT NULL DEFAULT now(),
    finished_at    timestamptz,
    CHECK ((status = 'failed') = (error_class IS NOT NULL))
);
-- 같은 요청을 동시에 두 번 호출해 호출 예산을 낭비하지 않는다
CREATE UNIQUE INDEX ingest_run_one_running_uq
    ON meta.ingest_run (source, endpoint, request_key) WHERE status = 'running';
CREATE INDEX ingest_run_done_idx
    ON meta.ingest_run (source, endpoint, request_key) WHERE status IN ('success', 'empty');

-- ===== meta: 호출 예산. 프로세스 재시작, 동시 태스크에서도 정확해야 한다 =====
CREATE TABLE meta.api_quota_policy (
    source     text PRIMARY KEY,
    hard_limit integer NOT NULL CHECK (hard_limit > 0),
    soft_limit integer NOT NULL CHECK (soft_limit > 0),
    CHECK (soft_limit <= hard_limit)
);

CREATE TABLE meta.api_quota_usage (
    source     text NOT NULL REFERENCES meta.api_quota_policy (source),
    quota_date date NOT NULL,
    used       integer NOT NULL DEFAULT 0 CHECK (used >= 0),
    PRIMARY KEY (source, quota_date)
);

-- p_share: 이 호출자가 쓸 수 있는 soft_limit 비율. 백필은 0.7로 호출해 일별 수집 몫을 남긴다.
CREATE FUNCTION meta.fn_reserve_quota(p_source text, p_n integer DEFAULT 1, p_share numeric DEFAULT 1)
RETURNS boolean LANGUAGE plpgsql AS $$
DECLARE
    v_date  date := (now() AT TIME ZONE 'Asia/Seoul')::date;
    v_limit integer;
    v_ok    boolean;
BEGIN
    SELECT soft_limit INTO STRICT v_limit FROM meta.api_quota_policy WHERE source = p_source;
    INSERT INTO meta.api_quota_usage (source, quota_date) VALUES (p_source, v_date)
    ON CONFLICT DO NOTHING;
    UPDATE meta.api_quota_usage SET used = used + p_n
    WHERE source = p_source AND quota_date = v_date AND used + p_n <= floor(v_limit * p_share)
    RETURNING true INTO v_ok;
    RETURN COALESCE(v_ok, false);
END $$;

-- ===== meta: 품질 =====
CREATE TABLE meta.dq_rule (
    rule_id     text PRIMARY KEY,
    target      text NOT NULL,
    severity    text NOT NULL CHECK (severity IN ('warn', 'quarantine', 'block')),
    description text NOT NULL,
    params      jsonb NOT NULL DEFAULT '{}',
    enabled     boolean NOT NULL DEFAULT true
);

CREATE TABLE meta.dq_exception (
    rule_id     text NOT NULL REFERENCES meta.dq_rule (rule_id),
    entity_key  text NOT NULL,
    valid_from  date NOT NULL,
    valid_to    date NOT NULL DEFAULT 'infinity',
    reason      text NOT NULL,
    approved_by text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (rule_id, entity_key, valid_from),
    CHECK (valid_from < valid_to)
);

CREATE TABLE meta.quarantine_row (
    quarantine_id   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rule_id         text NOT NULL REFERENCES meta.dq_rule (rule_id),
    target_table    text NOT NULL,
    entity_key      text NOT NULL,
    row_data        jsonb NOT NULL,
    src_response_id bigint,
    status          text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'released', 'dropped')),
    created_at      timestamptz NOT NULL DEFAULT now(),
    resolved_at     timestamptz,
    resolution_note text,
    CHECK ((status = 'open') = (resolved_at IS NULL)),
    UNIQUE (rule_id, target_table, entity_key)
);

-- ===== meta: 빌드와 서빙 =====
CREATE TABLE meta.build (
    build_id     text PRIMARY KEY,
    data_cutoff  date NOT NULL,
    git_sha      text NOT NULL,
    status       text NOT NULL DEFAULT 'building'
                 CHECK (status IN ('building', 'validated', 'published', 'failed')),
    manifest     jsonb,
    created_at   timestamptz NOT NULL DEFAULT now(),
    published_at timestamptz
);

CREATE TABLE meta.dq_result (
    dq_id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rule_id       text NOT NULL REFERENCES meta.dq_rule (rule_id),
    build_id      text REFERENCES meta.build (build_id),
    target_date   date,
    passed        boolean NOT NULL,
    checked_count bigint NOT NULL DEFAULT 0,
    fail_count    bigint NOT NULL DEFAULT 0,
    sample        jsonb,
    checked_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX dq_result_build_idx ON meta.dq_result (build_id, rule_id);

CREATE TABLE meta.serving_pointer (
    channel    text PRIMARY KEY CHECK (channel IN ('research', 'live')),
    build_id   text NOT NULL REFERENCES meta.build (build_id),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- block 규칙 실패가 있거나 검증 전이면 발행하지 않는다. 포인터 교체는 원자적이다.
CREATE FUNCTION meta.fn_publish_build(p_build_id text, p_channel text)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    v_failed integer;
    v_status text;
BEGIN
    SELECT status INTO STRICT v_status FROM meta.build WHERE build_id = p_build_id FOR UPDATE;
    IF v_status NOT IN ('validated', 'published') THEN
        RAISE EXCEPTION 'build % is %, not validated', p_build_id, v_status;
    END IF;
    SELECT count(*) INTO v_failed
    FROM meta.dq_result d JOIN meta.dq_rule r USING (rule_id)
    WHERE d.build_id = p_build_id AND r.severity = 'block' AND NOT d.passed;
    IF v_failed > 0 THEN
        RAISE EXCEPTION 'build % has % failed block checks', p_build_id, v_failed;
    END IF;
    UPDATE meta.build SET status = 'published', published_at = now() WHERE build_id = p_build_id;
    INSERT INTO meta.serving_pointer (channel, build_id) VALUES (p_channel, p_build_id)
    ON CONFLICT (channel) DO UPDATE SET build_id = EXCLUDED.build_id, updated_at = now();
END $$;

-- ===== raw: 내용 기준 불변 저장 + 관측 로그 =====
CREATE TABLE raw.api_response (
    response_id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source         text NOT NULL CHECK (source IN ('krx', 'dart', 'ecos', 'datago', 'manual')),
    endpoint       text NOT NULL,
    request_key    text NOT NULL,
    request_params jsonb NOT NULL,
    http_status    smallint,
    body_code      text,
    payload        jsonb,
    blob_path      text,
    content_sha256 char(64) NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source, endpoint, request_key, content_sha256),
    CHECK ((payload IS NOT NULL) <> (blob_path IS NOT NULL)),
    -- 인증키가 저장되면 적재 자체를 실패시킨다
    CHECK (NOT (request_params ?| ARRAY['crtfc_key', 'AUTH_KEY', 'auth_key', 'serviceKey', 'apikey']))
);

CREATE TABLE raw.fetch_event (
    fetch_id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    response_id bigint NOT NULL REFERENCES raw.api_response (response_id),
    run_id      bigint REFERENCES meta.ingest_run (run_id),
    fetched_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX fetch_event_response_idx ON raw.fetch_event (response_id, fetched_at DESC);

CREATE FUNCTION raw.fn_forbid_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'raw is append-only (%)', TG_TABLE_NAME;
END $$;
CREATE TRIGGER api_response_immutable BEFORE UPDATE OR DELETE ON raw.api_response
    FOR EACH ROW EXECUTE FUNCTION raw.fn_forbid_mutation();
CREATE TRIGGER api_response_no_truncate BEFORE TRUNCATE ON raw.api_response
    FOR EACH STATEMENT EXECUTE FUNCTION raw.fn_forbid_mutation();
CREATE TRIGGER fetch_event_immutable BEFORE UPDATE OR DELETE ON raw.fetch_event
    FOR EACH ROW EXECUTE FUNCTION raw.fn_forbid_mutation();
CREATE TRIGGER fetch_event_no_truncate BEFORE TRUNCATE ON raw.fetch_event
    FOR EACH STATEMENT EXECUTE FUNCTION raw.fn_forbid_mutation();

-- 응답 1건 기록. 내용이 같으면 raw 행은 그대로 두고 fetch_event만 추가한다.
CREATE FUNCTION raw.fn_record_fetch(
    p_source text, p_endpoint text, p_request_key text, p_request_params jsonb,
    p_payload jsonb, p_blob_path text, p_content_sha256 text,
    p_http_status integer, p_body_code text, p_run_id bigint
) RETURNS TABLE (response_id bigint, is_new boolean)
LANGUAGE plpgsql AS $$
DECLARE
    v_id  bigint;
    v_new boolean := false;
BEGIN
    INSERT INTO raw.api_response AS r (source, endpoint, request_key, request_params,
        http_status, body_code, payload, blob_path, content_sha256)
    VALUES (p_source, p_endpoint, p_request_key, p_request_params,
        p_http_status, p_body_code, p_payload, p_blob_path, p_content_sha256)
    ON CONFLICT (source, endpoint, request_key, content_sha256) DO NOTHING
    RETURNING r.response_id INTO v_id;
    IF FOUND THEN
        v_new := true;
    ELSE
        SELECT r.response_id INTO STRICT v_id FROM raw.api_response r
        WHERE r.source = p_source AND r.endpoint = p_endpoint
          AND r.request_key = p_request_key AND r.content_sha256 = p_content_sha256;
    END IF;
    INSERT INTO raw.fetch_event (response_id, run_id) VALUES (v_id, p_run_id);
    RETURN QUERY SELECT v_id, v_new;
END $$;

-- 요청별 현재 내용. A→B→A 재출현에서도 A를 돌려준다.
CREATE VIEW raw.v_latest_response AS
SELECT DISTINCT ON (r.source, r.endpoint, r.request_key)
       r.response_id, r.source, r.endpoint, r.request_key, r.payload, r.blob_path,
       f.fetched_at AS last_fetched_at
FROM raw.api_response r
JOIN raw.fetch_event f ON f.response_id = r.response_id
ORDER BY r.source, r.endpoint, r.request_key, f.fetched_at DESC, f.fetch_id DESC;

-- 소스 정정 감지: 직전 관측과 내용이 달라진 시점
CREATE VIEW raw.v_revision AS
SELECT source, endpoint, request_key, fetched_at, response_id, prev_response_id
FROM (
    SELECT r.source, r.endpoint, r.request_key, f.fetched_at, f.response_id,
           lag(f.response_id) OVER (PARTITION BY r.source, r.endpoint, r.request_key
                                    ORDER BY f.fetched_at, f.fetch_id) AS prev_response_id
    FROM raw.fetch_event f JOIN raw.api_response r ON r.response_id = f.response_id
) s
WHERE prev_response_id IS NOT NULL AND prev_response_id <> response_id;

-- ===== staging =====
CREATE TABLE staging.krx_daily_price (
    trade_date       date NOT NULL,
    market           text NOT NULL CHECK (market IN ('KOSPI', 'KOSDAQ', 'KONEX')),
    isu_cd           text NOT NULL,
    isu_nm           text,
    sector_nm        text,
    close_price      numeric(18, 2),
    change_from_prev numeric(18, 2),
    fluc_rate        numeric(10, 4),
    open_price       numeric(18, 2),
    high_price       numeric(18, 2),
    low_price        numeric(18, 2),
    volume           bigint,
    trade_value      numeric(24, 0),
    market_cap       numeric(24, 0),
    listed_shares    bigint,
    base_price       numeric(18, 2) GENERATED ALWAYS AS (close_price - change_from_prev) STORED,
    src_response_id  bigint NOT NULL REFERENCES raw.api_response (response_id),
    PRIMARY KEY (trade_date, market, isu_cd)
);

CREATE TABLE staging.krx_index_daily (
    trade_date      date NOT NULL,
    idx_clss        text NOT NULL,
    idx_nm          text NOT NULL,
    close_idx       numeric(18, 4),
    src_response_id bigint NOT NULL REFERENCES raw.api_response (response_id),
    PRIMARY KEY (trade_date, idx_clss, idx_nm)
);

CREATE TABLE staging.krx_security_snapshot (
    snapshot_date   date NOT NULL,
    market          text NOT NULL,
    isu_std_cd      text NOT NULL,
    isu_srt_cd      text NOT NULL,
    isu_nm          text,
    isu_abbrv       text,
    list_date       date,
    secu_group      text,
    sector_nm       text,
    stock_kind      text,
    par_value       numeric(18, 2),
    listed_shares   bigint,
    src_response_id bigint NOT NULL REFERENCES raw.api_response (response_id),
    PRIMARY KEY (snapshot_date, market, isu_std_cd)
);

CREATE TABLE staging.krx_delisting (
    isu_srt_cd        text NOT NULL,
    delist_date       date NOT NULL,
    isu_std_cd        text,
    isu_nm            text,
    market            text,
    reason_text       text,
    arrangement_start date,
    arrangement_end   date,
    successor_srt_cd  text,
    src_response_id   bigint NOT NULL REFERENCES raw.api_response (response_id),
    PRIMARY KEY (isu_srt_cd, delist_date)
);

CREATE TABLE staging.dart_corp (
    corp_code     char(8) PRIMARY KEY,
    corp_name     text NOT NULL,
    stock_code    text,
    jurir_no      text,
    modify_date   date,
    first_seen_at timestamptz NOT NULL,
    last_seen_at  timestamptz NOT NULL
);

CREATE TABLE staging.dart_filing (
    rcept_no        char(14) PRIMARY KEY,
    corp_code       char(8) NOT NULL,
    corp_cls        text,
    stock_code      text,
    report_nm       text NOT NULL,
    rcept_dt        date NOT NULL,
    flr_nm          text,
    rm              text,
    bsns_year       integer,
    reprt_code      text CHECK (reprt_code IN ('11011', '11012', '11013', '11014')),
    is_correction   boolean NOT NULL DEFAULT false,
    withdrawn_from  date,
    first_seen_at   timestamptz NOT NULL,
    src_response_id bigint NOT NULL REFERENCES raw.api_response (response_id)
);
CREATE INDEX dart_filing_period_idx
    ON staging.dart_filing (corp_code, bsns_year, reprt_code, rcept_dt);

CREATE TABLE staging.dart_fin_line (
    src_response_id   bigint NOT NULL REFERENCES raw.api_response (response_id),
    line_no           integer NOT NULL,
    source_kind       text NOT NULL CHECK (source_kind IN ('multi', 'single_all', 'xbrl')),
    rcept_no          char(14),
    corp_code         char(8) NOT NULL,
    bsns_year         integer NOT NULL,
    reprt_code        text NOT NULL,
    fs_div            text NOT NULL,
    sj_div            text,
    account_id        text,
    account_nm        text NOT NULL,
    thstrm_amount     numeric(30, 0),
    thstrm_add_amount numeric(30, 0),
    frmtrm_amount     numeric(30, 0),
    frmtrm_add_amount numeric(30, 0),
    thstrm_dt         text,
    currency          text,
    PRIMARY KEY (src_response_id, line_no)
);

-- 값이 바뀔 때만 행을 추가한다. first_seen_at이 거시 vintage의 관측 시각이다.
CREATE TABLE staging.ecos_observation (
    stat_code       text NOT NULL,
    cycle           text NOT NULL,
    item_key        text NOT NULL,
    obs_time        text NOT NULL,
    first_seen_at   timestamptz NOT NULL,
    value           numeric,
    unit_name       text,
    src_response_id bigint NOT NULL REFERENCES raw.api_response (response_id),
    PRIMARY KEY (stat_code, cycle, item_key, obs_time, first_seen_at)
);

-- ===== mart: 달력 =====
CREATE TABLE mart.dim_trading_calendar (
    cal_date date PRIMARY KEY,
    is_open  boolean NOT NULL,
    status   text NOT NULL CHECK (status IN ('confirmed', 'provisional')),
    basis    text NOT NULL CHECK (basis IN ('index_presence', 'weekend', 'holiday_list', 'manual'))
);

CREATE FUNCTION mart.fn_next_open(p_date date) RETURNS date
LANGUAGE sql STABLE AS $$
    SELECT min(cal_date) FROM mart.dim_trading_calendar WHERE is_open AND cal_date > p_date
$$;

CREATE FUNCTION mart.fn_prev_open(p_date date) RETURNS date
LANGUAGE sql STABLE AS $$
    SELECT max(cal_date) FROM mart.dim_trading_calendar WHERE is_open AND cal_date < p_date
$$;

-- 배당락일: 기준일 이하 마지막 개장일의 직전 개장일 (T+2 결제 기준).
-- 기준일이 휴장일이어도 결제 가능한 마지막 날을 기준으로 계산한다.
CREATE FUNCTION mart.fn_ex_date(p_record_date date) RETURNS date
LANGUAGE sql STABLE AS $$
    SELECT mart.fn_prev_open(max(cal_date))
    FROM mart.dim_trading_calendar WHERE is_open AND cal_date <= p_record_date
$$;

-- ===== mart: 종목 마스터 =====
CREATE TABLE mart.dim_security (
    security_id        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    first_isu_srt_cd   text NOT NULL,
    list_date          date,
    first_traded_date  date NOT NULL,
    last_traded_date   date,
    delist_date        date,
    delist_date_source text CHECK (delist_date_source IN ('official', 'last_seen')),
    UNIQUE (first_isu_srt_cd, first_traded_date),
    CHECK ((delist_date IS NULL) = (delist_date_source IS NULL)),
    -- 마지막 거래일에는 아직 상장 상태다. last_seen 근사도 다음 개장일로 둔다.
    CHECK (delist_date IS NULL OR last_traded_date IS NULL OR delist_date > last_traded_date)
);

CREATE TABLE mart.dim_security_history (
    security_id   bigint NOT NULL REFERENCES mart.dim_security (security_id),
    valid_from    date NOT NULL,
    valid_to      date NOT NULL DEFAULT 'infinity',
    isu_srt_cd    text NOT NULL CHECK (isu_srt_cd ~ '^[0-9A-Z]{6}$'),
    isu_std_cd    text,
    isu_nm        text,
    market        text NOT NULL CHECK (market IN ('KOSPI', 'KOSDAQ', 'KONEX')),
    security_type text NOT NULL CHECK (security_type IN
        ('common', 'preferred', 'reit', 'spac', 'foreign', 'dr', 'infra', 'other')),
    sector_nm     text,
    PRIMARY KEY (security_id, valid_from),
    CHECK (valid_from < valid_to),
    EXCLUDE USING gist (isu_srt_cd WITH =, daterange(valid_from, valid_to, '[)') WITH &&),
    EXCLUDE USING gist (security_id WITH =, daterange(valid_from, valid_to, '[)') WITH &&)
);

CREATE TABLE mart.map_security_corp (
    security_id bigint NOT NULL REFERENCES mart.dim_security (security_id),
    corp_code   char(8) NOT NULL,
    valid_from  date NOT NULL,
    valid_to    date NOT NULL DEFAULT 'infinity',
    method      text NOT NULL CHECK (method IN ('stock_code', 'filing_stock_code', 'jurir_no', 'manual')),
    PRIMARY KEY (security_id, corp_code, valid_from),
    CHECK (valid_from < valid_to),
    EXCLUDE USING gist (security_id WITH =, daterange(valid_from, valid_to, '[)') WITH &&)
);

CREATE TABLE mart.dim_account_std (
    account_std text PRIMARY KEY,
    statement   text NOT NULL CHECK (statement IN ('BS', 'IS', 'CF')),
    value_basis text NOT NULL CHECK (value_basis IN ('instant', 'ytd')),
    description text NOT NULL
);

CREATE TABLE mart.map_account_std (
    map_id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_std  text NOT NULL REFERENCES mart.dim_account_std (account_std),
    industry     text NOT NULL DEFAULT 'general'
                 CHECK (industry IN ('general', 'bank', 'insurance', 'securities')),
    account_id   text,
    account_nm   text,
    priority     integer NOT NULL DEFAULT 100,
    CHECK (account_id IS NOT NULL OR account_nm IS NOT NULL)
);

CREATE TABLE mart.dim_macro_series (
    series_id     text PRIMARY KEY,
    stat_code     text NOT NULL,
    cycle         text NOT NULL CHECK (cycle IN ('D', 'SM', 'M', 'Q', 'S', 'A')),
    item_key      text NOT NULL,
    series_name   text NOT NULL,
    unit_name     text,
    lag_rule_days integer NOT NULL CHECK (lag_rule_days >= 1),
    UNIQUE (stat_code, cycle, item_key)
);

CREATE TABLE mart.fact_macro_release (
    series_id      text NOT NULL REFERENCES mart.dim_macro_series (series_id),
    obs_period_end date NOT NULL,
    release_date   date NOT NULL,
    release_kind   text NOT NULL DEFAULT 'first' CHECK (release_kind IN ('first', 'revised')),
    source         text NOT NULL,
    PRIMARY KEY (series_id, obs_period_end, release_kind),
    CHECK (release_date > obs_period_end)
);

-- ===== mart: 시세 =====
-- cum_factor: 상장 이후 ex_date <= trade_date인 이벤트의 price_factor 누적곱.
-- 새 이벤트가 생겨도 과거 행은 바뀌지 않는다. adj(t | as_of) = close(t) * G(as_of) / G(t)
CREATE TABLE mart.fact_daily_price (
    security_id   bigint NOT NULL REFERENCES mart.dim_security (security_id),
    trade_date    date NOT NULL,
    market        text NOT NULL,
    open_price    numeric(18, 2),
    high_price    numeric(18, 2),
    low_price     numeric(18, 2),
    close_price   numeric(18, 2) NOT NULL,
    base_price    numeric(18, 2),
    volume        bigint NOT NULL CHECK (volume >= 0),
    trade_value   numeric(24, 0),
    market_cap    numeric(24, 0),
    listed_shares bigint,
    ret_price     double precision,
    cum_factor    double precision NOT NULL DEFAULT 1 CHECK (cum_factor > 0),
    is_traded     boolean GENERATED ALWAYS AS (volume > 0) STORED,
    PRIMARY KEY (security_id, trade_date),
    CHECK (close_price > 0),
    CHECK (open_price IS NULL OR open_price > 0),
    CHECK (high_price IS NULL OR high_price > 0),
    CHECK (low_price IS NULL OR low_price > 0),
    CHECK (high_price IS NULL OR low_price IS NULL OR high_price >= low_price),
    CHECK (high_price IS NULL OR open_price IS NULL OR open_price <= high_price),
    CHECK (low_price IS NULL OR open_price IS NULL OR open_price >= low_price),
    -- 거래가 있는 날만 종가가 고저 범위 안에 있어야 한다. 거래 없는 날 OHLC는 NULL이다.
    CHECK (volume = 0 OR (open_price IS NOT NULL AND high_price IS NOT NULL
                          AND low_price IS NOT NULL
                          AND close_price BETWEEN low_price AND high_price)),
    CHECK (volume > 0 OR (open_price IS NULL AND high_price IS NULL AND low_price IS NULL))
) PARTITION BY RANGE (trade_date);

CREATE FUNCTION mart.fn_add_price_partition(p_year integer)
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS mart.fact_daily_price_%s PARTITION OF mart.fact_daily_price
         FOR VALUES FROM (%L) TO (%L)',
        p_year, make_date(p_year, 1, 1), make_date(p_year + 1, 1, 1));
END $$;

DO $$
BEGIN
    FOR y IN 2010..2027 LOOP
        PERFORM mart.fn_add_price_partition(y);
    END LOOP;
END $$;
-- 기본 파티션에 행이 들어오면 DQ가 실패한다 (R-OPS-01)
CREATE TABLE mart.fact_daily_price_default PARTITION OF mart.fact_daily_price DEFAULT;

CREATE INDEX fact_daily_price_date_idx ON mart.fact_daily_price (trade_date, security_id);

-- 경제적 사건 1건 = 1행. 탐지 경로는 evidence에 둔다 (이중 적용 방지).
CREATE TABLE mart.fact_corp_action (
    action_id        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    security_id      bigint NOT NULL REFERENCES mart.dim_security (security_id),
    ex_date          date NOT NULL,
    action_type      text NOT NULL CHECK (action_type IN
        ('split', 'reverse_split', 'bonus_issue', 'stock_dividend', 'rights',
         'capital_reduction', 'merger', 'spinoff', 'other')),
    price_factor     double precision NOT NULL CHECK (price_factor > 0),
    status           text NOT NULL DEFAULT 'candidate'
                     CHECK (status IN ('candidate', 'confirmed', 'rejected')),
    known_from       date NOT NULL,
    cum_factor_after double precision NOT NULL DEFAULT 1 CHECK (cum_factor_after > 0),
    note             text,
    UNIQUE (security_id, ex_date),
    CHECK (known_from <= ex_date)
);

CREATE TABLE mart.fact_corp_action_evidence (
    action_id       bigint NOT NULL REFERENCES mart.fact_corp_action (action_id) ON DELETE CASCADE,
    detected_by     text NOT NULL CHECK (detected_by IN ('base_price_gap', 'dart', 'manual')),
    evidence_key    text NOT NULL,
    observed_factor double precision,
    detected_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (action_id, detected_by, evidence_key)
);

-- 이벤트 변경 시 한 종목만 재계산한다. rejected는 누적곱에서 제외한다.
CREATE FUNCTION mart.fn_refresh_cum_factor(p_security_id bigint)
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    UPDATE mart.fact_corp_action a SET cum_factor_after = COALESCE(s.cf, 1)
    FROM (
        SELECT action_id,
               exp(sum(ln(price_factor)) FILTER (WHERE status <> 'rejected')
                   OVER (ORDER BY ex_date)) AS cf
        FROM mart.fact_corp_action WHERE security_id = p_security_id
    ) s
    WHERE a.action_id = s.action_id AND a.cum_factor_after IS DISTINCT FROM COALESCE(s.cf, 1);

    UPDATE mart.fact_daily_price p SET cum_factor = s.cf
    FROM (
        SELECT d.security_id, d.trade_date,
               COALESCE((SELECT a.cum_factor_after FROM mart.fact_corp_action a
                         WHERE a.security_id = d.security_id AND a.ex_date <= d.trade_date
                         ORDER BY a.ex_date DESC LIMIT 1), 1) AS cf
        FROM mart.fact_daily_price d WHERE d.security_id = p_security_id
    ) s
    WHERE p.security_id = s.security_id AND p.trade_date = s.trade_date
      AND p.cum_factor IS DISTINCT FROM s.cf;

    UPDATE mart.fact_daily_price p SET ret_price = s.r
    FROM (
        SELECT security_id, trade_date,
               close_price::double precision /
               NULLIF(lag(close_price) OVER w * (cum_factor / lag(cum_factor) OVER w), 0) - 1 AS r
        FROM mart.fact_daily_price WHERE security_id = p_security_id
        WINDOW w AS (ORDER BY trade_date)
    ) s
    WHERE p.security_id = s.security_id AND p.trade_date = s.trade_date
      AND p.ret_price IS DISTINCT FROM s.r;
END $$;

-- 현금배당은 기준가에 반영되지 않으므로 price_factor와 분리한다.
-- known_from이 ex_date보다 늦을 수 있다 (배당액 확정 전 배당락). 신호에는 known_from을 쓴다.
CREATE TABLE mart.fact_dividend (
    security_id    bigint NOT NULL REFERENCES mart.dim_security (security_id),
    ex_date        date NOT NULL,
    record_date    date,
    cash_per_share numeric(18, 4) NOT NULL CHECK (cash_per_share > 0),
    known_from     date NOT NULL,
    src_rcept_no   char(14),
    PRIMARY KEY (security_id, ex_date, known_from)
);

CREATE TABLE mart.fact_delisting (
    security_id           bigint PRIMARY KEY REFERENCES mart.dim_security (security_id),
    delist_date           date NOT NULL,
    last_trade_date       date NOT NULL,
    reason_group          text NOT NULL CHECK (reason_group IN
        ('distress', 'merger_cash', 'merger_stock', 'voluntary', 'other', 'unknown')),
    reason_text           text,
    arrangement_start     date,
    arrangement_end       date,
    successor_security_id bigint REFERENCES mart.dim_security (security_id),
    exit_value            numeric(18, 4),
    delist_return         double precision NOT NULL,
    return_basis          text NOT NULL CHECK (return_basis IN
        ('last_close', 'consideration', 'assumed')),
    CHECK (delist_date > last_trade_date),
    CHECK (delist_return >= -1)
);

-- ===== mart: 재무 =====
CREATE TABLE mart.fact_financial_pit (
    fin_id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    corp_code       char(8) NOT NULL,
    bsns_year       integer NOT NULL,
    reprt_code      text NOT NULL CHECK (reprt_code IN ('11011', '11012', '11013', '11014')),
    fs_div          text NOT NULL CHECK (fs_div IN ('CFS', 'OFS')),
    account_std     text NOT NULL,
    value_basis     text NOT NULL CHECK (value_basis IN ('instant', 'ytd')),
    fiscal_months   smallint CHECK (fiscal_months IN (3, 6, 9, 12)),
    amount          numeric(30, 0),
    period_end      date NOT NULL,
    rcept_no        char(14) NOT NULL,
    rcept_dt        date NOT NULL,
    available_from  date NOT NULL,
    withdrawn_from  date,
    version_seq     integer NOT NULL CHECK (version_seq >= 1),
    pit_quality     text NOT NULL CHECK (pit_quality IN
        ('observed', 'xbrl_original', 'single_version', 'backfill_latest')),
    src_response_id bigint REFERENCES raw.api_response (response_id),
    UNIQUE (corp_code, bsns_year, reprt_code, fs_div, account_std, rcept_no),
    CHECK (available_from > rcept_dt),
    CHECK (rcept_dt >= period_end),
    CHECK ((value_basis = 'ytd') = (fiscal_months IS NOT NULL)),
    CHECK (withdrawn_from IS NULL OR withdrawn_from >= rcept_dt)
);
CREATE INDEX fact_financial_pit_asof_idx
    ON mart.fact_financial_pit (corp_code, bsns_year, reprt_code, fs_div, version_seq DESC);
CREATE INDEX fact_financial_pit_avail_idx ON mart.fact_financial_pit (available_from);

-- 공시 다음 개장일 이전 사용을 DB에서 막는다
CREATE FUNCTION mart.fn_check_available_from() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE v_next date := mart.fn_next_open(NEW.rcept_dt);
BEGIN
    IF v_next IS NULL THEN
        RAISE EXCEPTION 'calendar has no open date after %', NEW.rcept_dt;
    END IF;
    IF NEW.available_from < v_next THEN
        RAISE EXCEPTION 'available_from % is before next open % (rcept_dt %)',
            NEW.available_from, v_next, NEW.rcept_dt;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER fact_financial_pit_available_chk
    BEFORE INSERT OR UPDATE OF available_from, rcept_dt ON mart.fact_financial_pit
    FOR EACH ROW EXECUTE FUNCTION mart.fn_check_available_from();

-- ===== mart: 거시 =====
CREATE TABLE mart.fact_macro_pit (
    series_id       text NOT NULL REFERENCES mart.dim_macro_series (series_id),
    obs_period_end  date NOT NULL,
    available_from  date NOT NULL,
    value           numeric,
    available_basis text NOT NULL CHECK (available_basis IN
        ('observed_snapshot', 'release_calendar', 'lag_rule')),
    is_rebased      boolean NOT NULL DEFAULT false,
    PRIMARY KEY (series_id, obs_period_end, available_from),
    CHECK (available_from > obs_period_end)
);

-- ===== mart: 팩터 =====
-- PostgreSQL에는 최근 2개 빌드만 둔다. 전체 이력은 Parquet 스냅샷이 원본이다.
CREATE TABLE mart.factor_daily (
    build_id    text NOT NULL REFERENCES meta.build (build_id),
    factor_name text NOT NULL,
    trade_date  date NOT NULL,
    security_id bigint NOT NULL REFERENCES mart.dim_security (security_id),
    value       double precision,
    PRIMARY KEY (build_id, factor_name, trade_date, security_id)
);
CREATE INDEX factor_daily_date_idx ON mart.factor_daily (build_id, trade_date, factor_name);

-- ===== mart: as-of 함수 =====
-- 재무: p_as_of 시점에 유효한 최신 공시의 행 전체 (공시 단위 스냅샷).
-- 정정에서 사라진 계정이 이전 버전 값으로 남지 않는다. 철회된 공시는 철회일부터 제외한다.
CREATE FUNCTION mart.fn_financial_asof(p_as_of date)
RETURNS SETOF mart.fact_financial_pit
LANGUAGE sql STABLE AS $$
    WITH latest AS (
        SELECT DISTINCT ON (corp_code, bsns_year, reprt_code, fs_div)
               corp_code, bsns_year, reprt_code, fs_div, rcept_no
        FROM mart.fact_financial_pit
        WHERE available_from <= p_as_of
          AND (withdrawn_from IS NULL OR withdrawn_from > p_as_of)
        ORDER BY corp_code, bsns_year, reprt_code, fs_div, version_seq DESC
    )
    SELECT f.*
    FROM mart.fact_financial_pit f
    JOIN latest l USING (corp_code, bsns_year, reprt_code, fs_div, rcept_no)
$$;

-- 시점 재무값: 계정별 최신 결산. 연결이 있으면 연결, 없으면 별도.
CREATE FUNCTION mart.fn_financial_latest(p_as_of date)
RETURNS TABLE (corp_code char(8), fs_div text, account_std text, period_end date,
               amount numeric, pit_quality text)
LANGUAGE sql STABLE AS $$
    SELECT DISTINCT ON (f.corp_code, f.account_std)
           f.corp_code, f.fs_div, f.account_std, f.period_end, f.amount, f.pit_quality
    FROM mart.fn_financial_asof(p_as_of) f
    WHERE f.value_basis = 'instant' AND f.amount IS NOT NULL
    ORDER BY f.corp_code, f.account_std, f.period_end DESC,
             CASE f.fs_div WHEN 'CFS' THEN 0 ELSE 1 END
$$;

-- TTM = 당기 누적 + 직전 연간 - 전년 동기 누적. 세 값 모두 p_as_of 시점에 알려진 값이고,
-- 하나라도 없으면 부분합을 만들지 않고 제외한다. 결산월은 period_end로 계산한다.
CREATE FUNCTION mart.fn_financial_ttm(p_as_of date)
RETURNS TABLE (corp_code char(8), fs_div text, account_std text, period_end date,
               ttm_amount numeric, min_quality text)
LANGUAGE sql STABLE AS $$
    WITH f AS (
        SELECT * FROM mart.fn_financial_asof(p_as_of)
        WHERE value_basis = 'ytd' AND amount IS NOT NULL
    ),
    cur AS (
        SELECT DISTINCT ON (corp_code, fs_div, account_std) *
        FROM f ORDER BY corp_code, fs_div, account_std, period_end DESC
    ),
    calc AS (
        SELECT c.corp_code, c.fs_div, c.account_std, c.period_end,
               CASE WHEN c.fiscal_months = 12 THEN c.amount
                    ELSE c.amount + fy.amount - py.amount END AS ttm_amount,
               CASE WHEN 'backfill_latest' IN (c.pit_quality, fy.pit_quality, py.pit_quality)
                    THEN 'backfill_latest' ELSE 'clean' END AS min_quality
        FROM cur c
        LEFT JOIN f fy ON fy.corp_code = c.corp_code AND fy.fs_div = c.fs_div
              AND fy.account_std = c.account_std AND fy.fiscal_months = 12
              AND fy.period_end = (date_trunc('month', c.period_end)
                  - make_interval(months => c.fiscal_months)
                  + interval '1 month - 1 day')::date
        LEFT JOIN f py ON py.corp_code = c.corp_code AND py.fs_div = c.fs_div
              AND py.account_std = c.account_std AND py.fiscal_months = c.fiscal_months
              AND py.period_end = (date_trunc('month', c.period_end)
                  - interval '12 months' + interval '1 month - 1 day')::date
    )
    SELECT DISTINCT ON (corp_code, account_std)
           corp_code, fs_div, account_std, period_end, ttm_amount, min_quality
    FROM calc
    WHERE ttm_amount IS NOT NULL
    ORDER BY corp_code, account_std, period_end DESC,
             CASE fs_div WHEN 'CFS' THEN 0 ELSE 1 END
$$;

-- 수정주가: p_as_of 이후 이벤트는 반영하지 않는다. 행마다 이벤트를 다시 곱하지 않는다.
CREATE FUNCTION mart.fn_adj_price(p_as_of date)
RETURNS TABLE (security_id bigint, trade_date date, close_price numeric,
               adj_close double precision, adj_volume double precision)
LANGUAGE sql STABLE AS $$
    WITH a AS (
        SELECT DISTINCT ON (c.security_id) c.security_id, c.cum_factor_after
        FROM mart.fact_corp_action c
        WHERE c.ex_date <= p_as_of
        ORDER BY c.security_id, c.ex_date DESC
    )
    SELECT p.security_id, p.trade_date, p.close_price,
           p.close_price::double precision * COALESCE(a.cum_factor_after, 1) / p.cum_factor,
           p.volume::double precision * p.cum_factor / COALESCE(a.cum_factor_after, 1)
    FROM mart.fact_daily_price p
    LEFT JOIN a ON a.security_id = p.security_id
    WHERE p.trade_date <= p_as_of
$$;

-- 유니버스: p_as_of 시점 상장 종목 (이후 폐지 종목 포함). 기본은 보통주만.
CREATE FUNCTION mart.fn_universe(p_as_of date, p_types text[] DEFAULT ARRAY['common'])
RETURNS TABLE (security_id bigint, isu_srt_cd text, market text, security_type text,
               sector_nm text)
LANGUAGE sql STABLE AS $$
    SELECT s.security_id, h.isu_srt_cd, h.market, h.security_type, h.sector_nm
    FROM mart.dim_security s
    JOIN mart.dim_security_history h
      ON h.security_id = s.security_id
     AND p_as_of >= h.valid_from AND p_as_of < h.valid_to
    WHERE COALESCE(s.list_date, s.first_traded_date) <= p_as_of
      AND (s.delist_date IS NULL OR s.delist_date > p_as_of)
      AND h.security_type = ANY (p_types)
$$;

-- 거시: p_as_of 시점에 알려진 관측값
CREATE FUNCTION mart.fn_macro_asof(p_as_of date)
RETURNS SETOF mart.fact_macro_pit
LANGUAGE sql STABLE AS $$
    SELECT DISTINCT ON (series_id, obs_period_end) *
    FROM mart.fact_macro_pit
    WHERE available_from <= p_as_of
    ORDER BY series_id, obs_period_end, available_from DESC
$$;

-- 일별 수익률. 총수익은 P&L용이다. 배당을 신호로 쓸 때는 fact_dividend.known_from을 따른다.
CREATE VIEW mart.v_daily_return AS
SELECT p.security_id, p.trade_date, p.ret_price,
       p.ret_price + COALESCE(d.cash_per_share::double precision
                              / NULLIF(p.base_price, 0)::double precision, 0) AS ret_total,
       l.delist_return
FROM mart.fact_daily_price p
LEFT JOIN LATERAL (
    SELECT x.cash_per_share FROM mart.fact_dividend x
    WHERE x.security_id = p.security_id AND x.ex_date = p.trade_date
    ORDER BY x.known_from DESC LIMIT 1
) d ON true
LEFT JOIN mart.fact_delisting l
       ON l.security_id = p.security_id AND l.last_trade_date = p.trade_date;

CREATE VIEW meta.v_pipeline_health AS
SELECT source, endpoint,
       max(finished_at) FILTER (WHERE status IN ('success', 'empty')) AS last_ok_at,
       count(*) FILTER (WHERE status = 'failed'
                        AND started_at > now() - interval '24 hours') AS failed_24h,
       count(*) FILTER (WHERE status = 'running'
                        AND heartbeat_at < now() - interval '15 minutes') AS stale_running
FROM meta.ingest_run
GROUP BY source, endpoint;

-- ===== 권한 =====
GRANT USAGE ON SCHEMA meta, raw TO quant_ingest;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA meta TO quant_ingest;
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA raw TO quant_ingest;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA meta, raw TO quant_ingest;

GRANT USAGE ON SCHEMA meta, raw, staging, mart TO quant_transform;
GRANT SELECT ON ALL TABLES IN SCHEMA raw TO quant_transform;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA meta TO quant_transform;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA staging, mart TO quant_transform;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA meta, staging, mart TO quant_transform;

GRANT USAGE ON SCHEMA mart, meta TO quant_research;
GRANT SELECT ON ALL TABLES IN SCHEMA mart, meta TO quant_research;
```

## 사용 패턴

```sql
-- 응답 기록: 같은 내용이면 raw 행은 그대로, fetch_event만 추가
SELECT * FROM raw.fn_record_fetch(%s, %s, %s, %s, %s, NULL, %s, %s, %s, %s);

-- 호출 직전 예산 예약. false면 호출하지 않고 quota로 종료
SELECT meta.fn_reserve_quota('krx');

-- 2024-04-01 시점 TTM 순이익 (연결 우선, 없으면 별도)
SELECT * FROM mart.fn_financial_ttm('2024-04-01') WHERE account_std = 'net_income';

-- 2024-04-01 시점 보통주 유니버스와 수정 종가
SELECT u.security_id, u.isu_srt_cd, p.adj_close
FROM mart.fn_universe('2024-04-01') u
JOIN mart.fn_adj_price('2024-04-01') p USING (security_id)
WHERE p.trade_date = '2024-04-01';
```

`request_key` 예시: `basDd=20261030`. 키는 요청을 결정하는 파라미터만 정렬해 만들고 인증키를 넣지 않습니다.

## 재무 금액 적재 규칙

G2-6 결과로 확정합니다. 아래는 공개 자료 기준 초안입니다.

| 재무제표 | 보고서 | 저장 값 | `value_basis` | `fiscal_months` |
|---|---|---|---|---|
| 재무상태표 | 전체 | `thstrm_amount` | `instant` | NULL |
| 손익 | 1분기 | `thstrm_add_amount`, 없으면 `thstrm_amount` | `ytd` | 3 |
| 손익 | 반기, 3분기 | `thstrm_add_amount` | `ytd` | 6, 9 |
| 손익 | 사업보고서 | `thstrm_amount` | `ytd` | 12 |
| 현금흐름 | 전체 | 누적 값 필드 (G2-6) | `ytd` | 3, 6, 9, 12 |

`period_end`는 응답의 기간 필드나 보고서명에서 구합니다. `bsns_year`와 `12-31`을 조합하지 않습니다.

## 범위 밖

- 계정과목 전체 표준화: v0.4.0에서 PER, PBR, ROE에 필요한 계정부터 시작
- 일중 데이터 테이블: 소스 결정 후 Parquet으로 추가
- 로그인 역할과 비밀번호 배포: 역할은 DDL에 있고 로그인 분리는 v1.0.0 마무리
