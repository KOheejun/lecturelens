import math
import re
from datetime import datetime

import typer
from rich import print
from langchain_openai import ChatOpenAI

from .config import UPSTAGE_API_KEY, OPENAI_BASE_URL, CHAT_MODEL, TRANSCRIPT_DIR, SUMMARY_DIR
from .summarizer import summarize_file
from .audio_capture import record_system_audio_chunk, save_wav
from .transcriber import LocalTranscriber, append_segments_jsonl, append_segments_txt
from .loader import load_transcript_txt
from .retriever import retrieve_relevant_chunks
from .chain import answer_question
from .course_memory import build_course_memory, build_next_direction

app = typer.Typer(help="LectureLens - 강의 전사 기반 학습 도우미 CLI")


def build_llm():
    if not UPSTAGE_API_KEY:
        print("[red]UPSTAGE_API_KEY가 비어 있습니다. .env 파일을 먼저 채워주세요.[/red]")
        raise typer.Exit(code=1)

    return ChatOpenAI(
        api_key=UPSTAGE_API_KEY,
        base_url=OPENAI_BASE_URL,
        model=CHAT_MODEL,
        temperature=0.2,
    )


def _latest_transcript_txt():
    txt_files = sorted(TRANSCRIPT_DIR.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not txt_files:
        print("[red]전사 txt 파일이 없습니다. 먼저 study-session 또는 record를 실행하세요.[/red]")
        raise typer.Exit(code=1)
    return txt_files[0]


def _sanitize_title(title: str) -> str:
    title = title.strip()
    if not title:
        return ""
    title = re.sub(r'[\\/:*?"<>|]+', "_", title)
    title = re.sub(r"\s+", "_", title)
    return title[:40]


def _make_session_id(title: str = "") -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = _sanitize_title(title)
    if safe_title:
        return f"{ts}_{safe_title}"
    return ts


def _run_record_live(
    chunk_seconds: int,
    model_size: str,
    language: str,
    title: str = "",
):
    if chunk_seconds <= 0:
        print("[red]chunk-seconds는 1 이상이어야 합니다.[/red]")
        raise typer.Exit(code=1)

    session_id = _make_session_id(title)
    jsonl_path = TRANSCRIPT_DIR / f"{session_id}.jsonl"
    txt_path = TRANSCRIPT_DIR / f"{session_id}.txt"

    transcriber = LocalTranscriber(model_size=model_size, device="cpu", compute_type="int8")

    print(f"[bold green]학습 세션 시작[/bold green] session_id={session_id}")
    print(f"[yellow]내부 전사 단위: {chunk_seconds}초[/yellow]")
    print("[yellow]강의를 재생한 뒤, 끝나면 Ctrl+C 로 종료하세요.[/yellow]")

    elapsed = 0.0
    chunk_index = 1

    try:
        while True:
            print(f"[bold]청크 {chunk_index} 녹음 중... ({chunk_seconds}초)[/bold]")

            audio = record_system_audio_chunk(chunk_seconds, sample_rate=16000)

            wav_path = TRANSCRIPT_DIR / f"{session_id}_chunk_{chunk_index:03d}.wav"
            save_wav(audio, wav_path, sample_rate=16000)

            print("[blue]전사 중...[/blue]")
            segments = transcriber.transcribe_wav(str(wav_path), language=language)
            adjusted = append_segments_jsonl(
                jsonl_path=jsonl_path,
                session_id=session_id,
                chunk_index=chunk_index,
                offset_seconds=elapsed,
                segments=segments,
            )
            append_segments_txt(txt_path, adjusted)

            if adjusted:
                for seg in adjusted:
                    print(f"[white]{seg['start_ts']} ~ {seg['end_ts']}[/white] {seg['text']}")
            else:
                print("[dim]이번 청크에서는 인식된 문장이 없었습니다.[/dim]")

            try:
                wav_path.unlink()
            except Exception:
                pass

            elapsed += chunk_seconds
            chunk_index += 1

    except KeyboardInterrupt:
        print("")
        print("[bold yellow]사용자 중단 감지 - 세션을 마무리합니다.[/bold yellow]")

    print(f"[green]전사 종료[/green]")
    print(f"[cyan]JSONL:[/cyan] {jsonl_path}")
    print(f"[cyan]TXT:[/cyan] {txt_path}")

    return txt_path, jsonl_path


def _run_ask(question: str, target: str, top_k: int):
    docs = load_transcript_txt(target)
    retrieved = retrieve_relevant_chunks(question, docs, top_k=top_k)

    print(f"[bold green]질문[/bold green] {question}")
    print(f"[bold cyan]대상 파일[/bold cyan] {target}")
    print("")

    print("[bold yellow]검색된 근거 구간[/bold yellow]")
    for i, doc in enumerate(retrieved, start=1):
        start_ts = doc.metadata.get("start_ts", "")
        end_ts = doc.metadata.get("end_ts", "")
        print(f"[{i}] {start_ts} ~ {end_ts}")
        print(f"    {doc.page_content}")

    print("")
    print("[bold magenta]답변[/bold magenta]")
    answer = answer_question(question, retrieved)
    print(answer)


@app.command()
def ping():
    llm = build_llm()
    resp = llm.invoke("한 줄로 '연결 성공'이라고만 답해줘.")
    print(f"[green]{resp.content}[/green]")


@app.command("study-session")
def study_session(
    chunk_seconds: int = typer.Option(10, help="내부 전사 단위(초)"),
    model_size: str = typer.Option("base", help="Whisper 모델 크기"),
    language: str = typer.Option("ko", help="전사 언어"),
    title: str = typer.Option("", help="세션 제목"),
):
    txt_path, _ = _run_record_live(
        chunk_seconds=chunk_seconds,
        model_size=model_size,
        language=language,
        title=title,
    )

    print("")
    print("[bold blue]자동 요약 생성 중...[/bold blue]")
    summary_path = summarize_file(str(txt_path))

    print(f"[bold green]학습 세션 완료[/bold green]")
    print(f"[cyan]전사 파일:[/cyan] {txt_path}")
    print(f"[cyan]요약 파일:[/cyan] {summary_path}")
    print("")
    print("[bold]바로 이어서 해볼 수 있는 질문 예시[/bold]")
    print('1) .\\.venv\\Scripts\\python.exe -m src.cli check-understanding "LLM은 블랙박스라서 결과를 그대로 믿기보다 검증이 필요하다는 뜻"')
    print('2) .\\.venv\\Scripts\\python.exe -m src.cli ask "이 강의 핵심이 뭐야?"')
    print('3) .\\.venv\\Scripts\\python.exe -m src.cli review-journey')
    print('4) .\\.venv\\Scripts\\python.exe -m src.cli next-direction')


@app.command("summarize-latest")
def summarize_latest():
    latest = _latest_transcript_txt()
    out_path = summarize_file(str(latest))
    print(f"[cyan]최신 전사 요약 완료:[/cyan] {out_path}")


@app.command()
def ask(
    question: str = typer.Argument(...),
    file_path: str = typer.Option("", "--file"),
    top_k: int = typer.Option(4),
):
    target = file_path if file_path else str(_latest_transcript_txt())
    _run_ask(question=question, target=target, top_k=top_k)


@app.command("check-understanding")
def check_understanding(
    statement: str = typer.Argument(...),
    file_path: str = typer.Option("", "--file"),
    top_k: int = typer.Option(4),
):
    target = file_path if file_path else str(_latest_transcript_txt())
    question = f"내가 이해한게 {statement}인데 맞아?"
    _run_ask(question=question, target=target, top_k=top_k)


@app.command("review-journey")
def review_journey(limit: int = typer.Option(20, help="반영할 최근 요약 수")):
    result = build_course_memory(limit=limit)
    print(result)


@app.command("next-direction")
def next_direction(limit: int = typer.Option(20, help="반영할 최근 요약 수")):
    result = build_next_direction(limit=limit)
    print(result)


@app.command()
def history(limit: int = typer.Option(10)):
    txt_files = sorted(TRANSCRIPT_DIR.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)

    if not txt_files:
        print("[red]저장된 세션이 없습니다.[/red]")
        raise typer.Exit(code=1)

    print("[bold green]최근 학습 세션[/bold green]")
    print("")

    for i, txt_path in enumerate(txt_files[:limit], start=1):
        stem = txt_path.stem
        summary_path = SUMMARY_DIR / f"{stem}_summary.md"
        summary_status = "있음" if summary_path.exists() else "없음"

        print(f"[{i}] 세션명: {stem}")
        print(f"    전사: {txt_path.name}")
        print(f"    요약: {summary_status}")
        print(f"    수정시각: {datetime.fromtimestamp(txt_path.stat().st_mtime)}")
        print("")


if __name__ == "__main__":
    app()
