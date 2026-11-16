# 3. 데이터 소스 정리표

`docs/03-data-sources.md`. 기준일: 2026-11-03

> **KRX, DART, ECOS 공식 문서는 여전히 확정되지 않았습니다.** 이번 검토 환경에서도 세 곳의 공식 페이지를 읽을 수 없었고 실제 API 호출은 0건입니다. 공개 클라이언트 코드와 문서로 교차 확인했습니다. 구현 전에 [게이트](06-issues.md)에서 확정합니다.

| 표시 | 의미 |
|---|---|
| 🔵 | 공식 출처 또는 직접 실행으로 확인 |
| 🟢 | 독립된 공개 자료 2곳 이상 일치 |
| 🟡 | 공개 자료 1곳에서만 확인 |
| 🔴 | 미확인. 실제 호출로 확인 필요 |

## 이전 문서 대비 정정

| 항목 | 이전 | 정정 | 상태 |
|---|---|---|---|
| DART 일 한도 | 10,000회 | 약 20,000회, 키별로 다를 수 있음 | 🟢 |
| DART 분당 제한 | 없음 | 분당 1,000회 이상 요청 시 제한 가능 | 🟡 |
| ECOS 호출 제한 | 약 1,000회/일 | 일 한도 근거 없음. 300회/3분 제한 보고 | 🟡 |
| ECOS 오류 전달 | 없음 | HTTP 200 본문의 `RESULT.CODE` | 🟢 |
| ECOS 환율 표 | `731Y004` | 일별은 `731Y001` | 🟡 |
| ECOS GDP 표 | `200Y001` | 계절조정 `200Y107/108`, 원계열 `200Y109/110` 후보 | 🟡 |
| KRX 오류 전달 | 없음 | 본문 `respCode`, 쿼터 초과 429, 과도한 호출 시 IP 차단 | 🟡 |
| 상장폐지 출처 | 미확정 | KRX 정보데이터시스템 [20037] 상장폐지종목 현황 | 🟢 |
| 전체 재무 호출 수 | 132,000회 | `fs_div` 필수라 연결·별도 모두 받으면 2배 | 🟢 |

## 소스 요약

| 소스 | 수집 항목 | 갱신 | 인증 | 호출 제한 |
|---|---|---|---|---|
| **KRX Open API** | 코스피·코스닥 일별매매, 종목기본, 지수 | 전 영업일 데이터가 다음 영업일 08:00 갱신 🟢 | `AUTH_KEY` 헤더, API별 이용 승인 🟢 | 키당 10,000회/일, 자정 초기화 🟢 |
| **OpenDART** | 고유번호, 공시검색, 재무, XBRL, 배당, 주요사항 | 공시 발생 시 | `crtfc_key` 쿼리 파라미터 🟢 | 약 20,000회/일 🟢, 분당 1,000회 🟡 |
| **ECOS** | 기준금리, 시장금리, 환율, CPI, GDP, 경기지표 | 통계표별 상이 | URL 경로에 인증키 🟢 | 300회/3분 🟡, 일 한도 🔴 |
| **KRX 상장폐지 목록** | 폐지일, 사유, 정리매매 기간 | 수동 갱신 | 정보데이터시스템 로그인 🟡 | 수동 내려받기만 사용 |
| **금융위 공공데이터** (보조) | KRX상장종목정보, 주식시세정보 | 다음 영업일 13시 이후 🔵 | 공공데이터포털 인증키 | 페이지에 미표기 🔵 |

## KRX 상세

| 구분 | 내용 | 상태 |
|---|---|---|
| Base URL | `data-dbg.krx.co.kr/svc/apis`. 공개 구현마다 http, https가 다름 | 🟡 |
| 일별매매 | `sto/stk_bydd_trd`, `sto/ksq_bydd_trd`, `sto/knx_bydd_trd` | 🟢 |
| 종목기본 | `sto/stk_isu_base_info`, `sto/ksq_isu_base_info`, `sto/knx_isu_base_info` | 🟢 |
| 지수 | `idx/kospi_dd_trd`, `idx/kosdaq_dd_trd` | 🟢 |
| 요청 | `basDd=YYYYMMDD`, 날짜 단위 전 종목 응답 | 🟢 |
| 응답 블록 | `OutBlock_1` 배열. 오류는 `respCode`, `respMsg` | 🟡 |
| 일별매매 필드 | `BAS_DD, ISU_CD, ISU_NM, MKT_NM, SECT_TP_NM, TDD_CLSPRC, CMPPREVDD_PRC, FLUC_RT, TDD_OPNPRC, TDD_HGPRC, TDD_LWPRC, ACC_TRDVOL, ACC_TRDVAL, MKTCAP, LIST_SHRS` | 🟡 |
| 종목기본 필드 | `ISU_CD, ISU_SRT_CD, ISU_NM, ISU_ABBRV, ISU_ENG_NM, LIST_DD, MKT_TP_NM, SECUGRP_NM, SECT_TP_NM, KIND_STKCERT_TP_NM, PARVAL, LIST_SHRS` | 🟡 |
| 제공 기간 | 일별매매 2010-01-04부터, 코넥스 2013-07-01부터 | 🟡 |
| 미제공 | 수정주가, 상장폐지일, 거래정지·관리종목, 투자자별 거래, PER/PBR, 일중 데이터 | 🟡 |
| 이용 조건 | 비상업적 목적, 출처 "한국거래소 통계정보" 표기, 원천 데이터 제3자 재배포 금지 | 🟡 |

## DART 상세

| 구분 | 내용 | 상태 |
|---|---|---|
| Base URL | `https://opendart.fss.or.kr/api/` | 🟢 |
| 고유번호 | `corpCode.xml` (zip) | 🟢 |
| 회사 개황 | `company.json`. `jurir_no`로 법인등록번호 대조 | 🟡 |
| 공시검색 | `list.json`. `bgn_de, end_de, corp_code, last_reprt_at, pblntf_ty, corp_cls, page_no, page_count` | 🟢 |
| 검색 제약 | `corp_code` 미지정 시 3개월 이내, `page_count` 최대 100 | 🟢 |
| 주요계정(다중) | `fnlttMultiAcnt.json`. 호출당 100개사, 초과 시 `021` | 🟢 |
| 전체 재무제표 | `fnlttSinglAcntAll.json`. `corp_code, bsns_year, reprt_code, fs_div` 필수 | 🟢 |
| XBRL 원본 | `fnlttXbrl.xml`. `rcept_no, reprt_code` (zip) | 🟢 |
| 보고서 코드 | 11013(1분기), 11012(반기), 11014(3분기), 11011(사업) | 🟢 |
| 금액 필드 | 손익 `thstrm_amount`는 당분기, `thstrm_add_amount`는 누적. 쉼표 포함 문자열, `-`는 값 없음 | 🟡 |
| 제공 기간 | 재무 API는 2015 사업연도부터 | 🟢 |
| 메시지 코드 | `000, 010, 011, 012, 013, 020, 021, 100, 101, 800, 900, 901` | 🟢 |

`rcept_dt`만으로는 접수 시각을 알 수 없습니다. `rcept_no` 앞 8자리는 날짜처럼 보이지만 공시일 판정에는 `list.json`의 `rcept_dt`만 씁니다.

## ECOS 상세

| 구분 | 내용 | 상태 |
|---|---|---|
| 조회 URL | `/api/StatisticSearch/{key}/json/kr/{start}/{end}/{stat_code}/{cycle}/{from}/{to}/{item...}` | 🟢 |
| 탐색 서비스 | `StatisticTableList`, `StatisticItemList` | 🟢 |
| 주기 코드 | `A, S, Q, M, SM, D` | 🟡 |
| 데이터 없음 | `INFO-200` | 🟢 |
| 오류 코드 | `INFO-100`, `ERROR-100/101/200/300/301/400/500/600/601/602` | 🟡 |
| 조회 시간 | 서버 60초 초과 시 `ERROR-400`. 클라이언트 타임아웃은 75초 이상 | 🟡 |
| 페이지 | 키 있는 요청 `1/100000` 사용 사례 있음. `list_total_count`로 검증 | 🟡 |
| 기준금리 | `722Y001`, 항목 `0101000`, 일별 | 🟢 |
| 후보 통계표 | CPI `901Y009`, 환율 `731Y001`, 경기종합지수 `901Y067`, 산업생산 `901Y033` | 🟡 |
| 시장금리 | 후보 `817Y002`. `StatisticTableList`로 확인 | 🔴 |

ECOS의 시점은 공표일이 아니라 대상 기간입니다. 공표일은 통계청 계열 지표의 경우 [공표 일정](https://mods.go.kr/lcofNewsPln.es?mid=a60303000000)으로 관리합니다. 예: 2026년 3월 소비자물가는 2026-04-02 공표 🔵.

## 프로젝트 지침과 충돌하는 점

| 지침 | 조사 결과 | 조치 |
|---|---|---|
| KRX에서 상장폐지 종목 정보 수집 | Open API에 상장폐지일 없음 🟡 | 정보데이터시스템 파일을 `manual` 소스로 적재 |
| 수정주가 반영 | KRX는 원주가만 제공 🟡 | 기준가로 직접 계산, 현금배당은 DART |
| 재무 공시일 기준 저장 | 정정 전 원본 확보 미확정 | `pit_quality` 4등급 운영 |
| 생존편향 없는 데이터 | 시세 2010년~, 재무 2015년~ | 팩터 백테스트 시작은 **2016년 이후** 권장 |
| 공개 포트폴리오 | 원천 재배포 금지 🟡 | 코드만 공개 |
| 취업 후 사용 | 비상업 조건 🟡 | 회사 업무에 쓰려면 유료 라이선스 검토 |

## 퀀트 관점 주의사항

- **거래량 범위**: 2025년 이후 KRX 거래량은 시장 전체가 아닙니다. 보도 기준 2026년 넥스트레이드 비중은 10%대이고 거래량 상한은 15%입니다.
- **우선주 시가총액**: PER, PBR은 회사 단위 값이므로 보통주 시가총액만 쓰면 왜곡됩니다. 같은 `corp_code`의 전 종목 시총을 합산합니다.
- **연결 필터**: `fs_div='CFS'`만 쓰면 별도 재무만 있는 회사가 사라집니다. 연결 우선, 없으면 별도입니다.
- **누적과 분기**: DART 손익은 누적과 3개월 값이 다르고, 4분기는 별도 보고서가 없습니다. TTM은 `누적 + 직전 연간 - 전년 동기 누적`입니다.
- **결산월**: 12월 결산을 가정하지 않습니다. `period_end`로 계산합니다.
- **은행·보험·증권**: 계정 체계가 달라 `map_account_std.industry`로 분리합니다.
- **코드 형식**: 단축코드는 문자열입니다. 앞자리 0과 영문 포함 코드를 숫자로 읽지 않습니다.
- **pandas 3**: Airflow 3.3.2 constraints의 pandas는 3.0.5입니다. 코드 컬럼은 `dtype`을 명시합니다.
- **pykrx**: KRX 로그인 정보가 필요하고 공식 데이터와 차이가 있을 수 있다고 명시되어 있습니다. 파이프라인 소스로 쓰지 않습니다.

## 초기 백필 호출량

거래일은 2010-01-04부터 2026-10-30까지 약 4,170일, 평일은 4,390일입니다. 예산은 KRX 8,000회/일, DART 16,000회/일 기준입니다.

| 작업 | 계산 | 호출 수 | 소요 |
|---|---|---|---|
| KOSPI 지수 (달력 구축) | 평일 4,390 | 4,390 | |
| 코스피·코스닥 일별매매 | 4,170 × 2 | 8,340 | |
| 종목기본 월 1회 | 202개월 × 2 | 404 | |
| **KRX 합계** | | **13,134** | **2일** |
| DART 주요계정(다중) | 30배치 × 46보고서 | 1,380 | 1일 |
| DART 공시검색 정기공시 | 48개 3개월 창, 공시 수 ÷ 100 | 약 1,500 추정 | 1일 |
| DART 전체 재무 (연결만) | 3,000 × 46 | 138,000 | 9일 |
| DART 전체 재무 (연결+별도) | 3,000 × 46 × 2 | 276,000 | 18일 |

회사 수 3,000은 폐지 포함 추정치입니다. 실제 호출은 `dart_filing`에 공시가 있는 조합으로 줄입니다.

**추천**: `fnlttMultiAcnt`로 전 종목을 먼저 채우고, 전체 재무제표는 분석 유니버스에만 수집합니다. 정정이 있는 기간만 XBRL로 원본을 받습니다.

| 대안 | 장점 | 단점 |
|---|---|---|
| 다중 주요계정 | 호출 수 100분의 1 | 계정이 제한적 |
| 단일 전체 재무제표 | 계정 전체 | 전 종목 백필 2~3주 |
| 정정 기간 XBRL | 정정 전 원본 확보 | 파싱 비용 |

## 참고 자료

공식 페이지 (직접 확인 필요)

- [KRX Open API](https://openapi.krx.co.kr), [OpenDART 개발가이드](https://opendart.fss.or.kr/guide/main.do), [ECOS Open API](https://ecos.bok.or.kr/api/)

이번 검토에서 확인한 자료

- 공식: [Airflow docker-compose 3.3.2](https://raw.githubusercontent.com/apache/airflow/3.3.2/airflow-core/docs/howto/docker-compose/docker-compose.yaml), [Airflow constraints 3.3.2](https://raw.githubusercontent.com/apache/airflow/constraints-3.3.2/constraints-3.12.txt), [apache-airflow PyPI](https://pypi.org/project/apache-airflow/), [금융위 주식시세정보](https://www.data.go.kr/data/15094808/openapi.do), [금융위 KRX상장종목정보](https://www.data.go.kr/data/15094775/openapi.do), [통계 공표 일정](https://mods.go.kr/lcofNewsPln.es?mid=a60303000000)
- 공개 구현: [krx-openapi](https://pypi.org/project/krx-openapi/), [krx-rs](https://docs.rs/crate/krx-rs/latest/source/src/client.rs), [opendart-client](https://pypi.org/project/opendart-client/), [dart-fss](https://github.com/josw123/dart-fss), [k-dart](https://raw.githubusercontent.com/NomaDamas/k-skill/main/docs/features/k-dart.md), [ecos-reader](https://pypi.org/project/ecos-reader/), [cluefin ECOS PR](https://github.com/kgcrom/cluefin/pull/169), [pykrx](https://pypi.org/project/pykrx/)
- 2차 자료: [OpenDART 재무 API 해설](https://algolab.co.kr/blog/dart-opendart-financial-statement-api-lag-2026), [상장폐지와 생존편향](https://algolab.co.kr/blog/survivorship-bias-backtest-delisted-krx-2026)
- 제도 변화: [가격제한폭 30%](https://news.bizwatch.co.kr/article/market/2015/06/15/0018), [신규상장 가격제한폭](https://economist.co.kr/article/view/ecn202306200029), [배당절차 개선](https://www.etoday.co.kr/news/view/2235394), [공매도 재개](https://www.jjan.kr/articleAmp/20250331580001), [KRX 애프터마켓과 NXT 비중](https://www.sidae.com/article/2026091115143275147), [KRX 애프터마켓 첫 주](https://www.kbmaeil.com/article/20260920500338), [결제주기 단축 추진](https://www.etoday.co.kr/news/view/2545047)
