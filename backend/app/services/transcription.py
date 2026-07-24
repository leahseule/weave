import glob
import os
import shutil
import subprocess
import tempfile

from openai import OpenAI

from app.config import settings

# Whisper API 파일 상한은 25MB. 이 이하는 한 번에, 초과하면 ffmpeg로 조각내 전사.
DIRECT_LIMIT = 24 * 1024 * 1024      # 여유를 둬 24MB
UPLOAD_LIMIT = 300 * 1024 * 1024     # 안전상 최대 업로드 크기
CHUNK_SECONDS = 600                  # 조각 길이(10분)


class TranscriptionError(Exception):
    """전사 실패(키 미설정, 파일 초과, API 오류 등)를 라우터에 전달."""


def _fmt_ts(seconds: float) -> str:
    total = int(seconds or 0)
    return f"{total // 60:02d}:{total % 60:02d}"


def _seg_attr(seg, key, default=None):
    """세그먼트가 dict든 객체든 값을 꺼낸다."""
    if isinstance(seg, dict):
        return seg.get(key, default)
    return getattr(seg, key, default)


def _transcribe_bytes(filename: str, content: bytes, offset: int = 0) -> list[str]:
    """단일 오디오(≤25MB)를 Whisper로 전사. `[mm:ss] 텍스트` 줄 리스트 반환.

    offset(초)은 조각 전사 시 앞 조각들의 누적 시간(타임스탬프 보정).
    """
    client = OpenAI(api_key=settings.openai_api_key)
    resp = client.audio.transcriptions.create(
        model="whisper-1",
        file=(filename, content),
        response_format="verbose_json",
        temperature=0,
    )
    lines: list[str] = []
    segments = getattr(resp, "segments", None)
    if segments:
        for seg in segments:
            text = (_seg_attr(seg, "text", "") or "").strip()
            if not text:
                continue
            # 무음 구간의 환각("thank you for watching" 등) 필터
            if (_seg_attr(seg, "no_speech_prob", 0.0) or 0.0) > 0.6:
                continue
            start = (_seg_attr(seg, "start", 0) or 0) + offset
            lines.append(f"[{_fmt_ts(start)}] {text}")
    else:
        text = (getattr(resp, "text", "") or "").strip()
        if text:
            lines.append(f"[{_fmt_ts(offset)}] {text}")
    return lines


def _split_to_chunks(content: bytes, filename: str):
    """ffmpeg로 오디오를 10분 mp3(모노 16kHz 64k) 조각으로 분할. (tmpdir, [경로]) 반환."""
    tmpdir = tempfile.mkdtemp(prefix="weave_audio_")
    ext = os.path.splitext(filename or "")[1] or ".webm"
    src = os.path.join(tmpdir, "src" + ext)
    with open(src, "wb") as f:
        f.write(content)
    pattern = os.path.join(tmpdir, "chunk_%04d.mp3")
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", src,
        "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k",
        "-f", "segment", "-segment_time", str(CHUNK_SECONDS), pattern,
    ]
    try:
        subprocess.run(cmd, check=True, timeout=900)
    except FileNotFoundError as exc:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise TranscriptionError(
            "서버에 ffmpeg가 없어 긴 파일을 처리할 수 없어요."
        ) from exc
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise TranscriptionError("오디오 분할에 실패했어요.") from exc
    chunks = sorted(glob.glob(os.path.join(tmpdir, "chunk_*.mp3")))
    return tmpdir, chunks


def transcribe(filename: str, content: bytes) -> str:
    """오디오를 Whisper로 전사. 25MB 초과 시 조각내어 전사 후 이어붙인다.

    반환 형식: 세그먼트별 한 줄  `[mm:ss] 발화내용`
    """
    if not settings.openai_api_key:
        raise TranscriptionError(
            "OPENAI_API_KEY가 설정되지 않았습니다. weave/.env 에 키를 넣어주세요."
        )
    if len(content) > UPLOAD_LIMIT:
        raise TranscriptionError("파일이 너무 큽니다 (최대 300MB).")

    try:
        if len(content) <= DIRECT_LIMIT:
            lines = _transcribe_bytes(filename or "audio", content, offset=0)
        else:
            tmpdir, chunks = _split_to_chunks(content, filename)
            try:
                lines = []
                for i, path in enumerate(chunks):
                    with open(path, "rb") as f:
                        data = f.read()
                    lines += _transcribe_bytes(
                        os.path.basename(path), data, offset=i * CHUNK_SECONDS
                    )
            finally:
                shutil.rmtree(tmpdir, ignore_errors=True)
    except TranscriptionError:
        raise
    except Exception as exc:  # noqa: BLE001 — 외부 API 오류를 도메인 오류로 감쌈
        raise TranscriptionError(f"전사 API 호출 실패: {exc}") from exc

    result = "\n".join(lines).strip()
    if not result:
        raise TranscriptionError("음성이 감지되지 않았어요. 다시 녹음해 주세요.")
    return result
