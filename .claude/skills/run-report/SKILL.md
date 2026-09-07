---
name: run-report
description: YAI 보고서 평가 Streamlit 앱 실행 및 자동 디버깅.
argument-hint: "[--stop]"
allowed-tools: Bash, Read, Edit, Grep
---

# YAI 보고서 평가 앱 실행

작업 디렉토리: 이 스킬 파일이 속한 프로젝트 루트 (`app.py`가 있는 위치)
앱: `app.py` (Streamlit)
실행 인터프리터: conda 환경 `yai`

## 실행 방법 결정

인자(`$ARGUMENTS`)를 확인해 아래 중 하나를 선택한다:

- `--stop` → 실행 중인 streamlit 프로세스 종료
  ```bash
  pkill -f "streamlit run app.py"
  ```

- 그 외 (기본) → 앱 실행
  ```bash
  conda run -n yai streamlit run app.py
  ```
  포그라운드로 실행되며 브라우저 URL을 출력한다. 백그라운드로 띄우고 싶다면 `run_in_background: true`로 실행한다.

## 실행 절차

1. **앱 실행**: 위 명령어를 Bash로 실행한다 (보통 `run_in_background: true` 권장 — Streamlit은 서버 프로세스라 종료되지 않음).
2. **기동 확인**: 출력에서 `Local URL: http://localhost:PORT`를 확인하고 사용자에게 알려준다.
3. **에러 발생 시 자동 디버깅**:
   a. 트레이스백에서 파일명과 줄 번호를 파악한다.
   b. `app.py` 또는 `eval_criteria_*.py`의 해당 줄 주변을 Read로 읽는다.
   c. 원인을 분석하고 수정안을 제시한다.
   d. 사용자 승인 후 Edit으로 수정하고 재실행한다.

## 주요 에러 패턴 및 대응

| 에러 | 원인 | 대응 |
|------|------|------|
| `ModuleNotFoundError: streamlit` | `yai` conda 환경이 아닌 다른 인터프리터로 실행 | `conda run -n yai ...`로 실행했는지 확인 |
| UI에 "OPENROUTER_API_KEY가 설정되어 있지 않습니다" / "GEMINI_API_KEY가 설정되어 있지 않습니다" | `.env` 파일 없음/키 누락 | `.env`의 해당 키(`OPENROUTER_API_KEY` 또는 `GEMINI_API_KEY`) 확인 |
| `401 Unauthorized` (OpenRouter) / `403`·`API key not valid` (Gemini) | API 키 오류 | `.env`의 해당 API 키 재확인 |
| `429` (OpenRouter/Gemini) | Rate limit | `evaluate()` 내에서 최대 3회 재시도됨 — 계속 발생 시 잠시 후 재시도 |
| `404 ... no longer available` (Gemini) | `GEMINI_MODEL`에 지정한 모델이 만료/폐기됨 | 에러 메시지가 안내하는 대체 모델명으로 `.env`의 `GEMINI_MODEL` 갱신 (기본값은 `app.py`에서도 주기적으로 갱신 필요) |
| "채점 기준이 아직 준비되지 않았습니다" | 선택한 보고서 종류의 `EVAL_SYSTEM_PROMPT`가 `None` | 해당 `eval_criteria_*.py`에 프롬프트 작성 필요 (정상 상황이라면 발생하지 않음) |
| `json.JSONDecodeError` | AI 응답이 JSON 형식이 아님 | 재시도로 해결되는 경우가 많음. OpenRouter는 `response_format` 지원 모델인지, Gemini는 `responseMimeType` 지원 모델인지 확인 |

## 성공 시 보고

앱 실행이 완료되면 아래 내용을 요약해서 보여준다:
- 접속 URL (`Local URL`)
- 채점 요청이 있었다면: 보고서 종류, 총점, `results/`에 저장된 파일명
