# Weave — AWS EC2 배포 가이드 (docker-compose + 자동 HTTPS)

네가 만든 docker-compose를 **AWS EC2 서버에서 그대로 실행**하는 방식. 리눅스·SSH·Docker·HTTPS를 직접 겪어본다.

> 전체 흐름: **EC2 생성 → 방화벽 열기 → 도메인 연결 → SSH 접속 → Docker 설치 → clone → .env → 실행**

준비물: AWS 계정, (권장) 도메인 하나. 도메인이 없으면 무료 **DuckDNS**(`something.duckdns.org`)로 대체 가능.

---

## 1. EC2 인스턴스 생성

1. AWS 콘솔 → **EC2** → **Launch instance**
2. **이름**: `weave`
3. **AMI**: Ubuntu Server 24.04 LTS
4. **인스턴스 타입**: `t3.micro` (또는 `t2.micro`) — **프리티어 대상**
5. **키 페어**: 새로 생성 → `weave-key.pem` 다운로드 (SSH 열쇠, 잘 보관)
6. **네트워크 설정 (보안 그룹)**: 아래 인바운드 규칙 허용
   - SSH (22) — 소스: **내 IP** (보안상 권장)
   - HTTP (80) — 소스: Anywhere (0.0.0.0/0)
   - HTTPS (443) — 소스: Anywhere (0.0.0.0/0)
7. **스토리지**: 기본 8GB → **20GB** 정도로 늘리면 여유 있음
8. **Launch** → 인스턴스의 **퍼블릭 IP** 확인 (예: `13.125.x.x`)

---

## 2. 도메인 연결 (HTTPS에 필요)

HTTPS 인증서는 **도메인**에만 발급돼 (raw IP엔 안 됨).

- **도메인이 있으면**: DNS 관리에서 **A 레코드** 추가 → `weave` → `<EC2 퍼블릭 IP>`
- **없으면 (무료)**: https://www.duckdns.org 에서 `something.duckdns.org` 만들고 IP를 EC2 퍼블릭 IP로 지정

> DNS 전파에 몇 분 걸릴 수 있음. `nslookup 도메인` 으로 IP가 맞게 나오는지 확인.

---

## 3. SSH 접속

다운로드한 키가 있는 폴더에서 (Windows PowerShell):

```powershell
# 키 권한 정리(최초 1회) — 너무 열려있으면 SSH가 거부함
icacls weave-key.pem /inheritance:r
icacls weave-key.pem /grant:r "$($env:USERNAME):(R)"

ssh -i weave-key.pem ubuntu@<EC2-퍼블릭-IP>
```

처음이면 `yes` 입력. 이제 서버 안이다.

---

## 4. Docker 설치 (서버 안에서)

```bash
sudo apt update && sudo apt upgrade -y
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu     # sudo 없이 docker 쓰기
newgrp docker                      # 그룹 즉시 적용 (또는 재접속)
docker --version && docker compose version
```

---

## 5. 코드 가져오기 + 비밀값 설정

```bash
git clone https://github.com/leahseule/weave.git
cd weave

# 운영 .env 만들기 (템플릿 복사 후 편집)
cp .env.prod.example .env
nano .env
```

`.env`에서 채울 값:
- `POSTGRES_PASSWORD` — 강력한 비밀번호
- `SECRET_KEY` — 서버에서 `openssl rand -base64 48` 실행해 나온 값 붙여넣기
- `OPENAI_API_KEY` — 네 OpenAI 키
- `DOMAIN` — 2단계에서 연결한 도메인 (예: `weave.duckdns.org`)

`nano` 저장: `Ctrl+O` → `Enter` → `Ctrl+X`

---

## 6. 실행

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

- 처음엔 이미지 빌드로 몇 분 걸림
- Caddy가 도메인으로 **HTTPS 인증서를 자동 발급**함 (80/443 열려있고 DNS 맞으면 자동)

상태 확인:
```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f caddy   # 인증서 발급 로그
docker compose -f docker-compose.prod.yml logs -f api     # 앱 로그
```

이제 브라우저에서 **`https://네도메인`** → 회원가입 → 사용! 친구에게 이 주소 공유.

---

## 7. (선택) Google Drive / Google 로그인

`.env`에 추가:
```
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=https://네도메인/drive/callback
GOOGLE_AUTH_REDIRECT_URI=https://네도메인/auth/google/callback
```
그리고 Google Cloud Console → OAuth 클라이언트 → **승인된 리디렉션 URI**에 위 두 개 추가. 저장 후:
```bash
docker compose -f docker-compose.prod.yml up -d
```

---

## 운영 팁

**업데이트 (코드 바뀌면)**
```bash
cd weave && git pull
docker compose -f docker-compose.prod.yml up -d --build
```

**DB 백업**
```bash
docker compose -f docker-compose.prod.yml exec db pg_dump -U weave weave > backup_$(date +%F).sql
```

**중지 / 재시작**
```bash
docker compose -f docker-compose.prod.yml down      # 중지 (데이터 볼륨은 유지)
docker compose -f docker-compose.prod.yml up -d     # 재시작
```

---

## 한계 / 주의

- **옵시디언 검색**: 로컬 볼트를 읽는 기능이라 서버에선 동작 안 함 (나머지는 정상)
- **비용**: t3.micro는 프리티어 12개월 무료, 이후 ~월 $8. 안 쓸 땐 인스턴스 **중지**(stop)하면 과금 절감 (단 퍼블릭 IP는 바뀔 수 있음 → 고정하려면 Elastic IP)
- **보안**: SSH 22는 내 IP만 열기, 시스템 업데이트(`apt upgrade`) 가끔 해주기
- **AWS 예산 알림**: Billing → Budgets 에서 알림 설정 추천

---

## 도메인 없이 빠른 데모만 하려면? (http, 비권장)

HTTPS 없이 IP로만 잠깐 보여줄 거면:
1. `docker-compose.prod.yml`에서 `caddy` 서비스를 지우고, `api`에 `ports: ["80:8000"]` 추가
2. `api` 환경변수 `SESSION_HTTPS_ONLY: "false"` 로 변경
3. `http://<EC2-IP>` 로 접속

> 로그인 쿠키가 암호화 안 된 채 오가므로 **친구 몇 명 잠깐 데모**만. 계속 쓸 거면 도메인+HTTPS로.
