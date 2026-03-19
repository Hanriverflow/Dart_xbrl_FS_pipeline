# DART XBRL 분석 파이프라인 v2.0

> **⚡ MAJOR UPGRADE 완료**: 배치 처리, 주석 테이블 파싱, LLM 자동 메모 기능이 추가되었습니다!

OpenDART API에서 정기보고서 XBRL 원문을 내려받아 재무제표와 주석을 분석하는 Python CLI 프로젝트입니다. 이번 v2.0 업그레이드로 단일 분석을 넘어 **대규모 배치 처리**, **구조적 주석 테이블 추출**, **AI 기반 수익성 분석 메모**가 가능해졌습니다.

---

## 🎯 주요 기능 (What's New in v2.0)

### 1️⃣ 배치 실행 시스템 (Batch Runner)
- **여러 회사 × 여러 날짜 × 여러 보고서 유형**을 한 번에 처리
- 실패한 작업만 재시도하는 스마트 재실행 기능
- 병렬 실행으로 처리 시간 단축 (최대 4개 동시 실행)
- 작업 상태 지속성: 중단 후에도 재개 가능

```bash
# 12개 작업을 한 번에 실행
uv run dart-xbrl batch --job-file config/batch_jobs.yaml --max-workers 4

# 실패한 작업만 재시도
uv run dart-xbrl batch --job-file config/batch_jobs.yaml --retry-failed
```

### 2️⃣ 주석 숫자 테이블 구조 파싱
- XBRL 주석에서 **표 형태의 숫자 데이터**를 구조적으로 추출
- 차입금, 이자비용, CAPEX, 환율 민감도 등 핵심 테이블 자동 인식
- 단위 변환 자동 처리 (원/천원/백만원/억원)
- 정확도 95% 이상, 단위 변환 오류 0건 목표

```bash
# 주석 테이블 파싱 포함 실행
uv run dart-xbrl batch --job-file config/batch_jobs.yaml --with-note-tables
```

**출력 예시** (`reports/<접수번호>_note_tables.json`):
```json
{
  "tables": [
    {
      "table_id": "tbl_a3f2b8d9",
      "title": "차입금 현황",
      "table_type": "차입금",
      "unit": "백만원",
      "columns": ["구분", "당기", "전기"],
      "rows": [...]
    }
  ]
}
```

### 3️⃣ LLM 수익성 개선 포인트 메모
- AI가 재무 데이터를 분석하여 **"수익성 개선 포인트"** 자동 생성
- 모든 주장에 **수치 근거 필수 첨부** (table_id 또는 계정 reference)
- 과장/환각 방지를 위한 엄격한 검증 시스템
- 투자 의사결정용 1-2페이지 요약 메모 출력

```bash
# LLM 메모 생성 포함 실행
uv run dart-xbrl batch --job-file config/batch_jobs.yaml --with-llm-memo
```

**출력 예시** (`reports/<접수번호>_profitability_memo.md`):
```markdown
# 하나마이크론 수익성 개선 포인트 분석

## 핵심 개선 포인트
1. **차입금 이자부담 감소**: 이자비용 28.3% 감소 (table: tbl_a3f2b8d9)
   - 2024년 1,228.7억원 → 2025년 880.5억원
   - 원인: 단기차입금 상환 및 금리 인하 효과

## 근거 수치
- 영업활동현금흐름: +326.9% 증가 (table: tbl_c7d9e1f4)
- 부채비율: 221.0% → 209.2% 개선

## 리스크
- 유동비율 84.7%로 단기 유동성 관리 필요

## 추가 확인 필요
- 환율 변동 대응 전략 상세 검토
```

---

## 📊 성능 지표 (KPI)

| 지표 | 목표 | 실제 |
|------|------|------|
| 배치 완주율 | 95%+ | ✅ 100% (12-job 테스트) |
| 테이블 파싱 정확도 | 95%+ | ✅ 검증 완료 |
| 단위 변환 오류 | 0건 | ✅ 0건 |
| LLM 메모 근거 누락 | 0건 | ✅ 0건 |
| 테스트 통과 | 전체 | ✅ 59 passed |

---

## 🗂️ 프로젝트 구조

```
.
├── config/
│   ├── default.yaml              # 기본 설정
│   ├── batch_jobs.example.yaml   # 배치 작업 예시
│   └── insight_prompt_template.txt  # LLM 프롬프트
├── src/dart_xbrl_pipeline/
│   ├── cli.py                    # CLI 명령어 (analyze, batch)
│   ├── analyzer.py               # 단일 분석 로직
│   ├── batch_runner.py           # 🆕 배치 실행 엔진
│   ├── batch_models.py           # 🆕 배치 데이터 모델
│   ├── note_table_parser.py      # 🆕 주석 테이블 파서
│   ├── note_models.py            # 🆕 테이블 데이터 모델
│   ├── insight_writer.py         # 🆕 LLM 메모 작성기
│   ├── insight_models.py         # 🆕 인사이트 데이터 모델
│   ├── config_models.py          # 🆕 설정 검증 모델
│   ├── xbrl_parser.py            # XBRL 파싱 유틸리티
│   ├── opendart.py               # OpenDART API 클라이언트
│   ├── reporter.py               # 결과 저장
│   └── models.py                 # 기본 데이터 모델
├── tests/                        # 🆕 테스트 스위트 (59개 테스트)
├── reports/                      # 분석 결과 출력
├── data/                         # 다운로드 데이터
└── README.md                     # 이 파일
```

---

## 🚀 설치 및 실행

### 사전 요구사항
- Python 3.11+ (`.python-version` 참조)
- `uv` 패키지 매니저
- OpenDART API 키 ([발급 링크](https://opendart.fss.or.kr/intro/main.do))

### 1. 설치

```bash
# 저장소 클론
git clone <repository-url>
cd Dart_xbrl_FS_pipeline

# 가상환경 및 의존성 설치
uv sync
```

### 2. 환경 설정

```bash
# .env 파일 생성
cp .env.example .env

# .env 파일에 API 키 설정
# OPENDART_API_KEY=your_api_key_here
```

### 3. 실행 확인

```bash
# 기본 도움말
uv run dart-xbrl --help

# 배치 명령 도움말
uv run dart-xbrl batch --help
```

---

## 📖 사용법

### 단일 회사 분석 (기존 기능)

```bash
uv run dart-xbrl --corp-name 하나마이크론 --date 2026-03-19 --report-type annual
```

### 배치 분석 (신규 기능)

**Step 1: 배치 작업 파일 작성**

```yaml
# config/my_batch.yaml
max_workers: 4
retry_failed: true
jobs:
  - corp_name: 하나마이크론
    corp_code: "00286846"
    date: "2025-12-31"
    report_type: annual
  
  - corp_name: 삼성전자
    corp_code: "00126380"
    date: "2025-06-30"
    report_type: semiannual
  
  - corp_name: LG에너지솔루션
    corp_code: "01390338"
    date: "2025-03-31"
    report_type: q1
```

**Step 2: 배치 실행**

```bash
# 기본 배치 실행
uv run dart-xbrl batch --job-file config/my_batch.yaml

# 병렬 8개로 실행
uv run dart-xbrl batch --job-file config/my_batch.yaml --max-workers 8

# 주석 테이블 파싱 포함
uv run dart-xbrl batch --job-file config/my_batch.yaml --with-note-tables

# LLM 메모 생성 포함
uv run dart-xbrl batch --job-file config/my_batch.yaml --with-llm-memo

# 모든 기능 활성화
uv run dart-xbrl batch --job-file config/my_batch.yaml \
  --with-note-tables \
  --with-llm-memo \
  --max-workers 4

# 실패한 작업만 재시도
uv run dart-xbrl batch --job-file config/my_batch.yaml --retry-failed
```

---

## 📤 출력 파일

### 기본 출력
- `reports/<접수번호>_analysis.json` - JSON 분석 결과
- `reports/<접수번호>_analysis.md` - Markdown 분석 보고서

### 배치 실행 출력
- `reports/batch/<batch_id>/summary.json` - 배치 실행 요약
- `reports/batch/<batch_id>/state.json` - 작업 상태 (재개용)

### 주석 테이블 출력 (--with-note-tables)
- `reports/<접수번호>_note_tables.json` - 구조화된 테이블 데이터

### LLM 메모 출력 (--with-llm-memo)
- `reports/<접수번호>_profitability_memo.md` - AI 분석 메모

---

## 🧪 테스트

```bash
# 전체 테스트 실행
uv run pytest

# 특정 모듈 테스트
uv run pytest tests/unit/test_batch_runner.py
uv run pytest tests/unit/test_note_table_parser.py
uv run pytest tests/unit/test_insight_writer.py

# 커버리지 확인
uv run pytest --cov=src --cov-report=html
```

---

## ⚙️ 고급 설정

### config/default.yaml

```yaml
report_name_keywords:
  annual: ["사업보고서"]
  semiannual: ["반기보고서"]
  q1: ["1분기보고서"]
  q3: ["3분기보고서"]

reprt_codes:
  annual: "11011"
  semiannual: "11012"
  q1: "11013"
  q3: "11014"

analysis:
  profitability_keywords:
    revenue_mix: ["매출", "수익", "고객과의 계약"]
    cost_structure: ["매출원가", "원재료", "감가상각"]
    finance: ["금융수익", "금융비용", "이자비용", "차입금"]
    capex: ["유형자산", "건설중인자산", "시설투자"]
```

---

## 🛠️ 트러블슈팅

### API 키 오류

```bash
# API 키 확인
uv run python -c "from dart_xbrl_pipeline.config import load_settings; load_settings(); import os; print('API Key:', os.getenv('OPENDART_API_KEY')[:10] + '...' if os.getenv('OPENDART_API_KEY') else 'Not set')"
```

### 배치 실행 중단 후 재개

배치 실행이 중단되어도 `reports/batch/<batch_id>/state.json`에 상태가 저장됩니다. `--retry-failed` 옵션으로 실패한 작업만 재시도하세요.

### 디버그 모드

```bash
# 상세 로그 출력
uv run dart-xbrl batch --job-file config/my_batch.yaml --debug
```

---

## 📚 문서

- **빠른 시작 가이드**: [QUICK_start.md](./QUICK_start.md)
- **PRD (제품 요구사항)**: [PRD.md](./PRD.md)
- **로드맵**: [roadmap.md](./roadmap.md)

---

## 🔗 참고 링크

- OpenDART: https://opendart.fss.or.kr
- 공시검색 API: https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019001
- XBRL 원본파일 API: https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2019019

---

## 📝 라이선스

MIT License

---

## 🙋 지원

문제가 있으시면 GitHub Issues에 등록해 주세요.
