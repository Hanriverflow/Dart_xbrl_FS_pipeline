# DART XBRL 프로젝트 업그레이드 로드맵

## 0) 목표 요약
이번 업그레이드의 핵심 목표는 아래 3가지입니다.

1. 여러 회사/여러 날짜를 한 번에 처리하는 배치 실행 기능
2. 주석 숫자 테이블을 구조적으로 파싱하는 엔진
3. LLM 요약 모듈로 "수익성 개선 포인트" 자동 메모 생성

---

## 1) 현재 상태와 갭

### 현재 상태
- CLI는 단일 회사 중심 분석(`dart-xbrl --corp-name ...`)에 최적화
- 손익계산서 중심의 계정 매칭은 가능하나, 주석은 키워드 기반 탐색 비중이 큼
- 결과물은 JSON/Markdown 생성 가능

### 갭
- 배치 오케스트레이션(여러 회사 x 여러 날짜 x 여러 보고서) 부재
- 주석 내 숫자 테이블(열/행/단위/주석 헤더) 구조 파싱 부재
- 분석 결과를 투자 메모 형태로 자동 요약하는 LLM 파이프라인 부재

---

## 2) 아키텍처 업그레이드 방향

### A. Batch Runner 레이어 추가
- 입력 스펙 파일(`config/batch_jobs.yaml` 또는 CSV) 기반 다건 실행
- 실행 단위: `(corp_name or corp_code, date, report_type)`
- 실패한 작업만 재시도 가능한 job 상태관리(`queued/running/succeeded/failed`)
- 결과 폴더를 job 단위로 분리 저장

### B. Notes Table Parser 모듈 신설
- XBRL 주석에서 테이블 노드 탐지
- 열/행 헤더, 단위(원/백만원/%), 기준기간(당기/전기) 추출
- 숫자 정규화(콤마, 괄호 음수, 단위 환산) 후 구조화 JSON 저장

### C. LLM Insight Generator 모듈 신설
- 입력: 손익/재무상태/현금흐름 + 주석 구조 데이터
- 출력: "수익성 개선 포인트" 중심 1~2페이지 메모
- 환각 방지를 위해 근거 숫자와 출처(테이블/계정) 강제 첨부

---

## 3) 단계별 실행 계획 (8주)

## Phase 1 (1~2주): 배치 실행 기반 구축

### 목표
단일 실행 중심 CLI를 배치 실행 가능한 형태로 확장

### 작업 항목
- `src/dart_xbrl_pipeline/cli.py`: `batch` 서브 커맨드 추가
- `src/dart_xbrl_pipeline/batch_runner.py` 신설
- `src/dart_xbrl_pipeline/models.py`: Job 모델 확장
- `config/batch_jobs.example.yaml` 추가

### 산출물
- `uv run dart-xbrl batch --job-file config/batch_jobs.yaml` 실행 가능
- 배치 실행 리포트(`reports/batch/<job_id>/summary.json`) 생성

### 검증 기준
- 10건 배치에서 성공/실패 건수 집계 정확
- 3개 이상 회사 x 2개 이상 기준일 x 2개 보고서 유형 혼합 job file 완주
- 결과물이 `(company, date, report_type)` 기준으로 분리 저장되고 재실행 시 성공 건은 스킵, 실패 건만 재처리

---

## Phase 2 (3~5주): 주석 숫자 테이블 구조 파싱

### 목표
키워드 탐색을 넘어 "숫자 테이블" 자체를 분석 가능한 데이터셋으로 전환

### 작업 항목
- `src/dart_xbrl_pipeline/note_table_parser.py` 신설
- 파싱 결과 스키마 정의(`table_id`, `title`, `columns`, `rows`, `unit`, `period_context`)
- 단위/부호/기간 정규화 유틸 추가
- 기존 `xbrl_parser.py`와 연동하여 주석 구조 데이터 병합

### 산출물
- `reports/<rcept_no>_note_tables.json` 생성
- 핵심 테이블(차입금, 이자비용, CAPEX, 환율 민감도 등) 샘플 추출 결과

### 검증 기준
- 샘플 20개 테이블에서 숫자 파싱 정확도 95% 이상
- 단위 변환 오류(예: 백만원/원 혼용) 0건

---

## Phase 3 (6~7주): LLM 수익성 개선 포인트 메모 자동화

### 착수 조건 (Phase 2 완료 기준)
- `note_tables.json` 스키마 고정 (호환성 변경 금지)
- 대표 테이블 유형별(차입금, 이자비용, CAPEX, 환율 민감도) 정확도 기준 충족

### 목표
정량 결과를 사람이 바로 읽을 수 있는 투자 메모로 자동 변환

### 작업 항목
- `src/dart_xbrl_pipeline/insight_writer.py` 신설
- 프롬프트 템플릿(근거 우선, 숫자 인용 필수, 과장 금지) 설계
- 입력 컨텍스트 압축기(핵심 지표 + 주석 테이블 하이라이트) 추가
- 메모 출력 포맷(`*_profitability_memo.md`) 정의

### 산출물
- 회사/기간별 자동 메모 파일 생성
- 메모 내 모든 주장에 숫자 근거 링크 또는 계정명 표기

### 검증 기준
- 5개 회사 샘플에서 사람이 수동 작성한 요약 대비 품질 리뷰 통과
- 근거 없는 문장(unsupported claim) 0건

---

## Phase 4 (8주): 통합 배포/운영 안정화

### 목표
배치 + 테이블 파싱 + LLM 메모 파이프라인을 일괄 운영 가능한 상태로 고정

### 작업 항목
- 통합 커맨드 제공: `dart-xbrl batch --with-note-tables --with-llm-memo`
- 장애 대응 로깅/리포트 정리(회사별 실패 원인, 재시도 가이드)
- 실행 비용/시간 모니터링(LLM 호출량, 토큰 사용량, 건당 처리시간)

### 산출물
- 운영 가이드 문서(배치 스케줄, 장애 조치, 비용 관리)
- 주간 실행 리포트 템플릿

### 검증 기준
- 50건 배치 기준 파이프라인 완주율 95% 이상
- 동일 입력 재실행 시 결과 재현성 확보

---

## 4) 파일 단위 변경 계획

### 신규 파일
- `src/dart_xbrl_pipeline/batch_runner.py`
- `src/dart_xbrl_pipeline/note_table_parser.py`
- `src/dart_xbrl_pipeline/insight_writer.py`
- `config/batch_jobs.example.yaml`
- `tests/test_batch_runner.py`
- `tests/test_note_table_parser.py`
- `tests/test_insight_writer.py`

### 수정 파일
- `src/dart_xbrl_pipeline/cli.py` (batch 옵션/통합 실행 플래그)
- `src/dart_xbrl_pipeline/analyzer.py` (구조 파서/LLM 모듈 연동)
- `src/dart_xbrl_pipeline/models.py` (job/table/memo 모델 추가)
- `README.md` (배치/LLM 사용법 추가)

---

## 5) 리스크와 대응

### 리스크 1: 회사별 XBRL 주석 포맷 편차
- 대응: 규칙 기반 + fallback 파서 이중화, 파싱 실패 테이블 원문 별도 저장

### 리스크 2: LLM 요약의 과장/환각
- 대응: 근거 없는 문장 차단 룰, 숫자/계정 근거 mandatory 체크

### 리스크 3: 배치 실행 중 API 제한/네트워크 오류
- 대응: 요청 제한(throttle), 지수 백오프 재시도, 실패 큐 분리

### 리스크 4: 비용 증가
- 대응: LLM 호출 전 요약 후보 축소, 캐시 적용, 회사당 토큰 상한 관리

---

## 6) 완료 정의 (Definition of Done)

각 목표별 증거 기반 완료 체크리스트:

- **목표 (a) 다건 배치**: 3개 이상 회사 x 2개 이상 기준일 x 2개 이상 보고서 유형을 1개 job file로 실행하고, 성공 건은 스킵/실패 건만 재처리 가능
- **목표 (b) 주석 테이블 파싱**: 대표 테이블 유형 4종(차입금, 이자비용, CAPEX, 환율 민감도)에서 숫자 파싱 정확도 95% 이상, 단위 변환 오류 0건
- **목표 (c) LLM 자동 메모**: 모든 주장 문장이 `table_id` 또는 계정 reference로 역추적 가능, unsupported claim 0건
- **공통**: 통합 커맨드(`--with-note-tables --with-llm-memo`)로 50건 배치 완주율 95% 이상

---

## 7) 즉시 실행할 첫 작업(이번 주)

1. 배치 입력 스키마(`batch_jobs.yaml`) 확정
2. `batch_runner.py` 골격 + 상태 저장 포맷 구현
3. 주석 테이블 파서 PoC(차입금/이자비용 테이블 3개 우선)
4. LLM 메모 템플릿 v1 작성은 Phase 2 후반/Phase 3 초기로 이동 (파싱 스키마 고정 후 설계)
