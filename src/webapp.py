import re
import sys
import subprocess
from collections import Counter
from pathlib import Path

import streamlit as st

from src.coach import generate_learning_coach_report

BASE_DIR = Path(__file__).resolve().parent.parent
TRANSCRIPT_DIR = BASE_DIR / "data" / "transcripts"
SUMMARY_DIR = BASE_DIR / "data" / "summaries"

def read_text(path: Path) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return path.read_text(encoding=enc)
        except Exception:
            pass
    return path.read_text(errors="ignore")

def get_transcript_files():
    if not TRANSCRIPT_DIR.exists():
        return []
    return sorted(
        [p for p in TRANSCRIPT_DIR.glob("*.txt") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

def get_summary_path(transcript_path: Path) -> Path:
    return SUMMARY_DIR / f"{transcript_path.stem}_summary.md"

def get_sessions():
    sessions = []
    for txt in get_transcript_files():
        summary = get_summary_path(txt)
        sessions.append(
            {
                "name": txt.stem,
                "transcript": txt,
                "summary": summary if summary.exists() else None,
            }
        )
    return sessions

def run_module(module_name, args):
    cmd = [sys.executable, "-m", module_name] + args
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        cwd=str(BASE_DIR),
    )
    if result.returncode != 0:
        return False, (result.stderr or result.stdout or "실행 실패").strip()
    return True, result.stdout.strip()

def run_cli(args):
    return run_module("src.cli", args)

def run_notion_push(summary_path: Path):
    return run_module("src.notion_push", ["--file", str(summary_path)])

def extract_keywords(text: str, top_k: int = 8):
    tokens = re.findall(r"[A-Za-z가-힣]{2,}", text.lower())
    stopwords = {
        "그리고","그러면","하지만","입니다","있는","하는","에서","으로","대한","하게",
        "그냥","이런","저런","정리","요약","핵심","부분","내용","강의","이번","관련",
        "the","and","that","with","from","this","have","will","your","what"
    }
    filtered = [t for t in tokens if t not in stopwords and len(t) >= 2]
    return [word for word, _ in Counter(filtered).most_common(top_k)]

def build_simple_recommendations(sessions):
    recommendations = []
    combined = ""

    for s in sessions[:5]:
        if s["summary"] and s["summary"].exists():
            combined += "\n" + read_text(s["summary"])

    keywords = extract_keywords(combined, top_k=6)

    if len(sessions) < 3:
        recommendations.append("강의 3개 이상 쌓이면 추천 정확도가 더 좋아짐")
    else:
        recommendations.append("최근 3개 강의를 묶어 공통 개념 복습하기")

    if keywords:
        recommendations.append(f"반복 키워드 우선 복습: {', '.join(keywords[:3])}")

    if sessions:
        recommendations.append(f"우선 다시 볼 세션: {sessions[0]['name']}")

    questions = []
    if keywords:
        questions = [
            f"{keywords[0]} 개념을 강의 기준으로 설명해줘",
            f"{keywords[0]}가 왜 중요한지 말해줘",
            f"{keywords[0]} 관련 시험 포인트 3개만 뽑아줘",
        ]
    else:
        questions = [
            "이 강의 핵심을 3줄로 요약해줘",
            "내 이해가 맞는지 검증해줘",
            "시험 전 핵심 포인트 3개를 알려줘",
        ]

    return recommendations, keywords, questions

st.set_page_config(page_title="LectureLens", page_icon="🎓", layout="wide")

if "chat_history_map" not in st.session_state:
    st.session_state.chat_history_map = {}

if "coach_reports" not in st.session_state:
    st.session_state.coach_reports = {}

sessions = get_sessions()

st.title("🎓 LectureLens")
st.caption("강의 전사 · 요약 · 이해점검 · Notion 기록 · AI 학습 코치")

if not sessions:
    st.warning("전사 파일이 없습니다. 먼저 study-session을 실행해줘.")
    st.stop()

selected_name = st.sidebar.selectbox(
    "세션 선택",
    options=[s["name"] for s in sessions],
    index=0,
)

selected = next(s for s in sessions if s["name"] == selected_name)
transcript_path = selected["transcript"]
summary_path = selected["summary"]

transcript_text = read_text(transcript_path)
summary_text = read_text(summary_path) if summary_path and summary_path.exists() else ""

history = st.session_state.chat_history_map.setdefault(selected_name, [])

with st.sidebar:
    st.markdown("### 빠른 실행")
    st.code(r'.\run_study_session_auto.ps1 -Title "LLM_강의"', language="powershell")
    st.write(f"전사 파일: `{transcript_path.name}`")
    st.write(f"요약 파일: `{summary_path.name if summary_path else '없음'}`")
    st.markdown("### 앱 한 줄 설명")
    st.info("강의 내용을 기록하고, 이해를 점검하고, 다음 학습 방향까지 추천하는 학습 도우미")

tab1, tab2, tab3 = st.tabs(["대시보드", "학습 도우미", "AI 학습 코치"])

with tab1:
    c1, c2, c3 = st.columns(3)
    c1.metric("전사 수", len(sessions))
    c2.metric("요약 존재", "예" if summary_path and summary_path.exists() else "아니오")
    c3.metric("현재 세션", selected_name)

    a1, a2 = st.columns(2)
    with a1:
        if st.button("이 세션 요약 생성/갱신", use_container_width=True):
            with st.status("요약 생성 중...", expanded=True):
                ok, out = run_cli(["summarize-file", str(transcript_path)])
                if ok:
                    st.success("요약 생성 완료")
                    st.code(out)
                    st.rerun()
                else:
                    st.error(out)

    with a2:
        if st.button("현재 summary를 Notion에 업로드", use_container_width=True, disabled=not (summary_path and summary_path.exists())):
            with st.status("Notion 업로드 중...", expanded=True):
                ok, out = run_notion_push(summary_path)
                if ok:
                    st.success("업로드 완료")
                    st.code(out)
                else:
                    st.error(out)

    st.markdown("### 요약")
    if summary_text:
        st.text_area("summary", summary_text, height=260, label_visibility="collapsed")
    else:
        st.info("요약 파일이 없어서 아직 표시할 내용이 없음")

    st.markdown("### 전사문")
    st.text_area("transcript", transcript_text, height=280, label_visibility="collapsed")

with tab2:
    st.markdown("### 질문 / 이해 점검")
    q1, q2, q3 = st.columns(3)

    quick_prompt = None
    if q1.button("핵심 3줄 요약", use_container_width=True):
        quick_prompt = "이 강의 핵심을 3줄로 요약해줘"
    if q2.button("내 이해 검증", use_container_width=True):
        quick_prompt = "내가 이해한게 이 강의는 핵심 개념을 설명하고 검증이 중요하다는 건데 맞아?"
    if q3.button("시험 포인트", use_container_width=True):
        quick_prompt = "이 강의에서 시험 전에 외워야 할 포인트 3개만 뽑아줘"

    for role, content in history:
        with st.chat_message(role):
            st.markdown(content)

    typed_prompt = st.chat_input("예: 내가 이해한게 LLM은 블랙박스라 출력 검증이 필요하다는 건데 맞아?")
    user_query = typed_prompt or quick_prompt

    if user_query:
        history.append(("user", user_query))
        with st.chat_message("user"):
            st.markdown(user_query)

        with st.chat_message("assistant"):
            with st.status("분석 중...", expanded=False):
                ok, out = run_cli(["ask", user_query, "--file", str(transcript_path)])
                if ok:
                    st.markdown(out)
                    history.append(("assistant", out))
                else:
                    st.error(out)
                    history.append(("assistant", f"오류:\n{out}"))

with tab3:
    st.markdown("### AI 학습 코치")
    st.caption("현재 강의 + 이전 강의 기록을 같이 보고 다음 학습 방향을 제안함")

    recommendations, keywords, questions = build_simple_recommendations(sessions)

    left, right = st.columns([1, 1])

    with left:
        st.markdown("#### 빠른 추천")
        for rec in recommendations:
            st.markdown(f"- {rec}")

        st.markdown("#### 반복 키워드")
        if keywords:
            st.write(", ".join(keywords))
        else:
            st.write("아직 키워드 부족")

    with right:
        st.markdown("#### 바로 물어볼 질문")
        for q in questions:
            st.code(q)

    if st.button("AI 학습 방향 분석", type="primary", use_container_width=True):
        with st.status("이전 기록까지 포함해 분석 중...", expanded=True):
            try:
                report = generate_learning_coach_report(
                    current_name=selected_name,
                    transcript_text=transcript_text,
                    summary_text=summary_text,
                )
                st.session_state.coach_reports[selected_name] = report
                st.success("분석 완료")
            except Exception as e:
                st.error(str(e))

    if selected_name in st.session_state.coach_reports:
        st.markdown(st.session_state.coach_reports[selected_name])
    else:
        st.info("버튼을 누르면 현재 강의와 이전 기록을 바탕으로 다음 학습 방향을 추천해줌")
