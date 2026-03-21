# DART XBRL v2 갭 클로징 개선계획

작성일: 2026-03-21

## 사용한 스킬
- `$plan` direct mode

## 요구사항 요약
- README/PRD/roadmap가 약속한 v2 경험을 실제 실행 경로와 산출물에 맞춘다.
- 이미 강한 배치 실행기와 evidence-first LLM 안전장치는 보존한다.
- 신규 아이디어는 받아들이되, v2 통합 완성보다 앞서지 않게 단계화한다.

## 현재 상태 확인
- `batch --with-note-tables --with-llm-memo` 플래그는 현재 환경변수만 세팅하고 실제 분석 파이프라인 옵션으로 전달되지 않는다. 근거: `src/dart_xbrl_pipeline/cli.py:164-183`
- 실제 분석 결과는 손익계산서 metric, note hit, summary만 반환한다. note table / memo / token usage 필드는 없다. 근거: `src/dart_xbrl_pipeline/analyzer.py:41-76`, `src/dart_xbrl_pipeline/models.py:39-49`
- 리포터도 `_analysis.json`과 `_analysis.md`만 저장한다. 근거: `src/dart_xbrl_pipeline/reporter.py:43-49`
- 반면 주석 테이블 파서와 LLM writer는 각각 독립 모듈과 테스트를 이미 갖고 있다. 근거: `src/dart_xbrl_pipeline/note_table_parser.py`, `src/dart_xbrl_pipeline/insight_writer.py`, `tests/unit/test_note_table_parser.py:20-52`, `tests/unit/test_insight_writer.py:62-245`
- 배치 레이어는 상태 저장, 재시도, resume 테스트까지 확보돼 있어 재사용 가치가 높다. 근거: `src/dart_xbrl_pipeline/batch_runner.py`, `tests/unit/test_batch_runner.py:50-243`

## 받아들인 제안

### 바로 반영
- P0: 통합 완성. 가장 큰 실제 갭이다.
- P0: 패키징/릴리즈 정리. README와 설치 경험이 어긋난다.
- P1: filing 선택 로직, corp code 캐시, note hit 스코프 축소.

### 부분 반영
- P1: fact 중심 재설계는 방향이 맞다. 다만 지금은 전면 교체보다 "provenance가 있는 중간 결과 계층"부터 도입한다.

### 후순위로 보류
- P2: `liquidity_memo`, `refinancing_risk_memo` 같은 issuer analysis stack 확장은 v2 통합 완료 뒤 별도 페이즈로 분리한다.

## 의사결정
- v2의 1차 목표는 "좋은 모듈이 있는 레포"에서 "문서대로 동작하는 파이프라인"으로 올리는 것이다.
- 따라서 이번 라운드는 orchestration, artifact contract, packaging, parser hardening에 집중한다.
- 데이터 모델 대수술은 단계적으로 넣는다. 기존 `AnalysisOutput`을 바로 비대하게 키우기보다, 새 결과 객체를 도입해 호환성을 관리한다.

## 수용 기준
1. `uv run dart-xbrl batch --job-file ... --with-note-tables --with-llm-memo` 실행 시 각 job 출력 폴더에 `_analysis.json/.md`, `_note_tables.json`, `_profitability_memo.md`, `_run_manifest.json`이 생성된다.
2. note table / memo 생성 여부는 환경변수가 아니라 typed execution config로 제어된다.
3. manifest에는 생성된 artifact 경로, warnings, token usage, schema version이 기록된다.
4. filing 선택은 deterministic score 기반으로 동작하며, `q1`과 `q3`를 동일 키워드 first-hit로 고르지 않는다.
5. corp code master는 캐시를 재사용하고, note hit 수집은 `.xsd` 노이즈를 기본 경로에서 제외한다.
6. 배치 재시도/resume 동작은 유지된다.
7. 최소 1개의 통합 테스트가 실제로 세 산출물 생성 여부를 검증한다.
8. 패키지 의존성은 runtime / dev / optional llm으로 분리되고, README 버전 표기와 package version이 일치한다.

## 구현 계획

### Phase 1. 통합 오케스트레이션 완성
대상 파일:
- `src/dart_xbrl_pipeline/cli.py:157-195`
- `src/dart_xbrl_pipeline/analyzer.py:41-76`
- `src/dart_xbrl_pipeline/models.py:39-49`
- `src/dart_xbrl_pipeline/reporter.py:43-49`
- `src/dart_xbrl_pipeline/batch_runner.py:69-91`
- `src/dart_xbrl_pipeline/config_models.py:45-105`

작업:
- `PipelineExecutionOptions`와 `PipelineArtifacts` 같은 typed 결과/옵션 모델을 추가한다.
- `cli.py`는 `with_note_tables`, `with_llm_memo`를 환경변수 대신 옵션 모델로 전달한다.
- `analyzer.py`는 기본 분석 후 `NoteTableParser`와 `InsightWriter`를 조건부 orchestration 한다.
- `reporter.py`는 analysis / note_tables / memo / manifest를 한 번에 저장하도록 확장한다.
- `batch_runner.py`는 저장된 artifact path를 job state에 기록하되, 기존 resume/retry semantics는 유지한다.

완료 기준:
- 단일 실행과 배치 실행 모두 동일 artifact contract를 사용한다.
- README에 적힌 두 플래그가 실제 산출물 생성으로 이어진다.

### Phase 2. 중간 데이터 계층 보강
대상 파일:
- `src/dart_xbrl_pipeline/models.py`
- `src/dart_xbrl_pipeline/xbrl_parser.py:88-178`
- `src/dart_xbrl_pipeline/note_models.py:176-203`
- `src/dart_xbrl_pipeline/insight_models.py:83-88`

작업:
- 전면 fact store 재작성 대신, provenance가 있는 중간 레이어를 추가한다.
- 최소 필드: `concept/tag`, `label/account_name`, `context_id`, `unit_ref/unit`, `raw_value`, `normalized_value`, `source_file`, `source_kind`, `confidence`.
- 기존 `income_statement_metrics`와 `note_hits`는 이 레이어에서 파생되는 호환 view로 유지한다.
- LLM 입력은 이 중간 레이어와 note table 결과에서 조립해 traceability를 강화한다.

완료 기준:
- 새 레이어를 추가해도 기존 summary/markdown 출력과 테스트가 깨지지 않는다.
- 이후 peer comparison/time-series 확장 시 재사용 가능한 provenance가 남는다.

### Phase 3. 파서와 공시 선택 로직 강화
대상 파일:
- `src/dart_xbrl_pipeline/analyzer.py:12-21`
- `src/dart_xbrl_pipeline/xbrl_parser.py:36-39`
- `src/dart_xbrl_pipeline/xbrl_parser.py:143-178`
- `src/dart_xbrl_pipeline/opendart.py:35-46`
- `config/default.yaml:1-17`

작업:
- `pick_filing()`을 score 기반 선택으로 교체한다.
- 추천 score 축: corp name exact, corp code exact, report name exact/pattern match, report_type code match, exact date, amendment penalty.
- `q1`/`q3`는 동일 `"분기보고서"` 키워드만 쓰지 말고 `reprt_code`, date proximity, 보고서명 패턴을 함께 반영한다.
- corp code zip은 일 단위 캐시 또는 파일 존재/mtime 기반 캐시를 둔다.
- `extract_note_hits()` 기본 경로에서 `.xsd`를 제외하고, 가능하면 note/table 관련 노드만 우선 순회한다.

완료 기준:
- filing 선택은 동일 입력에 대해 항상 같은 결과를 반환한다.
- 샘플 taxonomy 파일이 많은 케이스에서도 note hit 노이즈가 줄어든다.

### Phase 4. 패키징/운영 정리
대상 파일:
- `pyproject.toml:1-22`
- `README.md`
- CI 설정 파일 신규 추가

작업:
- `pytest`를 dev dependency로 이동한다.
- `openai`와 `anthropic`은 optional extra `llm`으로 분리한다.
- README의 `v2.0` 표기와 패키지 버전을 일치시킨다. 실제 릴리즈 준비가 안 됐다면 README를 "v2 roadmap/in progress"로 낮추는 선택지도 포함한다.
- `git clone <repository-url>` placeholder, 설치/실행 예시, 테스트 명령을 점검한다.
- CI 최소 세트: `ruff`, `pytest`, `coverage`, `pyright` 또는 `mypy`.

완료 기준:
- fresh install 시 runtime dependency만으로 기본 CLI가 동작한다.
- LLM 기능은 extras 설치 없이는 명확한 에러를, 설치 후에는 정상 동작 경로를 제공한다.

### Phase 5. v2 이후 확장 백로그
후보:
- `liquidity_memo`
- `refinancing_risk_memo`
- `bond_issuance_brief`
- `covenant_watch_memo`

조건:
- Phase 1~4 완료 후 착수
- 공통 evidence contract와 manifest schema를 재사용

## 리스크와 대응
- 통합 시 기존 batch 테스트가 깨질 수 있다.
  대응: Phase 1에서 reporter contract를 먼저 고정하고, 기존 test double을 새 contract에 맞춰 정리한다.
- 데이터 모델을 너무 크게 바꾸면 v2 closure가 늦어진다.
  대응: fact layer는 partial adoption으로 제한하고, 기존 output compatibility를 유지한다.
- LLM 연동이 테스트를 flaky하게 만들 수 있다.
  대응: 현재처럼 injected fake client 기반 테스트를 유지하고, acceptance test는 mock provider로 고정한다.
- README와 실제 버전 중 무엇을 맞출지 제품 판단이 필요하다.
  대응: 코드 기준으로 낮추는 안과 릴리즈 기준으로 올리는 안을 같이 준비하고, 릴리즈 시점에 확정한다.

## 검증 계획
- 단위 테스트:
  - `pick_filing` score/ranking
  - corp code cache hit/miss
  - `extract_note_hits` scope narrowing
  - reporter manifest 저장
- 통합 테스트:
  - batch + `with_note_tables` + `with_llm_memo`에서 4종 artifact 생성 검증
  - resume/retry 시 artifact path 보존 검증
- 문서/패키징 검증:
  - clean env에서 `uv sync`
  - 기본 CLI help
  - llm extras 설치 전/후 동작 확인

## 추천 실행 순서
1. Phase 1
2. Phase 3 중 filing/cache/note hit hardening
3. Phase 4
4. Phase 2
5. Phase 5

## 이번 계획의 핵심 판단
- 받아들인 리뷰의 핵심은 맞다. 특히 "문서상 약속과 실제 orchestration 사이의 갭"은 최우선으로 해결할 가치가 있다.
- 다만 fact-centric redesign와 credit memo 확장은 지금 즉시 전면 도입하기보다, v2 artifact contract를 먼저 고정한 뒤 올라가는 편이 리스크가 낮다.
