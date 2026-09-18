# Bidar

Bidar는 BNGdrasil 생태계의 인증 서버입니다. 사용자 계정과 역할(role)의 원본 데이터를 데이터베이스에 보관하고, JWT 기반 로그인·토큰 갱신·사용자 관리 API를 제공합니다. 게이트웨이 역할을 맡는 **Bifrost**는 요청마다 Bidar의 `/rbac/verify-permission`을 호출해 호출자의 권한을 위임 확인하며, 자체적으로 역할 판단을 내리지 않습니다.

이 문서는 현재 코드 기준으로 작성되었으며, 미구현 기능이나 계획 단계의 항목은 "알려진 제한과 후속 과제" 절에 별도로 표시합니다.

## API 목록

공개 회원가입 엔드포인트는 존재하지 않습니다. 계정은 `super_admin` 권한을 가진 사용자가 `POST /users`로 생성하거나, `python -m src.cli create-admin` CLI로만 생성할 수 있습니다.

| 메서드 · 경로 | 설명 | 필요 권한 | 주요 상태 코드 |
|---|---|---|---|
| `POST /auth/token` | OAuth2 호환 폼 로그인. 로그인 시도는 IP당 분당 요청 수로 제한됩니다 | 없음 | 401(자격 증명 오류·비활성 계정), 429(요청 과다) |
| `POST /auth/refresh` | refresh 토큰으로 access 토큰을 재발급합니다. refresh 토큰만 받아들이며 access 토큰을 넣으면 거절됩니다 | refresh 토큰 | 401(토큰 종류 불일치·만료·비활성 계정) |
| `GET /auth/me` | 현재 로그인한 사용자 정보를 반환합니다 | access 토큰 | 401 |
| `POST /users` | 사용자를 생성합니다 | super_admin | 400(아이디·이메일 중복), 401, 403, 422 |
| `GET /users/users` | 전체 사용자 목록을 조회합니다 | admin 이상 | 401, 403 |
| `GET /users/users/{id}` | 단일 사용자를 조회합니다 | admin 이상 | 401, 403, 404 |
| `PATCH /users/users/{id}` | 사용자의 프로필·역할·활성 상태를 수정합니다 | super_admin | 401, 403, 404, 409(마지막 활성 super_admin 보호), 422 |
| `DELETE /users/users/{id}` | 사용자를 삭제합니다 | super_admin | 400(자기 자신 삭제 시도), 401, 403, 404, 409(마지막 활성 super_admin 보호) |
| `PUT /users/users/{id}/activate` | 사용자를 활성화합니다 | admin 이상(대상이 admin 이상이면 super_admin) | 401, 403, 404 |
| `PUT /users/users/{id}/deactivate` | 사용자를 비활성화합니다 | admin 이상(대상이 admin 이상이면 super_admin) | 400(자기 자신 비활성화 시도), 401, 403, 404, 409(마지막 활성 super_admin 보호) |
| `POST /rbac/verify-permission` | Bearer 토큰과 요구 역할을 받아 DB의 현재 역할·활성 상태로 권한을 확인합니다. Bifrost가 위임 확인용으로 호출합니다 | access 토큰 | 401, 403 |
| `GET /rbac/my-role` | 현재 로그인한 사용자의 역할 정보를 반환합니다 | access 토큰 | 401 |
| `GET /health` | 서비스 상태 확인용 헬스체크입니다 | 없음 | 200 |
| `GET /metrics` | Prometheus 형식의 메트릭을 노출합니다 | 없음 | 200 |

## 역할 계층과 권한 경계

역할은 `user < moderator < admin < super_admin` 순서의 단일 계층으로 정의되어 있으며(`src/core/roles.py`), 상위 역할은 하위 역할이 요구하는 모든 권한을 자동으로 만족합니다. `User.is_superuser` 컬럼은 하위 호환을 위해 남아 있는 파생값으로, `role`이 `super_admin`일 때만 참이 되도록 생성·수정 시점에 서버가 항상 다시 계산합니다. 클라이언트가 보낸 `is_superuser` 값은 무시됩니다.

권한 경계는 다음과 같이 나뉩니다.

- `admin`은 사용자 조회와 활성화/비활성화를 수행할 수 있지만, 대상 계정의 역할이 `admin` 이상이면 거절됩니다. 이는 admin이 자신과 동급이거나 상위인 계정을 건드려서 권한을 탈취하는 경로를 막기 위한 조치입니다.
- 사용자 생성, 역할 변경, 삭제는 `super_admin`만 수행할 수 있습니다.
- 활성 상태인 마지막 `super_admin` 계정은 강등·비활성화·삭제할 수 없습니다. 이 검사는 트랜잭션 안에서 활성 super_admin 행을 id 순으로 잠근 뒤 수행되므로, 서로 다른 super_admin 두 명을 동시에 강등하는 요청이 겹쳐도 시스템에 super_admin이 전혀 남지 않는 상황이 생기지 않습니다.
- 자기 자신을 삭제하거나 비활성화하는 요청은 대상이 몇 명이든 상관없이 항상 거절됩니다. 운영자가 스스로를 잠그는 사고를 막기 위한 조치입니다.

## 토큰과 비밀번호

access 토큰과 refresh 토큰은 모두 `type` claim으로 구분되며, 서로 다른 용도로는 절대 통용되지 않습니다. 예를 들어 refresh 토큰을 `/auth/me`의 Bearer 토큰으로 사용하면 401이 반환됩니다. `iat`와 `exp`는 항상 UTC 기준의 시간대 인식(aware) 값으로 발급되고, `sub`·`user_id`·`type`·`exp`는 모든 토큰이 반드시 가져야 하는 필수 claim으로, 이 중 하나라도 없으면 검증 단계에서 거절됩니다.

RBAC 검증(`/rbac/verify-permission`, `require_role` 의존성)은 토큰에 담긴 역할 claim을 신뢰하지 않고, 매 요청마다 데이터베이스에서 사용자의 현재 역할과 활성 상태를 다시 조회합니다. 따라서 계정이 강등되거나 비활성화되면 이미 발급된 access 토큰이라도 즉시 권한을 잃습니다. 다만 refresh 토큰의 회전(rotation)과 서버 측 폐기 저장소는 아직 구현되어 있지 않으며, 이는 후속 과제로 남아 있습니다(코드 내 `TODO(follow-up)` 참고).

비밀번호는 bcrypt로 해시하여 저장하며, 최소 12자 이상이어야 하고 UTF-8로 인코딩했을 때 72바이트를 넘으면 안 됩니다. bcrypt 자체가 72바이트를 넘는 입력을 자동으로 잘라내는데, 그렇게 되면 72바이트까지 같은 두 비밀번호가 실질적으로 동일하게 취급되므로, Bidar는 이를 서버에서 조용히 자르는 대신 입력 단계에서 명시적으로 거절합니다.

## 환경 변수

`env.example`을 복사해 `.env`로 사용합니다. `ENVIRONMENT=production`일 때는 아래 표의 검증 규칙이 적용되어, 조건을 만족하지 못하면 서버가 아예 기동되지 않습니다.

| 변수 | 필수 여부 | 설명 |
|---|---|---|
| `ENVIRONMENT` | 아니오 | `development` \| `production` \| `test`. 기본값은 `development` |
| `JWT_SECRET_KEY` | production에서 필수 | 32자 이상이어야 하며, `changethis`·`example`·`placeholder` 등 예시 값으로 흔히 쓰이는 문자열이 포함되어 있으면 거절됩니다. development·test에서 비워 두면 재시작마다 바뀌는 임시 키가 자동 발급됩니다 |
| `JWT_ALGORITHM` | 아니오 | 기본값 `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 아니오 | 기본값 30 |
| `REFRESH_TOKEN_EXPIRE_DAYS` | 아니오 | 기본값 7 |
| `DATABASE_URL` | production에서 필수 | development에서 비워 두면 로컬용 기본값으로 대체됩니다 |
| `ALLOWED_HOSTS` | production에서 필수 | 쉼표로 구분한 호스트 목록. `TrustedHostMiddleware`에 그대로 전달됩니다. production에서 빈 값과 `*` 모두 기동 실패로 이어집니다. `auth-server`와 `localhost`를 반드시 포함해야 합니다 |
| `ALLOWED_ORIGINS` | production에서 필수 | 쉼표로 구분한 CORS origin 목록. production에서 빈 값과 `*` 모두 기동 실패로 이어집니다 |
| `FORWARDED_ALLOW_IPS` | 아니오 | uvicorn이 `X-Forwarded-For`·`X-Forwarded-Proto` 헤더를 신뢰할 리버스 프록시 주소. 기본값은 `127.0.0.1`이며, 운영 환경에서는 실제 프록시(VM1 Nginx) 주소로 지정해야 합니다. 로그인 rate limit이 이 값을 거쳐 계산된 클라이언트 주소를 키로 사용하기 때문입니다 |
| `LOGIN_RATE_LIMIT_PER_MINUTE` | 아니오 | `POST /auth/token`에만 적용되는 분당 요청 제한. 기본값 10. 이 제한은 워커 프로세스 내부 메모리 기반이라 워커마다 별도로 집계되며 재시작하면 초기화되므로, 완화 수단일 뿐 엄격한 쿼터는 아닙니다 |
| `HOST`, `PORT` | 아니오 | 서비스가 바인드할 주소와 포트. 기본값 `0.0.0.0:8001` |
| `DEBUG`, `LOG_LEVEL` | 아니오 | 로깅 관련 설정 |

## 최초 관리자 생성

공개 회원가입이 없으므로, 최초의 관리자 계정은 CLI로 생성합니다. 비밀번호는 명령줄 인자로 받지 않으며, 셸 히스토리나 프로세스 목록에 남지 않도록 환경 변수 또는 대화형 프롬프트로만 입력받습니다.

```bash
# 환경 변수로 비밀번호를 전달하는 방식
BIDAR_ADMIN_PASSWORD='...' uv run python -m src.cli create-admin \
  --username admin --email admin@example.com

# 터미널이 대화형이면 비밀번호를 프롬프트로 두 번 입력받아 확인합니다
uv run python -m src.cli create-admin --username admin --email admin@example.com
```

`--role` 옵션으로 `user`·`moderator`·`admin`·`super_admin` 중 하나를 지정할 수 있으며, 생략하면 `super_admin`이 기본값입니다. `--non-interactive`를 지정하면 환경 변수가 없을 때 프롬프트 대신 즉시 오류로 종료합니다.

## 로컬 개발과 테스트

```bash
# 의존성 설치
uv sync

# 개발 서버 실행 (env.example을 .env로 복사한 뒤)
./scripts/dev.sh

# 테스트 실행: DB·JWT 키 등 필요한 환경 변수를 스크립트가 직접 지정하므로
# 로컬 셸이나 .env에 남아 있는 값의 영향을 받지 않습니다
./scripts/test.sh

# 포매팅과 린트
./scripts/lint.sh
```

Docker 이미지는 `uv.lock`에서 내보낸 `requirements.txt`를 기준으로 런타임 의존성만 설치하며, uid 10001의 비root 사용자로 실행됩니다. CI는 이미지가 빌드 시점의 lock 파일과 어긋나지 않도록 `requirements.txt`와 `uv.lock`의 일치 여부를 검사합니다.

```bash
docker build -t bidar .
```

## 마이그레이션

스키마 변경은 `migrations/` 폴더의 SQL 스크립트로만 적용하며, Alembic은 도입하지 않습니다. 애플리케이션의 `init_db()`는 `create_all`만 수행하므로 기존 테이블의 컬럼 변경에는 관여하지 않습니다.

적용 순서는 `001_add_role_to_users.sql` → `002_preflight.sql`(읽기 전용 감사) → `002_align_role_and_superuser.sql`입니다. 운영 데이터는 VM3의 호스트 PostgreSQL 인스턴스에 있으며, 데이터베이스 이름은 `bngdrasil`입니다. 모든 실행 명령에는 `ON_ERROR_STOP=1`을 붙여서, 중간 구문이 실패했을 때 나머지가 조용히 이어지지 않도록 합니다. 상세한 절차와 확인해야 할 항목은 [`migrations/README.md`](migrations/README.md)를 참고하십시오.

## 운영 배포 (GitHub Actions)

`main` 브랜치에 커밋이 반영되면 `.github/workflows/release.yml`이 실행되어, 컨테이너 이미지를 빌드하고 운영 VM2의 auth-server 컨테이너를 교체합니다. 기존 `ci.yml`은 그대로 유지되며, 테스트와 린트, 보안 점검은 계속 그쪽에서 담당합니다.

### 워크플로 구성

워크플로는 다음 네 개의 job으로 이루어져 있습니다.

| job | 실행 환경 | 하는 일 |
| --- | --- | --- |
| `plan` | `ubuntu-latest` | 새 이미지를 빌드할지, 아니면 이미 올라가 있는 태그를 그대로 배포할지 결정합니다. |
| `test` | `ubuntu-latest` | `uv sync --group dev --frozen` 이후 `pytest`를 한 번 실행합니다. 검증되지 않은 트리에서 release가 나가지 않도록 막는 역할입니다. |
| `build` | `ubuntu-24.04-arm` | `ghcr.io/bngdrasil/bidar` 이미지를 `linux/arm64`로 빌드하여 push합니다. 태그는 `sha-<짧은 커밋 해시>`와 `main` 두 가지이고, 이후 단계에는 digest로 고정된 참조를 넘깁니다. |
| `deploy` | `ubuntu-latest` | `production` 환경에서 VM2에 SSH로 접속하여 `sudo /opt/bnbong/deploy-image.sh auth-server <이미지 참조>`를 실행하고, 그 뒤에 health 확인을 한 번 수행합니다. |

트리거는 `main` 브랜치 push와 `workflow_dispatch` 두 가지입니다. `workflow_dispatch`는 `image_tag`와 `skip_build` 두 개의 입력을 받으며, 두 입력은 롤백에 사용합니다.

`deploy` job에는 `concurrency: vm2-deploy` 그룹이 걸려 있습니다. VM2에는 compose 프로젝트가 하나뿐이므로, 두 개의 배포가 동시에 컨테이너를 교체하지 않도록 뒤에 들어온 실행을 취소하지 않고 대기시킵니다.

배포 이후의 smoke 확인은 VM2에 SSH로 접속한 상태에서 `curl -fsS http://127.0.0.1:8001/health`를 한 번 호출하는 방식입니다. Bidar는 `/health`를 애플리케이션 루트에 두고 있는데, VM1 Nginx의 `location /auth` 블록이 URI를 바꾸지 않고 그대로 전달하기 때문에 `https://api.bnbong.com/auth/health`로 요청하면 Bidar에는 `/auth/health`가 도착하고 404가 반환됩니다. 즉 이 health 엔드포인트에 닿는 공개 경로가 현재로서는 존재하지 않으므로, 확인 대상을 VM2의 loopback 포트로 잡았습니다.

실제 컨테이너 교체는 Baedalus 저장소가 제공하는 `deploy-image.sh`가 담당합니다. 이 스크립트는 이미지를 pull하고, 직전 이미지를 `rollback/<컨테이너>:<UTC 시각>`으로 태그해 두고, `/opt/bnbong/.env`의 `AUTH_SERVER_IMAGE` 값을 갱신한 뒤 `docker compose up -d --no-deps auth-server`를 실행하며, health 확인에 실패하면 직전 이미지로 스스로 되돌리고 0이 아닌 코드로 종료합니다. 워크플로는 이 종료 코드만 신뢰하며, 배포 절차 자체를 다시 구현하지 않습니다.

### 필요한 secrets와 environment

저장소 설정에서 다음 값을 미리 등록해야 합니다.

| 이름 | 종류 | 설명 |
| --- | --- | --- |
| `VM2_SSH_PRIVATE_KEY` | secret | VM2 배포 계정의 SSH 개인키 전문입니다. |
| `VM2_SSH_KNOWN_HOSTS` | secret | VM2의 호스트 키 항목입니다. 워크플로가 `StrictHostKeyChecking=yes`로 접속하므로 이 값이 없으면 연결이 거부됩니다. |
| `VM2_HOST` | secret | VM2의 접속 주소입니다. |
| `VM2_USER` | secret (선택) | 접속 계정 이름이며, 등록하지 않으면 `ubuntu`를 사용합니다. |
| `production` | environment | `deploy` job이 사용하는 환경입니다. 수동 승인이 필요하면 이 환경에 required reviewers를 지정하십시오. |

GHCR에 push할 때 쓰는 자격 증명은 별도로 등록하지 않습니다. `build` job이 `packages: write` 권한으로 발급된 `GITHUB_TOKEN`을 그대로 사용합니다.

### 최초 1회 준비

1. 첫 push가 끝나면 GitHub의 Packages 화면에서 `bidar` 패키지를 열고, 가시성을 public으로 변경하십시오. 이 설정을 마쳐야 VM2가 `docker login` 없이 이미지를 pull할 수 있습니다. 같은 화면에서 이 저장소에 `Write` 권한을 연결해 두어야 이후 push가 계속 성공합니다.
2. Baedalus 저장소의 `deploy-image.sh`를 VM2의 `/opt/bnbong/deploy-image.sh` 경로에 설치하고 실행 권한을 부여하십시오. 워크플로는 이 스크립트를 `sudo`로 호출하므로, 배포 계정이 해당 명령을 비밀번호 없이 실행할 수 있어야 합니다.
3. `/opt/bnbong/.env`에 `AUTH_SERVER_IMAGE` 항목이 존재하는지 확인하십시오. compose 파일이 이 변수로 이미지를 고르며, 값이 비어 있으면 로컬 빌드 이미지인 `bnbong-auth-server`로 되돌아갑니다.
4. 저장소 설정에서 `production` 환경을 만들고, 필요한 보호 규칙과 위의 secrets를 등록하십시오.

### 롤백 방법

Actions 화면에서 `Release` 워크플로를 선택한 뒤 `Run workflow`를 누르고, `image_tag`에 되돌리려는 커밋의 태그를 `sha-1a2b3c4` 형식으로 입력하십시오. `image_tag`를 지정하면 `test`와 `build` job을 건너뛰고 그 태그를 그대로 배포합니다. `skip_build`를 체크하는 경우에도 `image_tag`는 반드시 함께 입력해야 하며, 비어 있으면 `plan` job이 오류로 중단됩니다.

VM2에서 직접 되돌려야 하는 상황이라면 `deploy-image.sh`가 남겨 둔 `rollback/vm2-auth:<UTC 시각>` 태그를 사용할 수 있습니다. 다만 이 경로로 되돌린 내용은 GitHub 쪽 기록에 남지 않으므로, 이후에 `image_tag`를 사용한 배포로 상태를 맞추어 두는 편이 좋습니다.

## 운영 배포 시 주의 사항

- 이번 변경으로 토큰 검증 규칙이 강화되었으므로, 배포 이후 기존에 발급된 토큰은 모두 무효가 됩니다. 배포 후에는 모든 사용자가 다시 로그인해야 합니다.
- `ALLOWED_HOSTS`, `ALLOWED_ORIGINS`, `DATABASE_URL`, `JWT_SECRET_KEY`가 production 환경에서 새로 필수가 되었습니다. 값이 비어 있거나 예시 값이면 서버가 기동되지 않으므로, 배포 전에 환경 변수를 반드시 채워야 합니다.
- Docker 이미지는 uid 10001의 비root 사용자로 실행되므로, 볼륨이나 마운트 경로의 소유권이 이 uid에 맞춰져 있는지 확인해야 합니다.

## 알려진 제한과 후속 과제

- refresh 토큰의 회전(rotation)과 서버 측 폐기(revocation) 저장소가 아직 없습니다. 탈취된 refresh 토큰은 만료 전까지 계속 유효합니다.
- 로그인 rate limit은 워커 프로세스 내부 메모리 기반이며, 여러 워커나 여러 인스턴스에 걸쳐 공유되지 않습니다. durable한 제어는 게이트웨이 계층의 별도 limiter가 맡아야 합니다.
- `FORWARDED_ALLOW_IPS`를 신뢰 프록시 주소가 아니라 `*`로 설정한 채 포트가 외부에 직접 노출되면, 클라이언트가 자신의 출발지 주소를 위조해 rate limit을 우회할 수 있습니다. 운영 환경에서는 반드시 실제 리버스 프록시 주소로 좁혀야 합니다.
