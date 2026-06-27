from pathlib import Path
import wave
import numpy as np
import soundcard as sc


def record_system_audio_chunk(seconds: float, sample_rate: int = 16000) -> np.ndarray:
    speaker = sc.default_speaker()
    if speaker is None:
        raise RuntimeError("기본 스피커를 찾지 못했습니다.")

    mic = sc.get_microphone(id=str(speaker.name), include_loopback=True)
    if mic is None:
        raise RuntimeError("루프백 마이크를 찾지 못했습니다.")

    numframes = int(seconds * sample_rate)

    with mic.recorder(samplerate=sample_rate) as recorder:
        audio = recorder.record(numframes=numframes)

    if audio.ndim == 2:
        audio = audio.mean(axis=1)

    audio = np.clip(audio, -1.0, 1.0).astype(np.float32)
    return audio


def save_wav(audio: np.ndarray, wav_path: Path, sample_rate: int = 16000) -> None:
    wav_path.parent.mkdir(parents=True, exist_ok=True)

    pcm16 = (audio * 32767.0).astype(np.int16)

    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm16.tobytes())
