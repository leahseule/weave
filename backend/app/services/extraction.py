import json

from openai import OpenAI

from app.config import settings

MODEL = "gpt-4o-mini"

_SYSTEM = (
    "너는 회의록과 개인 메모를 분석해 구조화된 정보를 추출하는 도우미다. "
    "반드시 한국어로, 지정된 키를 가진 JSON 하나만 출력한다."
)


class ExtractionError(Exception):
    """추출 실패(키 미설정, API 오류, 파싱 실패 등)."""


def _meeting_instructions(body: str, objective_line: str) -> str:
    return (
        "다음 회의 내용을 분석해 아래 키를 가진 JSON으로만 답해줘.\n"
        "- title: 회의를 대표하는 짧은 제목 (한 줄, 20자 내외)\n"
        "- summary: 회의에서 논의된 핵심을 2~3문장으로 요약\n"
        "- action_items: 회의에서 나온 할 일·후속 조치·담당자가 맡기로 한 것·다음 단계를 "
        "빠짐없이 뽑은 문자열 배열. 담당자가 있으면 \"담당자: 할 일\" 형식. "
        "실행이 필요한 항목을 놓치지 말 것. 정말 없으면 []\n"
        "- keywords: 이 내용을 대표하는 구체적·고유한 핵심 주제나 고유명사"
        "(제품·프로젝트·기술·조직·사람 이름 등)만 3~5개. "
        "'회의/논의/자료/진행/계획/방안/내용/미팅/공유' 같은 일반적이거나 뻔한 단어는 "
        "절대 넣지 말 것. 의미있는 게 없으면 적게 넣거나 []\n"
        "- decisions: 회의에서 내려진 의사결정 문자열 배열 (없으면 [])\n"
        f"{objective_line}"
        "\n회의 내용:\n"
        f"{body}"
    )


def _note_instructions(body: str, objective_line: str) -> str:
    return (
        "다음은 사용자가 직접 작성한 메모다. 회의록이 아니라 개인 메모임을 감안해 "
        "아래 키를 가진 JSON으로만 답해줘.\n"
        "- title: 메모 내용을 대표하는 짧은 제목 (한 줄, 20자 내외)\n"
        "- summary: 메모의 핵심을 1~2문장으로 간결히 요약 (회의 요약처럼 격식 차리지 말 것)\n"
        "- action_items: 메모에 적힌 할 일·챙길 것을 문자열 배열로. "
        "작성자 본인의 메모이므로 담당자 표기는 하지 말 것. 없으면 []\n"
        "- keywords: 이 내용을 대표하는 구체적·고유한 핵심 주제나 고유명사"
        "(제품·프로젝트·기술·조직·사람 이름 등)만 3~5개. "
        "'회의/논의/자료/진행/계획/방안/내용/미팅/공유' 같은 일반적이거나 뻔한 단어는 "
        "절대 넣지 말 것. 의미있는 게 없으면 적게 넣거나 []\n"
        "- decisions: 메모에 명시된 결정·방침이 있으면 문자열 배열 (없으면 []). 억지로 만들지 말 것\n"
        f"{objective_line}"
        "\n메모 내용:\n"
        f"{body}"
    )


def extract_meeting(body: str, needs_objective: bool, kind: str = "meeting") -> dict:
    """회의/메모 본문에서 요약/액션아이템/키워드/결정(+목표)을 추출한다.

    kind="note"면 개인 메모 전용 프롬프트, 그 외엔 회의 프롬프트를 사용한다.
    """
    if not settings.openai_api_key:
        raise ExtractionError("OPENAI_API_KEY 미설정")

    is_note = kind == "note"
    label = "메모" if is_note else "회의"
    objective_line = (
        f"- objective: 이 {label}로 유추되는 프로젝트의 목표 한 문장\n"
        if needs_objective
        else ""
    )
    instructions = (
        _note_instructions(body, objective_line)
        if is_note
        else _meeting_instructions(body, objective_line)
    )

    client = OpenAI(api_key=settings.openai_api_key)
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": instructions},
            ],
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as exc:  # noqa: BLE001
        raise ExtractionError(f"추출 실패: {exc}") from exc
