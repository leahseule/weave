from openai import OpenAI

from app.config import settings

# Whisper API 파일 크기 상한 (PRD: MVP는 짧은 녹음만 지원)
MAX_AUDIO_BYTES = 25 * 1024 * 1024


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


def transcribe(filename: str, content: bytes) -> str:
    """오디오를 Whisper로 전사. 타임스탬프 세그먼트를 줄바꿈해 가독성 확보.

    반환 형식: 세그먼트별 한 줄  `[mm:ss] 발화내용`
    (화자 분리는 Whisper API 미지원 — timestamps로 가독성만 개선)
    """
    if not settings.openai_api_key:
        raise TranscriptionError(
            "OPENAI_API_KEY가 설정되지 않았습니다. weave/.env 에 키를 넣어주세요."
        )
    if len(content) > MAX_AUDIO_BYTES:
        raise TranscriptionError(
            "오디오가 25MB를 초과했습니다. MVP는 짧은 녹음만 지원합니다."
        )

    client = OpenAI(api_key=settings.openai_api_key)
    try:
        resp = client.audio.transcriptions.create(
            model="whisper-1",
            file=(filename, content),
            response_format="verbose_json",
            temperature=0,
        )
    except Exception as exc:  # noqa: BLE001 — 외부 API 오류를 도메인 오류로 감쌈
        raise TranscriptionError(f"전사 API 호출 실패: {exc}") from exc

    segments = getattr(resp, "segments", None)
    if segments:
        lines = []
        for seg in segments:
            text = (_seg_attr(seg, "text", "") or "").strip()
            if not text:
                continue
            # 무음 구간의 환각("thank you for watching" 등) 필터
            if (_seg_attr(seg, "no_speech_prob", 0.0) or 0.0) > 0.6:
                continue
            lines.append(f"[{_fmt_ts(_seg_attr(seg, 'start', 0))}] {text}")
        result = "\n".join(lines)
        if result.strip():
            return result
        raise TranscriptionError("음성이 감지되지 않았어요. 다시 녹음해 주세요.")

    text = (getattr(resp, "text", "") or "").strip()
    if not text:
        raise TranscriptionError("음성이 감지되지 않았어요. 다시 녹음해 주세요.")
    return text
