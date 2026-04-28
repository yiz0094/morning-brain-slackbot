# 모닝 브레인 (Morning Brain)

평일 아침 9시 KST에 슬랙 채널에 10분 뇌 운동을 포스트하고, 답변에 Claude로 피드백을 주고, 노션 Tasks DB에 자동 기록하는 개인용 슬랙봇.

## 운동 사이클

- **월~목**: 6개 풀에서 4일 단위 순환 — 마케팅 숫자, 영문 요약, 전략 케이스, 기억력, 자유 쓰기, 비즈니스 영단어
- **금**: 그 주 월~목 기록을 컨텍스트로 회고 질문
- **토/일**: 트리거 X (단, 미완료 평일 세션 답글은 처리)

3주마다 패턴이 한 바퀴.

## 본인(Yiz)이 직접 해야 할 셋업

### 1. 노션 Integration 만들기
1. https://notion.so/profile/integrations → **New integration**
2. 이름: `morning-brain-bot`, 워크스페이스: 본인 것
3. Capabilities: Read content, Update content, Insert content
4. **Internal Integration Secret** 복사 → `NOTION_TOKEN`

### 2. 노션 페이지 연결
1. **매일 아침 뇌훈련** 페이지 열기 (https://www.notion.so/350bffe38d5780f6b9b3d1ddd106c42d)
2. 우상단 ··· → **Connect to** → `morning-brain-bot` 선택
3. **자기계발** 박스 페이지에도 같은 방식으로 connect
4. Tasks DB는 같은 워크스페이스라 자동 접근

### 3. 슬랙 앱 등록
1. https://api.slack.com/apps → **Create New App** → **From an app manifest**
2. 워크스페이스: **이즈 개인채널** 선택
3. 저장소의 `slack_manifest.yaml` 내용 붙여넣기 → Create
4. **OAuth & Permissions** → **Install to Workspace** → 승인
5. **Bot User OAuth Token** 복사 (`xoxb-...`) → `SLACK_BOT_TOKEN`
6. **Basic Information** → **Signing Secret** 복사 → `SLACK_SIGNING_SECRET`

### 4. 채널 만들고 봇 초대
1. 슬랙에서 `#매일아침-뇌훈련` 채널 생성 (private 권장)
2. 채널에서 `/invite @모닝 브레인`
3. 채널 이름 클릭 → 맨 아래 **Channel ID** 복사 → `BRAIN_CHANNEL_ID`
4. 본인 프로필 → ··· **More** → **Copy member ID** → `OWNER_USER_ID`

### 5. Anthropic API 키
1. https://console.anthropic.com/ → API Keys → Create Key
2. 복사 → `ANTHROPIC_API_KEY`

### 6. Railway 배포
1. https://railway.app → GitHub 로그인
2. **New Project** → **Deploy from GitHub repo** → 이 저장소 선택
3. **Variables** 탭에 `.env.example`의 9개 환경변수 입력
4. **Settings** → **Public Networking** → **Generate Domain**
5. 슬랙 앱의 **Event Subscriptions** URL 등록:
   - Request URL: `https://<railway-domain>/slack/events`
   - Subscribe to bot events: `message.channels` (private 채널이면 `message.groups`도)
6. 슬래시 커맨드 4개 URL을 모두 `https://<railway-domain>/slack/commands`로 수정
   (`slack_manifest.yaml`의 `YOUR-RAILWAY-DOMAIN` placeholder 치환 후 manifest 재import)
7. 슬랙 앱 재설치 (권한 변경 후)

### 7. 첫 실행 확인
- Railway 로그에 `Scheduler started, jobs: ...` 떠야 함
- `/brain-now`로 즉시 한 번 트리거 → 슬랙 메시지 + 노션 Task 둘 다 생성 확인
- 노션 Task에서 박스/프로젝트 relation 채워졌는지 확인
- 슬랙 스레드에 답글 → 피드백 받고 노션 페이지 본문 업데이트 확인

## 로컬 개발

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # 값 채우기
python -m pytest tests/  # 테스트
uvicorn app.main:app --reload --port 3000
```

Slack Event Request URL은 ngrok 등 터널 필요.

## 슬래시 커맨드

| 커맨드 | 동작 |
|---|---|
| `/brain-skip` | 오늘 운동 건너뛰기 |
| `/brain-streak` | 연속 평일 일수 + 최근 14평일 기록 |
| `/brain-history [type]` | 최근 5개 노션 링크 (type 옵션) |
| `/brain-now` | 즉시 새 운동 트리거 (테스트용, cap 우회) |

## 디렉토리

```
.
├── app/                  # 애플리케이션 코드
│   ├── main.py           # FastAPI + Bolt + scheduler 통합 진입점
│   ├── scheduler.py      # 평일 09:00, 12:00, 일 23:00 cron
│   ├── slack_handlers.py # 메시지/슬래시 커맨드
│   ├── exercises.py      # 운동 콘텐츠 생성 + 피드백
│   ├── rotation.py       # 요일 → 운동 타입 결정
│   ├── claude_client.py  # Anthropic 래퍼
│   ├── notion_client.py  # Notion 래퍼
│   ├── storage.py        # SQLite (sessions + meta + sync 큐)
│   ├── models.py         # Session, ExerciseType
│   └── config.py         # 환경변수
├── prompts/              # 운동 YAML 7개
├── tests/
├── requirements.txt
├── slack_manifest.yaml
├── Procfile
├── railway.json
└── .env.example
```
