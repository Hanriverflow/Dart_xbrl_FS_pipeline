# QUICK_start.md - DART XBRL 파이프라인 빠른 시작 가이드

> **⏱️ 예상 소요 시간**: 15분  
> **🎯 목표**: 첫 배치 분석 실행까지

---

## 목차

1. [설치 (3분)](#1-설치-3분)
2. [환경 설정 (2분)](#2-환경-설정-2분)
3. [첫 실행 (5분)](#3-첫-실행-5분)
4. [배치 분석 (5분)](#4-배치-분석-5분)
5. [고급 기능](#5-고급-기능)
6. [문제 해결](#6-문제-해결)

---

## 1. 설치 (3분)

### 1.1 Python 3.11+ 확인

```bash
python --version
# Python 3.11.x 이상이어야 합니다
```

### 1.2 uv 설치

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 1.3 프로젝트 클론 및 설치

```bash
# 저장소 클론
git clone <repository-url>
cd Dart_xbrl_FS_pipeline

# 가상환경 생성 및 의존성 설치
uv sync
```

**✅ 확인:** `uv sync` 실행 후 `.venv` 폴더가 생성되면 성공

---

## 2. 환경 설정 (2분)

### 2.1 OpenDART API 키 발급

1. https://opendart.fss.or.kr 접속
2. 회원가입 → 로그인
3. **마이페이지** → **API 인증키 관리**
4. **인증키 발급** 클릭
5. 발급된 키 복사

### 2.2 .env 파일 설정

```bash
# 템플릿 복사
cp .env.example .env

# .env 파일 편집
```

**.env 파일 내용:**
```dotenv
OPENDART_API_KEY=your_actual_api_key_here
```

**⚠️ 주의:** `.env` 파일은 절대 Git에 커밋하지 마세요!

### 2.3 설정 확인

```bash
uv run python -c "from dart_xbrl_pipeline.config import load_settings; load_settings(); import os; print('✅ API Key 설정 완료:', os.getenv('OPENDART_API_KEY')[:8] + '...')"
```

---

## 3. 첫 실행 (5분)

### 3.1 단일 회사 분석

**가장 간단한 예시 - 삼성전자:**

```bash
uv run dart-xbrl --corp-name 삼성전자 --date 2026-03-19 --report-type annual
```

**출력 예시:**
```
🔄 삼성전자(00445054) 분석 중...
📥 XBRL 다운로드 완료: 20260319000032
📊 손익계산서 추출 완료 (12개 계정)
📝 주석 분석 완료 (45개 키워드 적중)
✅ 분석 완료
- json: reports\20260319000032_analysis.json
- markdown: reports\20260319000032_analysis.md
```

### 3.2 결과 확인

```bash
# Markdown 보고서 읽기
cat reports/20260319000032_analysis.md

# JSON 데이터 확인
uv run python -c "import json; print(json.dumps(json.load(open('reports/20260319000032_analysis.json')), indent=2, ensure_ascii=False))"
```

**✅ 첫 실행 성공!** 이제 배치 분석으로 넘어갑니다.

---

## 4. 배치 분석 (5분)

### 4.1 배치 작업 파일 작성

```bash
# 예시 파일 복사
cp config/batch_jobs.example.yaml config/my_first_batch.yaml
```

**config/my_first_batch.yaml 수정:**
```yaml
max_workers: 2
retry_failed: true
jobs:
  - corp_name: 삼성전자
    corp_code: "00126380"
    date: "2025-12-31"
    report_type: annual
  
  - corp_name: SK하이닉스
    corp_code: "00164779"
    date: "2025-09-30"
    report_type: q3
```

### 4.2 배치 실행

```bash
# 기본 배치 실행
uv run dart-xbrl batch --job-file config/my_first_batch.yaml
```

**실행 중 출력:**
```
🚀 배치 실행 시작 (총 3개 작업)
⚙️  병렬 작업자: 2개

[1/3] 🔄 삼성전자 (annual) 분석 중...
[2/3] 🔄 삼성전자 (semiannual) 분석 중...
✅ [1/3] 삼성전자 완료 (12.3s)
[3/3] 🔄 SK하이닉스 (q3) 분석 중...
✅ [2/3] 삼성전자 완료 (15.7s)
✅ [3/3] SK하이닉스 완료 (11.2s)

📊 배치 완료 요약
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
총 작업:     3
성공:        3 ✅
실패:        0 ❌
건너뜀:      0 ⏭️
총 소요:     28.4s
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📁 결과 저장: reports\batch\batch_20260319_143052\
   - summary.json
   - state.json
```

### 4.3 결과 확인

```bash
# 배치 요약 확인
cat reports/batch/batch_*/summary.json | uv run python -m json.tool

# 개별 회사 결과 확인
ls reports/20260319*.md
```

---

## 5. 고급 기능

### 5.1 주석 테이블 파싱 (--with-note-tables)

XBRL 주석에서 표 형태의 숫자 데이터를 추출합니다:

```bash
uv run dart-xbrl batch \
  --job-file config/my_first_batch.yaml \
  --with-note-tables
```

**추가 출력:**
- `reports/<접수번호>_note_tables.json`

**확인:**
```bash
uv run python -c "
import json
with open('reports/20260319000032_note_tables.json') as f:
    data = json.load(f)
    for table in data['tables']:
        print(f'📊 {table[\"title\"]} ({table[\"table_type\"]})')
        print(f'   단위: {table[\"unit\"]}, 행: {len(table[\"rows\"])}개')
"
```

### 5.2 LLM 수익성 메모 (--with-llm-memo)

AI가 재무 데이터를 분석하여 투자 메모를 생성합니다:

```bash
# LLM 메모 생성 (OpenAI API 키 필요)
export OPENAI_API_KEY=your_openai_key

uv run dart-xbrl batch \
  --job-file config/my_first_batch.yaml \
  --with-llm-memo
```

**추가 출력:**
- `reports/<접수번호>_profitability_memo.md`

**출력 예시:**
```markdown
# 삼성전자 수익성 개선 포인트 분석

## 핵심 개선 포인트
1. **차입금 이자부담 감소**: 이자비용 28.3% 감소 (table: tbl_a3f2b8d9)
   - 근거: 2024년 1,228.7억원 → 2025년 880.5억원

## 근거 수치
- 영업활동현금흐름: +326.9% 증가
- 부채비율: 221.0% → 209.2% 개선

## 리스크
- 유동비율 84.7%로 단기 유동성 관리 필요
```

### 5.3 모든 기능 활성화

```bash
uv run dart-xbrl batch \
  --job-file config/my_first_batch.yaml \
  --with-note-tables \
  --with-llm-memo \
  --max-workers 4
```

### 5.4 실패한 작업 재시도

배치 실행 중 일부 작업이 실패하면:

```bash
# 실패한 작업만 재시도
uv run dart-xbrl batch \
  --job-file config/my_first_batch.yaml \
  --retry-failed
```

**동작:**
- 이전 성공 작업은 자동으로 건너뜀 (skipped)
- 실패한 작업만 다시 실행
- 저장된 상태에서 재개

---

## 6. 문제 해결

### 6.1 API 키 오류

**증상:**
```
에러: OpenDART API 키가 설정되지 않았습니다
```

**해결:**
```bash
# .env 파일 확인
cat .env
# OPENDART_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx

# 파일이 없으면 생성
cp .env.example .env
# 편집기로 API 키 입력
```

### 6.2 회사를 찾을 수 없음

**증상:**
```
에러: 회사를 찾을 수 없습니다: xxx
```

**해결:**
```bash
# 정확한 회사명 확인
# - DART 공시 시스템에서 회사명 검색
# - 또는 corp_code 직접 지정

uv run dart-xbrl --corp-name "삼성전자" --corp-code "00126380"
```

### 6.3 공시를 찾을 수 없음

**증상:**
```
에러: 조건에 맞는 공시를 찾지 못했습니다
```

**해결:**
```bash
# 날짜 범위 확대
curl -s "https://opendart.fss.or.kr/api/list.json?crtfc_key=YOUR_KEY&corp_code=00126380&bgn_de=20200101&end_de=20261231&page_count=100" | uv run python -m json.tool

# 보고서 유형 변경
curl -s "https://opendart.fss.or.kr/api/list.json?crtfc_key=YOUR_KEY&corp_code=00126380&bgn_de=20250101&end_de=20251231&last_reprt_at=Y" | uv run python -m json.tool
```

### 6.4 디버그 모드

**문제가 지속되면 디버그 모드로 실행:**

```bash
uv run dart-xbrl batch \
  --job-file config/my_first_batch.yaml \
  --debug
```

**출력:**
- 전체 스택 트레이스
- 상세 로그
- HTTP 요청/응답

### 6.5 테스트 실행으로 검증

```bash
# 전체 테스트
uv run pytest

# 특정 테스트
uv run pytest tests/unit/test_batch_runner.py -v
```

---

## 📚 다음 단계

- **전체 기능**: [README.md](./README.md)
- **개발 가이드**: [PRD.md](./PRD.md)
- **구현 로드맵**: [roadmap.md](./roadmap.md)

---

## 💡 팁

1. **첫 실행은 단일 회사로 테스트** → 배치로 확장
2. **max_workers는 처음에 2로 시작** → 서버 부하 확인 후 증가
3. **LLM 메모는 마지막에 추가** → 기본 파이프라인 먼저 검증
4. **정기적으로 테스트 실행** → `uv run pytest`

---

**🎉 축하합니다! 이제 DART XBRL 파이프라인을 마스터했습니다!**
