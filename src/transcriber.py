from pathlib import Path
from typing import List, Dict
from faster_whisper import WhisperModel
import json


def format_ts(seconds: float) -> str:
    total_ms = int(seconds * 1000)
    ms = total_ms % 1000
    total_sec = total_ms // 1000
    s = total_sec % 60
    total_min = total_sec // 60
    m = total_min % 60
    h = total_min // 60
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


class LocalTranscriber:
    def __init__(self, model_size: str = "base", device: str = "cpu", compute_type: str = "int8"):
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe_wav(self, wav_path: str, language: str = "ko") -> List[Dict]:
        segments, info = self.model.transcribe(
            wav_path,
            language=language,
            vad_filter=True,
            beam_size=1,
        )

        rows = []
        for seg in segments:
            text = seg.text.strip()
            if not text:
                continue
            rows.append(
                {
                    "start": float(seg.start),
                    "end": float(seg.end),
                    "text": text,
                }
            )
        return rows


def append_segments_jsonl(
    jsonl_path: Path,
    session_id: str,
    chunk_index: int,
    offset_seconds: float,
    segments: List[Dict],
) -> List[Dict]:
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)

    adjusted = []
    with jsonl_path.open("a", encoding="utf-8") as f:
        for seg in segments:
            row = {
                "session_id": session_id,
                "chunk_index": chunk_index,
                "start": round(offset_seconds + seg["start"], 3),
                "end": round(offset_seconds + seg["end"], 3),
                "start_ts": format_ts(offset_seconds + seg["start"]),
                "end_ts": format_ts(offset_seconds + seg["end"]),
                "text": seg["text"],
            }
            adjusted.append(row)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return adjusted


def append_segments_txt(txt_path: Path, adjusted_segments: List[Dict]) -> None:
    txt_path.parent.mkdir(parents=True, exist_ok=True)

    with txt_path.open("a", encoding="utf-8-sig") as f:
        for seg in adjusted_segments:
            f.write(f"[{seg['start_ts']} ~ {seg['end_ts']}] {seg['text']}\n")

