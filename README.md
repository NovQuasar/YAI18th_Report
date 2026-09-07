# YAI 보고서 평가 도구

연세대학교 AI 학회(YAI) 스터디 보고서를 직접 붙여넣어, OpenRouter 또는 Gemini API로 채점하는 Streamlit UI 도구입니다.

---

## 동작 방식

```
UI에서 AI 제공자(OpenRouter/Gemini) 선택 → 보고서 종류/이미지 개수/본문 입력 → AI 채점 → results/ 폴더에 저장
```

1. **입력**: UI에서 AI 제공자(OpenRouter 또는 Gemini, `.env`에 키가 있는 것만 선택 가능), 학회원 이름, 주차, 팀 이름, 보고서 종류(개인 보고서 / 팀 Discussion / 프로젝트팀 / 연구팀 최종 보고서), 이미지 개수, 보고서 본문을 입력
2. **AI 채점**: 입력한 텍스트를 선택한 제공자(OpenRouter 경유 Claude, 또는 Gemini API 직접 호출)에 전달해 보고서 종류별 채점 항목을 JSON으로 채점
3. **결과 저장**: 채점 결과를 `results/` 폴더에 JSON(데이터용) + Markdown(가독용) 두 형식으로 저장

---

## 설치

```bash
pip install streamlit requests python-dotenv openpyxl
```

> `conda activate yai` 환경에 이미 설치되어 있습니다. (`openpyxl`은 `export_excel.py` 실행에 필요합니다.)

---

## 환경 설정

프로젝트 루트에 `.env` 파일을 만들고 아래 항목을 입력합니다. OpenRouter와 Gemini 중 최소 하나만 있으면 되고, 둘 다 있으면 앱 UI에서 어떤 제공자를 쓸지 고를 수 있습니다.

```env
# OpenRouter API 키 (https://openrouter.ai/keys 에서 발급)
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxx

# (선택) OpenRouter 모델 슬러그. 기본값: anthropic/claude-sonnet-4.5
# OPENROUTER_MODEL=anthropic/claude-sonnet-4.5

# Gemini API 키 (https://aistudio.google.com/apikey 에서 발급)
GEMINI_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx

# (선택) Gemini 모델명. 기본값: gemini-3.6-flash
# GEMINI_MODEL=gemini-3.6-flash
```

---

## 실행 방법

```bash
conda activate yai
streamlit run app.py
```

브라우저가 자동으로 열리며, UI에서 AI 제공자 선택 → 학회원 이름/주차 입력 → 팀 이름/보고서 종류 선택 → 이미지 개수 입력 → 본문 붙여넣기 → "평가하기" 버튼을 누르면 채점됩니다.

---

## 채점 기준

| 파일 | 대상 |
|---|---|
| `eval_criteria_personal.py` | 개인 보고서 |
| `eval_criteria_team_session.py` | 팀 Discussion |
| `eval_criteria_project.py` | 프로젝트팀 |
| `eval_criteria_final.py` | 연구팀 최종 보고서 |

개인 보고서 채점 항목 (총 16점):

| 항목 | 만점 | 설명 |
|---|---|---|
| 이해도 | 5점 | 논문/개념 이해 수준 |
| 가독성 | 5점 | 구조화·가독성 |
| 시각자료 | 3점 | 입력한 이미지 개수 기준 |
| 토론 | 3점 | 비판적 사고·토론 기여도 |
| **총점** | **16점** | |

팀 Discussion 채점 항목 (총 12점): 팀세션 진행 내용(5) / Discussion 과정(5) / Discussion 확장성(2)

프로젝트팀 채점 항목 (총 16점): 프로젝트 진행 내용(5) / 기술적 이해(5) / 팀 인사이트(3) / 가독성 및 시각자료(3)

연구팀 최종 보고서 채점 항목 (총 16점): 학술적 서사(5) / 팀 인사이트(5) / 가독성(3) / 시각자료(3)

각 파일의 `EVAL_SYSTEM_PROMPT`를 수정하면 채점 기준을 바꿀 수 있고, 항목 구성 자체를 바꾸려면 `app.py`의 `REPORT_TYPES`도 함께 수정해야 합니다.

---

## 평가 결과 저장

`results/` 폴더에 요청 1건당 아래 두 파일이 생성됩니다.

- `{타임스탬프}_{보고서종류}.json` — 점수·코멘트·원문을 모두 담은 구조화 데이터
- `{타임스탬프}_{보고서종류}.md` — 사람이 바로 읽기 편한 리포트

학회원 개인정보와 보고서 원문이 포함되므로 `results/`는 `.gitignore`에 포함되어 있습니다. **절대 커밋하지 마세요.**

---

## 제출 현황 엑셀로 내보내기 (`export_excel.py`)

`results/`에 쌓인 평가 결과를 모아 제출 현황 엑셀 파일을 만듭니다. "개인 보고서"는 학회원별로, "팀 Discussion"은 팀별로 집계합니다.

```bash
conda activate yai
python export_excel.py                                    # 개인 보고서 → results/제출현황_개인보고서.xlsx
python export_excel.py --type "팀 Discussion"               # 팀 Discussion → results/제출현황_팀Discussion.xlsx
python export_excel.py --roster members.txt                # 미제출자까지 표시하려면 명단 파일 지정
python export_excel.py --output 어딘가/파일명.xlsx            # 출력 경로 지정
```

- 집계되려면 앱에서 평가할 때 필요한 이름/주차를 입력해야 합니다. "개인 보고서"는 **학회원 이름**+**주차**, "팀 Discussion"은 **팀 이름**+**주차**가 필요합니다. 값이 비어 있는 기록은 건너뛰고 몇 건이 스킵됐는지 알려줍니다.
- `--roster`로 넘기는 명단 파일은 한 줄에 하나(개인 보고서는 학회원 이름, 팀 Discussion은 팀 이름), `#`으로 시작하는 줄은 주석으로 무시됩니다. 넘기지 않으면 "❌ 미제출" 칸은 비워둡니다.
- 결과물은 "보고서 제출 현황"(개인/팀 × 주차별 채점 항목) / "주차별 요약"(Top3 순위, 제출자, 미제출자) 두 개 탭으로 구성됩니다.
- 명단 파일과 출력된 `.xlsx`는 실명을 담고 있으므로 `.gitignore`에 포함되어 있습니다.

---

## 주의사항

- `.env` 파일은 `.gitignore`에 포함되어 있으므로 **절대 커밋하지 마세요.**
- 이미지 자체는 AI에게 전달되지 않고, 사용자가 입력한 **개수**만 채점에 반영됩니다.
