# HL D&I Handoff

작성일: 2026-03-21

## 목적

다음 세션에서 바로 이어서 작업할 수 있도록, HL D&I (`014790`)를 기준으로 확인한 사실과 남은 작업을 정리한다.

## 현재 상태

- 실제 OpenDART 표기:
  - 회사명: `HL D&I`
  - corp_code: `00161116`
  - stock_code: `014790`
- 2025 사업보고서 접수 정보:
  - 접수번호: `20260317000824`
  - 접수일: `2026-03-17`
  - 보고서명: `사업보고서 (2025.12)`
- `2025-12-31` 입력으로도 annual filing을 찾도록 fallback 검색이 추가됨
  - `analysis.diagnostics.search_window == "fiscal_fallback"`
- raw DART XBRL에는 literal HTML `<table>`가 없고, `presentation linkbase + label linkbase + dimensioned facts` 조합으로 note table이 표현됨
- 이에 따라 `NoteTableParser`에 presentation-driven fallback이 추가됨

## HL D&I 실데이터 결과

성공적으로 생성되는 산출물:

- `reports/20260317000824_analysis.json`
- `reports/20260317000824_analysis.md`
- `reports/20260317000824_note_tables.json`
- `reports/20260317000824_run_manifest.json`

현재 note table 결과:

- `차입금` 테이블 1개
- `환율 민감도` 테이블 1개

확인 포인트:

- `reports/20260317000824_note_tables.json`의 `table_count == 2`
- `reports/20260317000824_run_manifest.json`의 `warnings == []`

## Codex 분석 요약

Codex는 현재 parsed data만 기준으로 다음을 지적했다.

- 영업이익은 흑자이지만, 세전이익/순이익으로 잘 남지 않아 아래 라인 누수가 큼
- 다기관 차입 구조가 이미 분명함
- 아직 완전한 credit memo를 신뢰하긴 이르며, 특히 아래가 부족함
  - 전기 수치 일관성 검증
  - 현금흐름
  - 재무상태표
  - 총차입금/단기-장기 비중/평균금리 구조

## 현재 구현된 개선 사항

- `--with-llm-memo` 사용 시
  - `profitability_memo`
  - `credit_memo`
  를 함께 생성하도록 확장
- LLM provider 선택 가능:
  - `--llm-provider auto`
  - `--llm-provider openai`
  - `--llm-provider anthropic`
- 필요 시 모델 지정 가능:
  - `--llm-model <model-name>`

## 아직 남은 blocker

가장 큰 blocker는 실제 LLM provider 키가 `.env`에 없다는 점이다.

현재 확인 결과:

- `OPENDART_API_KEY`: 있음
- `OPENAI_API_KEY`: 없음
- `ANTHROPIC_API_KEY`: 없음

즉, HL D&I 기준 `--with-llm-memo`의 실제 provider 호출은 아직 end-to-end 검증되지 않았다.

## 다음에 바로 실행할 명령

### 1. note table만 검증

```bash
uv run dart-xbrl analyze \
  --corp-name 'HL D&I' \
  --corp-code 00161116 \
  --date 2025-12-31 \
  --report-type annual \
  --with-note-tables
```

### 2. OpenAI로 memo 검증

```bash
uv run dart-xbrl analyze \
  --corp-name 'HL D&I' \
  --corp-code 00161116 \
  --date 2025-12-31 \
  --report-type annual \
  --with-note-tables \
  --with-llm-memo \
  --llm-provider openai
```

### 3. Anthropic으로 memo 검증

```bash
uv run dart-xbrl analyze \
  --corp-name 'HL D&I' \
  --corp-code 00161116 \
  --date 2025-12-31 \
  --report-type annual \
  --with-note-tables \
  --with-llm-memo \
  --llm-provider anthropic
```

## 다음 우선순위

1. `.env`에 `OPENAI_API_KEY` 또는 `ANTHROPIC_API_KEY` 추가
2. HL D&I로 `profitability_memo` / `credit_memo` 실제 생성 확인
3. memo 품질 검토
   - 차입금 만기 압박
   - 이자비용 부담
   - FX 민감도
   - 영업이익 대비 순이익 누수
4. 필요하면 parsed table label 정리
   - 현재 일부 row/column 라벨은 영어 taxonomy 이름이 섞여 있음
5. 그 다음 샘플 issuer 1개 더 추가해 재현성 확인

## 검증 상태

- `uv run pytest` -> `72 passed`
- `uv run python -m compileall src tests` -> success

## 관련 문서

- `docs/designs/credit-wedge.md`
- `README.md`
- `QUICK_start.md`
