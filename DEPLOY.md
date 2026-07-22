# Weave 배포 가이드 (Render)

친구도 쓸 수 있게 인터넷에 올리는 방법. **Render**(무료 티어)에 Docker + 관리형 Postgres로 배포한다.

> 핵심 흐름: **GitHub에 코드 올리기 → Render Blueprint로 배포 → OpenAI 키 넣기 → URL 공유**

---

## 1. GitHub 저장소에 올리기

Render는 GitHub 저장소에서 배포한다. (`.env`는 `.gitignore`에 있어 **비밀키는 커밋되지 않음**.)

```bash
cd C:/Users/lia.y.kwak/weave
git init
git add .
git commit -m "Weave 초기 커밋"
```

그다음 GitHub에서 **새 비어있는 저장소**(예: `weave`)를 만들고, 나온 주소로:

```bash
git branch -M main
git remote add origin https://github.com/<내아이디>/weave.git
git push -u origin main
```

> 커밋 전에 `git status`로 **`.env`가 목록에 없는지** 꼭 확인. (있으면 안 됨 → 비밀 노출)

---

## 2. Render에서 배포 (Blueprint)

1. https://render.com 가입 (GitHub로 로그인 추천)
2. **New +** → **Blueprint**
3. 방금 올린 저장소 선택 → Render가 `render.yaml`을 읽어 **Postgres + 웹 서비스**를 자동 구성
4. **Apply** 클릭
   - `weave-db` (Postgres)와 `weave` (웹) 두 개가 생성됨
   - `DATABASE_URL`, `SECRET_KEY`는 자동 주입/생성됨

> `plan: free` 가 막히면 대시보드에서 가장 저렴한 플랜을 골라도 됨.

---

## 3. OpenAI 키 넣기 (필수 — 회의 전사/AI 추출용)

1. Render → `weave` 웹 서비스 → **Environment** 탭
2. `OPENAI_API_KEY` 값에 네 OpenAI 키 입력 → **Save**
3. 자동으로 재배포됨

> 키가 없어도 앱은 뜨지만, 음성 회의 전사·요약·태그 추출은 동작하지 않음.

---

## 4. 확인 & 공유

- 배포가 끝나면 `https://weave-xxxx.onrender.com` 주소가 생김
- 열어서 **회원가입(이메일/비밀번호)** → 프로젝트 만들어보기
- 친구에게 그 URL 공유 → 친구도 **회원가입** → 프로젝트에서 **멤버 → 초대**(친구 이메일, 에디터/뷰어)

### 무료 티어 주의
- 15분 미사용 시 **잠들었다가**, 다음 접속 때 **첫 로딩이 30~60초** 걸림 (정상)
- 무료 Postgres는 기간 제한이 있을 수 있음 → 계속 쓸 거면 유료 전환

---

## 5. (선택) Google Drive / Google 로그인 켜기

기본은 **이메일/비밀번호**만으로 충분하다. Google 기능을 원하면:

1. Render `weave` 서비스 Environment에 추가:
   - `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
   - `GOOGLE_REDIRECT_URI` = `https://<네주소>.onrender.com/drive/callback`
   - `GOOGLE_AUTH_REDIRECT_URI` = `https://<네주소>.onrender.com/auth/google/callback`
2. Google Cloud Console → 해당 OAuth 클라이언트 → **승인된 리디렉션 URI**에 위 두 주소 추가
3. OAuth 동의 화면이 "테스트" 모드면 **친구를 테스트 사용자로 추가** (아니면 로그인 불가)

> 설정 안 하면 로그인 화면의 "Google로 계속하기" 버튼은 **자동으로 숨겨짐**.

---

## 안 되는 것 / 한계 (원격 배포 시)

- **옵시디언 검색**: 네 PC 로컬 볼트 폴더를 읽는 기능이라 클라우드에선 동작 안 함 (설정에 "미연결"로 뜸). 나머지 기능은 정상.
- **OpenAI 비용**: 회의 전사·AI 추출은 네 키로 과금됨. 친구가 많이 쓰면 비용 발생.

---

## 문제 해결

- **DB 연결 오류**: `DATABASE_URL` 끝에 `?sslmode=require` 를 붙여보기
- **502/첫 로딩 실패**: 무료 티어가 깨어나는 중 → 1분 뒤 새로고침
- **마이그레이션 오류**: 웹 서비스 **Logs** 탭에서 `alembic` 관련 메시지 확인
