# LectureLens

강의를 실시간으로 전사하고, 질문에 답하고, 복습 자료까지 자동 생성하는 개인 학습 도우미.

## 주요 기능

- **실시간 전사** — 시스템 오디오를 10초 단위로 캡처해 faster-whisper로 타임스탬프 포함 전사
- **강의 Q&A** — 전사 내용 기반 커스텀 검색 + Upstage Solar Pro 2로 근거 구간 포함 답변
- **자동 요약** — 강의 전체를 청크 단위로 요약 후 최종 정리 (2-pass)
- **Study Pack 생성** — 핵심 개념·복습 질문·오개념 로그 자동 생성
- **Notion 연동** — 요약 결과를 Notion 데이터베이스에 자동 업로드
- **AI 학습 코치** — 여러 세션 기록을 종합해 다음 학습 방향 제안

## 기술 스택

| 구분 | 내용 |
|------|------|
| LLM | Upstage Solar Pro 2 (`solar-pro2`) |
| STT | faster-whisper (Whisper base, CPU) |
| 오디오 캡처 | soundcard (Windows 시스템 오디오 루프백) |
| 검색 | 커스텀 토큰 오버랩 기반 검색 (벡터 DB 미사용) |
| UI | Streamlit (3탭) |
| CLI | Typer + Rich |
| 외부 연동 | Notion API |

## 설치

> **Windows 전용** — 오디오 캡처가 Windows 루프백 방식을 사용합니다.

```powershell
# 1. 가상환경 생성 및 활성화
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. 패키지 설치
pip install -r requirements.txt

# 3. 환경 변수 설정
cp .env.example .env
# .env 파일을 열고 API 키 입력
```

**필요한 API 키:**
- `UPSTAGE_API_KEY` — [Upstage Console](https://console.upstage.ai) 에서 발급
- `NOTION_API_KEY`, `NOTION_DATABASE_ID` — [Notion Integrations](https://www.notion.so/my-integrations) 에서 발급 (선택)

## 사용법

### Streamlit 웹앱

```powershell
.\run_webapp.ps1
```

### 강의 자동 기록 (전사 → Notion 업로드 → Study Pack)

```powershell
.\run_study_session_auto.ps1 -Title "강의명"
```

### CLI 직접 사용

```powershell
# 강의 실시간 녹음 및 전사
python -m src.cli study-session --title "강의명"

# 질문
python -m src.cli ask "어텐션 메커니즘이 뭐야?" --file data/transcripts/강의명.txt

# 최신 전사 요약
python -m src.cli summarize-latest

# 전체 학습 이력 조회
python -m src.cli history
```

## 프로젝트 구조

```
lecturelens/
├── src/
│   ├── config.py          # 환경변수 로딩
│   ├── audio_capture.py   # 시스템 오디오 캡처
│   ├── transcriber.py     # faster-whisper 전사
│   ├── loader.py          # 전사 파일 파싱
│   ├── retriever.py       # 커스텀 키워드 검색
│   ├── chain.py           # LLM Q&A 체인
│   ├── summarizer.py      # 2-pass 요약
│   ├── study_pack.py      # Study Pack 생성
│   ├── coach.py           # AI 학습 코치
│   ├── course_memory.py   # 세션 간 누적 기억
│   ├── notion_push.py     # Notion 업로드
│   ├── webapp.py          # Streamlit UI
│   └── cli.py             # CLI 엔트리포인트
├── data/
│   └── transcripts/
│       └── sample.txt     # 전사 형식 예시
├── .env.example
├── requirements.txt
├── run_webapp.ps1
└── run_study_session_auto.ps1
```

## 답변 형식

강의 내용 관련 질문에 대해 아래 4가지 구조로 답변합니다.

1. **판정** — 강의에서 다룬 내용인지 여부
2. **근거 구간** — 관련 전사 구간의 타임스탬프 (`HH:MM:SS ~ HH:MM:SS`)
3. **보정 설명** — 전사 오류나 맥락 보완
4. **한 줄 암기 포인트** — 핵심 내용 요약

## 한계

- Windows 전용 (soundcard 루프백 의존)
- 로컬 실행 전용 (클라우드 배포 미지원)
- 검색이 키워드 기반이라 의미론적 유사어에 취약
