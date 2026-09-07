# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

YAI(연세대학교 AI 학회) 스터디 보고서 평가 도구. Streamlit UI에서 보고서 종류·이미지 개수·본문을 입력받아 OpenRouter 또는 Gemini API로 채점하고, 결과를 `results/` 폴더에 JSON+Markdown으로 저장한다. UI에서 AI 제공자(OpenRouter/Gemini)를 선택할 수 있다.

`legacy/`에는 개인 보고서 채점 기준의 이전 버전(`eval_criteria_personal_old.py`)만 참고용으로 남아 있다 (Notion/Google Sheets 자동 수집 파이프라인은 사용하지 않아 제거함).

## Setup

```bash
pip install streamlit requests python-dotenv openpyxl
```

`conda activate yai` 환경에 이미 설치되어 있다. (`openpyxl`은 `export_excel.py` 전용.)

`.env` 파일 필요 (OpenRouter / Gemini 중 최소 하나, 둘 다 있으면 UI에서 선택 가능):
```
OPENROUTER_API_KEY=<key>
OPENROUTER_MODEL=anthropic/claude-sonnet-4.5  # 선택, 기본값 동일

GEMINI_API_KEY=<key>
GEMINI_MODEL=gemini-3.6-flash                 # 선택, 기본값 동일
```

## Running

```bash
conda activate yai
streamlit run app.py
```

## Architecture

`app.py` 단일 파일 Streamlit 앱:

1. **입력 UI**: `st.selectbox`(AI 제공자: OpenRouter/Gemini — `.env`에 키가 있는 제공자만 노출), `st.text_input`(학회원 이름), `st.number_input`(주차), `st.text_input`(팀 이름), `st.selectbox`(보고서 종류: 개인 보고서/팀 Discussion/프로젝트팀/연구팀 최종 보고서), `st.number_input`(이미지 개수), `st.text_area`(본문).
2. **AI 평가** (`evaluate`): 선택된 제공자에 따라 `evaluate_openrouter` 또는 `evaluate_gemini`로 위임.
   - `evaluate_openrouter`: `requests`로 OpenRouter 엔드포인트(`https://openrouter.ai/api/v1/chat/completions`)에 직접 POST. 모델은 `OPENROUTER_MODEL`(기본 `anthropic/claude-sonnet-4.5`).
   - `evaluate_gemini`: `requests`로 Gemini `generateContent` 엔드포인트(`https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`)에 POST. 모델은 `GEMINI_MODEL`(기본 `gemini-3.6-flash`). `usageMetadata`를 OpenRouter의 `usage` 형태(`prompt_tokens`/`completion_tokens`/`total_tokens`)로 정규화하며, `cost`는 Gemini 응답에 없으므로 `-`로 표시.
   - 두 함수 모두 보고서 종류에 맞는 시스템 프롬프트(`eval_criteria_*.py`의 `EVAL_SYSTEM_PROMPT`)와 본문+이미지 개수를 전달해 JSON 응답을 받고, 실패 시 최대 3회 재시도.
3. **결과 저장** (`save_result`): `results/{타임스탬프}_{보고서종류}.json`(구조화 데이터, `member_name`/`week` 포함)과 `.md`(가독용 리포트) 두 파일로 저장.

`export_excel.py`는 별도 CLI 스크립트로, `results/*.json` 중 `--type`으로 지정한 report_type(기본값 "개인 보고서", `--type "팀 Discussion"`도 지원)이고 이름/`week`가 채워진 기록만 모아 `need.md` 형식의 엑셀(제출 현황 + 주차별 요약 Top3/제출/미제출)을 만든다. `REPORT_CONFIGS` 딕셔너리가 `entity`("member"=학회원 이름 기준 / "team"=팀 이름 기준)와 채점 항목을 정의하며, `app.py`의 `REPORT_TYPES`와 별개로 관리된다 (app.py는 Streamlit 모듈이라 import해서 재사용할 수 없음 — 항목을 바꾸면 두 파일을 함께 수정해야 함). `--roster` 없이는 미제출자 계산을 건너뛴다.

## Key Details

- **채점 기준 파일**: `app.py`의 `REPORT_TYPES` 딕셔너리가 보고서 종류 ↔ `eval_criteria_*.py` 파일 ↔ 채점 항목(JSON 키/라벨/만점)을 매핑한다.
  - `eval_criteria_personal.py` → 개인 보고서 (이해도/가독성/시각자료/토론, 16점)
  - `eval_criteria_team_session.py` → 팀 Discussion (팀세션 진행 내용/Discussion 과정/Discussion 확장성, 12점)
  - `eval_criteria_project.py` → 프로젝트팀 (프로젝트 진행 내용/기술적 이해/팀 인사이트/가독성 및 시각자료, 16점)
  - `eval_criteria_final.py` → 연구팀 최종 보고서 (학술적 서사/팀 인사이트/가독성/시각자료, 16점)

  새 보고서 종류를 추가하거나 채점 항목을 바꾸려면 해당 `eval_criteria_*.py`의 `EVAL_SYSTEM_PROMPT`와 `app.py`의 `REPORT_TYPES` 항목(`criteria`, `max_score`)을 함께 수정해야 한다.
- **이미지 처리**: 이미지 파일 자체는 AI에게 전달되지 않는다. 사용자가 UI에서 입력한 **개수**만 `[이미지 개수: N개]` 형태로 프롬프트에 포함되며, 채점 기준(`eval_criteria_personal.py`)도 개수 기반이다.
- **API 키**는 `.env`의 `OPENROUTER_API_KEY` / `GEMINI_API_KEY`에서 읽는다. 소스코드에 하드코딩된 키는 없음. 둘 다 설정돼 있으면 UI에서 제공자를 고를 수 있고, 하나만 있으면 그 제공자만 선택지로 노출된다.
- **결과 저장 폴더**(`results/`)는 학회원 개인정보·보고서 원문을 포함하므로 `.gitignore`에 포함되어 있다.
- **`member_name`/`week`**: `export_excel.py` 집계용으로 추가된 필드. UI에서 입력하지 않으면 빈 값/`None`으로 저장되고, `export_excel.py`는 그런 기록을 건너뛴다 (두 필드 도입 이전 결과들도 마찬가지로 스킵됨).
- **레거시 코드** (`legacy/eval_criteria_personal_old.py`): 개인 보고서 채점 기준의 이전 버전. 참고용으로만 보관, 현재 앱(`eval_criteria_personal.py`)과는 독립적으로 동작.
