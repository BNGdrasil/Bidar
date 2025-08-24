# Bidar (Bnbong + Vidar)

Authentication server of Bifrost(gateway server)

JWT 기반 인증 서버로, 마이크로서비스 아키텍처(MSA) 환경에서 사용자 인증을 담당하는 서비스입니다.

## 기능

- **JWT 토큰 기반 인증**: Access Token과 Refresh Token 지원
- **사용자 관리**: 회원가입, 로그인, 사용자 정보 조회/수정
- **보안**: 비밀번호 해싱, Rate Limiting, CORS 설정
- **데이터베이스**: PostgreSQL을 사용한 사용자 데이터 저장
- **캐싱**: Redis를 사용한 토큰 및 세션 관리
- **API 문서**: FastAPI 자동 생성 문서 (개발 환경)

## 기술 스택

- **Framework**: FastAPI
- **Database**: PostgreSQL
- **Cache**: Redis
- **Authentication**: JWT (python-jose)
- **Password Hashing**: bcrypt (passlib)
- **Testing**: pytest
- **Code Quality**: black, isort, flake8, mypy

## 사전 요구사항

- Python 3.9+
- uv (패키지 매니저)
- PostgreSQL
- Redis

## 빠른 시작

### 1. 환경 설정

```bash
# 저장소 클론
git clone git@github.com:BNGdrasil/Bidar.git
cd Bidar

# uv 설치 (아직 설치되지 않은 경우)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 의존성 설치 및 가상환경 생성
uv sync
```

### 2. 환경 변수 설정

```bash
# .env 파일 생성
cp env.example .env

# .env 파일에서 필요한 값들을 설정
# 특히 JWT_SECRET_KEY는 프로덕션에서 반드시 변경하세요!
```

### 3. 데이터베이스 설정

PostgreSQL과 Redis가 실행 중이어야 합니다. Docker를 사용하는 경우:

```bash
# PostgreSQL과 Redis 실행
docker run -d --name postgres -e POSTGRES_PASSWORD=password -e POSTGRES_DB=bnbong -p 5432:5432 postgres:15
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

### 4. 서버 실행

```bash
# 개발 모드로 실행
uv run python -m src.main

# 또는 스크립트 사용
./scripts/dev.sh
```

서버는 기본적으로 `http://localhost:8001`에서 실행됩니다.

## API 문서

개발 환경에서 다음 URL에서 API 문서를 확인할 수 있습니다:
- Swagger UI: `http://localhost:8001/docs`
- ReDoc: `http://localhost:8001/redoc`

## 주요 API 엔드포인트

### 인증 (Authentication)

- `POST /auth/register` - 회원가입
- `POST /auth/login` - 로그인
- `POST /auth/refresh` - 토큰 갱신
- `POST /auth/logout` - 로그아웃

### 사용자 관리 (Users)

- `GET /users/me` - 현재 사용자 정보 조회
- `PUT /users/me` - 사용자 정보 수정
- `DELETE /users/me` - 계정 삭제

### 헬스 체크

- `GET /health` - 서비스 상태 확인

## 테스트

```bash
# 모든 테스트 실행
uv run pytest

# 커버리지와 함께 테스트 실행
uv run pytest --cov=src

# 특정 테스트 파일 실행
uv run pytest tests/test_auth.py
```

## 개발 도구

### Pre-commit Hooks

코드 품질을 자동으로 관리하기 위해 pre-commit hooks를 사용합니다:

```bash
# pre-commit 설치 및 설정
uv run pre-commit install

# 모든 파일에 대해 pre-commit 실행
uv run pre-commit run --all-files

# 특정 hook만 실행
uv run pre-commit run black
uv run pre-commit run lint-scripts
```

### 수동 실행

```bash
# 코드 포맷팅
uv run black src tests
uv run isort src tests

# 린팅
uv run flake8 src tests
uv run mypy src

# 테스트 실행
uv run pytest

# 또는 스크립트 사용
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
```

## Docker

```bash
# Docker 이미지 빌드
docker build -t auth-server .

# Docker 컨테이너 실행
docker run -p 8001:8001 --env-file .env auth-server
```

## 보안 설정

프로덕션 환경에서는 다음 설정을 반드시 변경할 것:

1. **JWT_SECRET_KEY**: 강력한 비밀키로 변경
2. **ALLOWED_HOSTS**: 허용된 호스트만 설정
3. **ALLOWED_ORIGINS**: CORS 허용 도메인 설정
4. **DATABASE_URL**: 프로덕션 데이터베이스 연결 정보
5. **REDIS_URL**: 프로덕션 Redis 연결 정보

## 프로젝트 구조

```
auth-server/
├── src/
│   ├── core/           # 핵심 비즈니스 로직
│   │   ├── auth.py     # 인증 관련 로직
│   │   ├── users.py    # 사용자 관리 로직
│   │   └── database.py # 데이터베이스 설정
│   ├── models/         # 데이터 모델
│   │   └── user.py     # 사용자 모델
│   ├── utils/          # 유틸리티 함수
│   ├── config.py       # 설정 관리
│   └── main.py         # 애플리케이션 진입점
├── tests/              # 테스트 코드
├── scripts/            # 개발 스크립트
├── requirements.txt    # Python 의존성
├── pyproject.toml      # 프로젝트 설정
└── Dockerfile          # Docker 설정
```

## 라이선스

이 프로젝트는 개인 학습 및 개발 목적으로 사용됩니다.
