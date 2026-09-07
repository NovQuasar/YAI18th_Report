"""
YAI 보고서 평가 도구 (Streamlit UI)
------------------------------------------
사용법:
  1. conda activate yai
  2. streamlit run app.py

.env 파일에 아래 항목 필요 (OpenRouter / Gemini 중 최소 하나):
  OPENROUTER_API_KEY=<key>
  OPENROUTER_MODEL=anthropic/claude-sonnet-4.5   # 선택, 기본값 동일

  GEMINI_API_KEY=<key>
  GEMINI_MODEL=gemini-3.6-flash                  # 선택, 기본값 동일
"""

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv

from eval_criteria_personal import EVAL_SYSTEM_PROMPT as PERSONAL_PROMPT
from eval_criteria_team_session import EVAL_SYSTEM_PROMPT as TEAM_SESSION_PROMPT
from eval_criteria_project import EVAL_SYSTEM_PROMPT as PROJECT_PROMPT
from eval_criteria_final import EVAL_SYSTEM_PROMPT as FINAL_PROMPT

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
GEMINI_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

PROVIDERS = {
    "OpenRouter": {"available": bool(OPENROUTER_API_KEY), "model": OPENROUTER_MODEL},
    "Gemini": {"available": bool(GEMINI_API_KEY), "model": GEMINI_MODEL},
}

# 재시도해볼 만한 일시적 오류 (레이트리밋/서버 과부하). 401/404 등은 재시도해도 해결되지 않으므로 즉시 실패시킨다.
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _is_retryable(exc):
    """requests.HTTPError면 상태 코드로 판단하고, 그 외(타임아웃/JSON 파싱 실패 등)는 재시도 대상으로 본다."""
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code in RETRYABLE_STATUS_CODES
    return True


RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)
SUMMARY_PATH = RESULTS_DIR / "summary.md"

# 보고서 종류별 설정.
# - prompt: eval_criteria_*.py의 EVAL_SYSTEM_PROMPT
# - criteria: (JSON 응답의 키, 화면에 보여줄 라벨, 만점) 목록
# - max_score: 총점 만점
REPORT_TYPES = {
    "개인 보고서": {
        "prompt": PERSONAL_PROMPT,
        "criteria": [
            ("이해도", "이해도", 5),
            ("가독성", "가독성", 5),
            ("시각자료", "시각자료", 3),
            ("토론", "토론", 3),
        ],
        "max_score": 16,
    },
    "팀 Discussion": {
        "prompt": TEAM_SESSION_PROMPT,
        "criteria": [
            ("팀세션_진행내용", "팀세션 진행 내용", 5),
            ("Discussion_과정", "Discussion 과정", 5),
            ("Discussion_확장성", "Discussion 확장성", 2),
        ],
        "max_score": 12,
    },
    "프로젝트팀": {
        "prompt": PROJECT_PROMPT,
        "criteria": [
            ("프로젝트_진행내용", "프로젝트 진행 내용", 5),
            ("기술적_이해", "기술적 이해", 5),
            ("팀_인사이트", "팀 인사이트", 3),
            ("가독성_및_시각자료", "가독성 및 시각자료", 3),
        ],
        "max_score": 16,
    },
    "연구팀 최종 보고서": {
        "prompt": FINAL_PROMPT,
        "criteria": [
            ("학술적_서사", "학술적 서사", 5),
            ("팀_인사이트", "팀 인사이트", 5),
            ("가독성", "가독성", 3),
            ("시각자료", "시각자료", 3),
        ],
        "max_score": 16,
    },
}


def _extract_json(text):
    """모델이 ```json ... ``` 코드펜스로 감싸서 응답해도 JSON 부분만 뽑아낸다."""
    text = text.strip()
    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    return text


def evaluate_openrouter(system_prompt, report_text, image_count, retries=3):
    """OpenRouter(Claude 등)로 보고서 평가. 성공 시 딕셔너리 반환, 실패 시 예외 발생."""
    user_content = f"**보고서 내용:**\n{report_text}\n\n[이미지 개수: {image_count}개]"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "max_tokens": 4096,  # gpt-5 등 추론 모델은 reasoning 토큰도 이 한도를 나눠 쓰므로 여유있게 설정
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    }

    last_error = None
    for attempt in range(retries):
        try:
            r = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=60)
            r.raise_for_status()
            data = r.json()
            text = data["choices"][0]["message"]["content"]
            result = json.loads(_extract_json(text))
            usage = data.get("usage", {})
            return result, usage
        except Exception as e:
            last_error = e
            if not _is_retryable(e) or attempt == retries - 1:
                break
            time.sleep(2 * (attempt + 1))  # 2s, 4s, 6s ... 과부하/레이트리밋이 가라앉을 시간을 준다
    raise last_error


def evaluate_gemini(system_prompt, report_text, image_count, retries=3):
    """Gemini API로 보고서 평가. 성공 시 딕셔너리 반환, 실패 시 예외 발생."""
    user_content = f"**보고서 내용:**\n{report_text}\n\n[이미지 개수: {image_count}개]"
    url = GEMINI_URL_TEMPLATE.format(model=GEMINI_MODEL)
    headers = {"Content-Type": "application/json"}
    params = {"key": GEMINI_API_KEY}
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_content}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 4096,
            "responseMimeType": "application/json",
        },
    }

    last_error = None
    for attempt in range(retries):
        try:
            r = requests.post(url, headers=headers, params=params, json=payload, timeout=60)
            r.raise_for_status()
            data = r.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            result = json.loads(_extract_json(text))
            usage_meta = data.get("usageMetadata", {})
            # OpenRouter의 usage 형태(prompt_tokens/completion_tokens/total_tokens)에 맞춰 정규화.
            usage = {
                "prompt_tokens": usage_meta.get("promptTokenCount", "-"),
                "completion_tokens": usage_meta.get("candidatesTokenCount", "-"),
                "total_tokens": usage_meta.get("totalTokenCount", "-"),
                "cost": "-",  # Gemini API는 비용을 응답에 포함하지 않음
            }
            return result, usage
        except Exception as e:
            last_error = e
            if not _is_retryable(e) or attempt == retries - 1:
                break
            time.sleep(2 * (attempt + 1))  # 2s, 4s, 6s ... 과부하/레이트리밋이 가라앉을 시간을 준다
    raise last_error


def evaluate(provider, system_prompt, report_text, image_count, retries=3):
    """선택된 provider(OpenRouter/Gemini)로 보고서 평가를 위임한다."""
    if provider == "Gemini":
        return evaluate_gemini(system_prompt, report_text, image_count, retries=retries)
    return evaluate_openrouter(system_prompt, report_text, image_count, retries=retries)


def save_result(report_type, config, image_count, report_text, result, usage, team_name="", member_name="", week=None):
    """평가 결과를 results/ 폴더에 JSON + Markdown 두 형식으로 저장."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_type = report_type.replace(" ", "")
    base_name = f"{timestamp}_{safe_type}"
    team_name = team_name or result.get("team_name", "")

    record = {
        "timestamp": timestamp,
        "report_type": report_type,
        "team_name": team_name,
        "member_name": member_name,
        "week": week,
        "image_count": image_count,
        "report_text": report_text,
        "result": result,
        "usage": usage,
    }
    json_path = RESULTS_DIR / f"{base_name}.json"
    json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        f"# {report_type} 평가 결과",
        "",
        f"- 평가 일시: {timestamp}",
        f"- 주차: {week}주차" if week else "- 주차: (미입력)",
        f"- 학회원 이름: {member_name or '(미입력)'}",
        f"- 이미지 개수: {image_count}",
        f"- 팀 이름: {team_name}",
    ]
    if result.get("team_type"):
        md_lines.append(f"- 팀 유형: {result.get('team_type', '')}")
    md_lines += [
        "",
        "## 점수",
        "",
        "| 항목 | 점수 | 코멘트 |",
        "|---|---|---|",
    ]
    for key, label, _ in config["criteria"]:
        item = result.get(key, {})
        md_lines.append(f"| {label} | {item.get('score', '')} | {item.get('comment', '')} |")
    md_lines += [
        "",
        f"**총점: {result.get('총점', '')} / {config['max_score']}**",
        "",
        "## 종합평가",
        "",
        result.get("종합평가", ""),
        "",
        "## API 사용량",
        "",
        f"- 입력 토큰: {usage.get('prompt_tokens', '-')}",
        f"- 출력 토큰: {usage.get('completion_tokens', '-')}",
        f"- 총 토큰: {usage.get('total_tokens', '-')}",
        f"- 비용: ${usage.get('cost', '-')}",
        "",
        "## 원문",
        "",
        "```",
        report_text,
        "```",
    ]
    md_path = RESULTS_DIR / f"{base_name}.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    return json_path, md_path


def append_summary_line(team_name, report_type, config, result, member_name="", week=None):
    """채점 결과를 [4 / 5 / 2] = 11 형태로 results/summary.md에 순서대로 한 줄 추가."""
    scores = [str(result.get(key, {}).get("score", "-")) for key, _, _ in config["criteria"]]
    total = result.get("총점", "-")
    week_label = f"{week}주차" if week else "(주차 미입력)"
    member_label = member_name or "(이름 미입력)"
    line = f"- {week_label} | {team_name or '(팀 이름 미입력)'} | {member_label} | {report_type} | [{' / '.join(scores)}] = {total}"

    if not SUMMARY_PATH.exists():
        SUMMARY_PATH.write_text("# 채점 요약\n\n", encoding="utf-8")
    with SUMMARY_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


# ────────────────────────────────────────────
# UI
# ────────────────────────────────────────────

st.set_page_config(page_title="YAI 보고서 평가", page_icon="📝")
st.title("📝 YAI 보고서 평가 도구")

available_providers = [name for name, info in PROVIDERS.items() if info["available"]] or list(PROVIDERS.keys())
provider = st.selectbox("AI 제공자", available_providers)
st.caption(f"모델: {PROVIDERS[provider]['model']}")

col_a, col_b = st.columns(2)
member_name_input = col_a.text_input("학회원 이름", placeholder="예: 김야이")
week_input = col_b.number_input("주차", min_value=1, step=1, value=1)

team_name_input = st.text_input("팀 이름", placeholder="예: NLP팀")
report_type = st.selectbox("보고서 종류", list(REPORT_TYPES.keys()))
image_count = st.number_input("이미지 개수", min_value=0, step=1, value=0)
report_text = st.text_area("보고서 본문", height=400, placeholder="여기에 보고서 본문을 붙여넣으세요.")

if st.button("평가하기", type="primary"):
    config = REPORT_TYPES[report_type]
    system_prompt = config["prompt"]

    if not PROVIDERS[provider]["available"]:
        key_name = "OPENROUTER_API_KEY" if provider == "OpenRouter" else "GEMINI_API_KEY"
        st.error(f"{key_name}가 설정되어 있지 않습니다. .env 파일을 확인하세요.")
    elif system_prompt is None:
        st.warning(f"'{report_type}' 채점 기준이 아직 준비되지 않았습니다.")
    elif not report_text.strip():
        st.warning("보고서 본문을 입력하세요.")
    else:
        with st.spinner("AI가 채점 중입니다..."):
            try:
                result, usage = evaluate(provider, system_prompt, report_text, image_count)
            except Exception as e:
                st.error(f"평가 중 오류가 발생했습니다: {e}")
                result, usage = None, None

        if result:
            st.success("평가가 완료되었습니다.")

            cols = st.columns(len(config["criteria"]))
            for col, (key, label, max_score) in zip(cols, config["criteria"]):
                col.metric(label, f"{result.get(key, {}).get('score', '-')} / {max_score}")

            st.markdown(f"### 총점: {result.get('총점', '-')} / {config['max_score']}")

            for key, label, _ in config["criteria"]:
                item = result.get(key, {})
                st.markdown(f"**{label} 코멘트:** {item.get('comment', '')}")

            st.markdown("### 종합평가")
            st.write(result.get("종합평가", ""))

            st.markdown("### API 사용량")
            u1, u2, u3, u4 = st.columns(4)
            u1.metric("입력 토큰", usage.get("prompt_tokens", "-"))
            u2.metric("출력 토큰", usage.get("completion_tokens", "-"))
            u3.metric("총 토큰", usage.get("total_tokens", "-"))
            u4.metric("비용", f"${usage.get('cost', '-')}")

            team_name = team_name_input.strip()
            member_name = member_name_input.strip()
            json_path, md_path = save_result(
                report_type, config, image_count, report_text, result, usage,
                team_name=team_name, member_name=member_name, week=int(week_input),
            )
            append_summary_line(team_name, report_type, config, result, member_name=member_name, week=int(week_input))
            st.info(f"결과 저장됨: {json_path.name}, {md_path.name} (요약: {SUMMARY_PATH.name}에 추가됨)")
