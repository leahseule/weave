# Weave

회의를 프로젝트 단위로 쌓고, 관련 문서(Google Drive)를 붙여, 프로젝트 히스토리를 한눈에 파악하는 웹앱.

전체 제품 정의는 [PRD](../Weave_PRD.md) 참고.

## 스택
- FastAPI (Python)
- Postgres
- Docker / docker-compose

## 실행 (P0)

```bash
cp .env.example .env      # 필요시 값 수정
docker compose up --build
```

- API: http://localhost:8000
- 문서(Swagger): http://localhost:8000/docs
- 헬스체크: http://localhost:8000/health  →  `{"status":"ok","db":true}`

`db: true` 면 API가 Postgres까지 정상 연결된 상태.

## 구조

```
weave/
├── docker-compose.yml     # api + db 서비스
├── .env.example
└── backend/
    ├── Dockerfile
    ├── requirements.txt
    ├── alembic.ini        # 마이그레이션 설정
    ├── alembic/           # 마이그레이션 스크립트
    ├── app/
    │   ├── main.py        # FastAPI 앱, /health, 프론트 서빙
    │   ├── config.py      # 환경변수 설정
    │   ├── db.py          # SQLAlchemy 엔진 + 세션 + 헬스체크
    │   ├── models.py      # 테이블 정의 (PRD §8)
    │   ├── schemas.py     # 요청/응답 스키마
    │   ├── routers/       # projects · sources · meetings · curation
    │   └── services/      # transcription(Whisper) · extraction(GPT)
    └── frontend/          # 바닐라 반응형 UI (index.html · app.js · styles.css)
```

## 화면

http://localhost:8000 접속. 홈(프로젝트 목록) → 프로젝트 상세(좌: 타임라인 / 우:
Context 패널). 회의 추가(붙여넣기·음성), 결정 수락, 액션아이템 체크가 모두 UI에서 동작.

## API (P1)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/projects` | 프로젝트 생성 (목표는 선택) |
| GET | `/projects` | 목록 + 회의/문서 개수 집계 |
| GET | `/projects/{id}` | 상세 = 타임라인(sources) + Context |
| PATCH | `/projects/{id}` | 이름/목표 수정 |
| DELETE | `/projects/{id}` | 삭제 (하위 소스까지 cascade) |
| GET | `/projects/{id}/sources` | 타임라인 조회 |
| POST | `/projects/{id}/sources` | 소스 추가 (MEETING/DOCUMENT) |
| DELETE | `/sources/{id}` | 소스 삭제 |
| POST | `/projects/{id}/meetings/paste` | 메모(md) 붙여넣기 → 회의 (전사 불필요) |
| POST | `/projects/{id}/meetings/audio` | 음성 업로드 → Whisper 전사 → 회의 |
| POST | `/projects/{id}/context-items` | Context 항목 직접 추가 |
| PATCH | `/context-items/{id}` | 수락(accepted)/내용 수정 |
| DELETE | `/context-items/{id}` | 제안 거절/삭제 |
| POST | `/sources/{id}/action-items` | 액션아이템 직접 추가 |
| PATCH | `/action-items/{id}` | 체크/내용/마감일(due_date) 수정 |
| DELETE | `/action-items/{id}` | 액션아이템 삭제 |
| GET | `/calendar` | 마감일 지정된 액션아이템 (캘린더용) |

회의를 저장하면(붙여넣기·음성 모두) **자동으로** 요약·액션아이템·키워드·결정(→Context에
proposed 제안)·목표(첫 회의)가 추출된다. 결정은 `PATCH /context-items`로 수락한다.

http://localhost:8000/docs 에서 바로 호출해볼 수 있다.

## 환경변수

음성 전사를 쓰려면 `weave/.env` 에 OpenAI 키가 필요하다 (`.env.example` 참고):

```
OPENAI_API_KEY=sk-...
```

넣은 뒤 `docker compose up -d` 로 컨테이너에 반영. 키가 없으면 음성 경로만
비활성(400 안내)되고 나머지는 정상 동작한다.

## DB 마이그레이션 (Alembic)

컨테이너 기동 시 `alembic upgrade head`가 자동 실행된다.
모델(`app/models.py`)을 바꿨다면:

```bash
docker compose exec api alembic revision --autogenerate -m "설명"
docker compose exec api alembic upgrade head
```

## 마일스톤
- **P0** — docker-compose로 FastAPI + Postgres 기동, `/health` ✅
- **P1** — 데이터 모델 + 프로젝트/타임라인 CRUD ✅
- **P2** — 회의 입력(녹음/업로드/붙여넣기) → Whisper 전사 ✅
- **P3** — 회의 저장 시 자동 LLM 추출(요약·액션·키워드·결정·목표) + Context 큐레이션 ✅
- **P5** — 반응형 웹 UI (홈·프로젝트 상세·회의 추가·큐레이션), FastAPI가 서빙 ✅ (현재)
- **P4** — Google Drive 연결 + 키워드 검색 추천 (다음)
- P2 — 회의 입력(녹음/업로드/붙여넣기) → 전사
- P3 — LLM 추출 → Context 제안·큐레이션
- P4 — Google Drive 연결 + 키워드 검색 추천·pin
- P5 — 반응형 화면 + README/데모
