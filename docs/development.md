# 로컬 개발

로컬 환경에서 Bidar를 실행하고 테스트와 린트를 수행하며 Docker 이미지를 빌드하는 방법을 설명하는 문서입니다.

## 실행과 테스트

```bash
# 의존성 설치
uv sync

# 개발 서버 실행 (env.example을 .env로 복사한 뒤)
./scripts/dev.sh

# 테스트 실행: 데이터베이스와 JWT 키 등 필요한 환경 변수를 스크립트가 직접 지정하므로
# 로컬 셸이나 .env에 남아 있는 값의 영향을 받지 않습니다
./scripts/test.sh

# 포매팅과 린트
./scripts/lint.sh
```

`scripts/format.sh`는 black과 isort를 실행해 코드 형식만 정리합니다. 린트 검사는 black과 isort, flake8, mypy를 함께 수행합니다.

환경 변수를 준비하는 방법은 [환경 변수 문서](configuration.md)를 참고하십시오.

## Docker 빌드

```bash
docker build -t bidar .
```

Docker 이미지는 `uv.lock`에서 내보낸 `requirements.txt`를 기준으로 런타임 의존성만 설치하며, uid 10001의 비root 사용자로 실행됩니다. CI는 이미지가 빌드 시점의 lock 파일과 어긋나지 않도록 `requirements.txt`와 `uv.lock`의 일치 여부를 검사합니다.

## CI가 수행하는 검사

`.github/workflows/ci.yml`은 다음 세 가지 job을 실행합니다.

- `test`: Python 3.12와 3.13 행렬에서 pytest를 실행합니다.
- `lint`: black, isort, flake8, mypy를 실행합니다.
- `security`: bandit, pip-audit을 실행하고 requirements 동기화 여부를 확인합니다.

배포 파이프라인과 CI의 연동 방식은 [운영 가이드](operations.md)에 정리되어 있습니다.
