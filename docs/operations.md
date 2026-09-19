# 운영 가이드

관리자 계정 관리와 데이터베이스 마이그레이션, GitHub Actions 배포 절차, 운영 환경에서 유의해야 할 사항을 정리한 문서입니다.

## 최초 관리자 생성

공개 회원가입이 없으므로 최초의 관리자 계정은 CLI로 생성합니다. 비밀번호는 명령줄 인자로 받지 않습니다. 셸 히스토리나 프로세스 목록에 남지 않도록 환경 변수 또는 대화형 프롬프트로만 입력받습니다.

```bash
# 환경 변수로 비밀번호를 전달하는 방식
BIDAR_ADMIN_PASSWORD='...' uv run python -m src.cli create-admin \
  --username admin --email admin@example.com

# 터미널이 대화형이면 비밀번호를 프롬프트로 두 번 입력받아 확인합니다
uv run python -m src.cli create-admin --username admin --email admin@example.com
```

`--role` 옵션으로 `user`, `moderator`, `admin`, `super_admin` 가운데 하나를 지정할 수 있습니다. 생략하면 `super_admin`이 기본값입니다. `--non-interactive`를 지정하면 환경 변수가 없을 때 프롬프트를 띄우지 않고 즉시 오류로 종료합니다.

## 비밀번호 재설정

기존 계정의 비밀번호를 잊어버렸다면 `reset-password` 서브커맨드로 새 비밀번호를 지정합니다. 이 명령도 비밀번호를 명령줄 인자로 받지 않으며, 환경 변수 `BIDAR_NEW_PASSWORD` 또는 대화형 프롬프트로만 입력받습니다. 프롬프트는 오타를 막기 위해 같은 값을 두 번 입력받아 확인합니다.

```bash
# 환경 변수로 새 비밀번호를 전달하는 방식
BIDAR_NEW_PASSWORD='...' uv run python -m src.cli reset-password --username admin

# 운영 환경에서는 인증 서버 컨테이너 안에서 실행합니다
sudo docker exec -it vm2-auth python -m src.cli reset-password --username bnbong
```

새 비밀번호는 계정 생성과 동일한 규칙을 따릅니다. 즉 최소 12자 이상이어야 하고, UTF-8로 인코딩했을 때 72바이트를 넘으면 bcrypt가 처리할 수 없으므로 거부됩니다. 자세한 규칙은 [인증·권한 모델](auth-model.md)을 참고하십시오.

지정한 사용자가 존재하지 않으면 종료 코드 1로 실패합니다. 비활성 상태인 계정이라면 경고만 출력하고 비밀번호를 그대로 변경합니다. 변경에 성공하면 `Password updated for <username>`을 출력합니다.

이미 발급된 액세스 토큰과 리프레시 토큰은 비밀번호를 재설정해도 무효화되지 않습니다. 이 서비스는 발급한 토큰을 서버 측에서 폐기하는 저장소를 두고 있지 않기 때문에, 기존 토큰은 만료 시각까지 그대로 사용할 수 있습니다.

## 마이그레이션

스키마 변경은 `migrations/` 폴더의 SQL 스크립트로만 적용하며, Alembic은 도입하지 않습니다. 애플리케이션의 `init_db()`는 `create_all`만 수행하므로 기존 테이블의 컬럼 변경에는 관여하지 않습니다.

적용 순서는 `001_add_role_to_users.sql`, `002_preflight.sql`(읽기 전용 감사), `002_align_role_and_superuser.sql`입니다. 운영 데이터는 VM3의 호스트 PostgreSQL 인스턴스에 있으며, 데이터베이스 이름은 `bngdrasil`입니다. 모든 실행 명령에는 `ON_ERROR_STOP=1`을 붙여서, 중간 구문이 실패했을 때 나머지가 조용히 이어지지 않도록 합니다.

상세한 절차와 확인해야 할 항목은 [`../migrations/README.md`](../migrations/README.md)에 정리되어 있습니다.

## GitHub Actions 배포

`main` 브랜치에 커밋이 반영되면 먼저 `.github/workflows/ci.yml`이 실행됩니다. 그 실행이 성공으로 끝났을 때에만 `.github/workflows/release.yml`이 이어서 실행되어 컨테이너 이미지를 빌드하고 운영 VM2의 auth-server 컨테이너를 교체합니다. release 워크플로는 자체 테스트 job을 가지고 있지 않으며, 테스트와 린트, 보안 점검은 모두 `ci.yml`이 담당합니다.

### 트리거와 CI 연동

`ci.yml`은 `main`과 `dev` 브랜치 push, 그리고 `main`을 대상으로 하는 pull request에서 실행됩니다. release는 이 가운데 `main` push에서 시작된 CI 실행을 `workflow_run` 이벤트로 넘겨받습니다.

```
main 브랜치에 push
        │
        ▼
  CI (ci.yml)
  ├─ test      : Python 3.12 / 3.13 행렬에서 pytest 실행
  ├─ lint      : black, isort, flake8, mypy 실행
  └─ security  : bandit, pip-audit, requirements 동기화 확인
        │
        ├─ 세 job 가운데 하나라도 실패하면 실행 결론이 failure가 됩니다.
        │      └─ Release의 plan job이 건너뛰어지고, build와 deploy도 실행되지 않습니다.
        │
        └─ 세 job이 모두 성공하면 실행 결론이 success가 됩니다.
               │
               ▼
        Release (release.yml)
        plan ──→ build ──→ deploy (production 환경)
```

GitHub는 실행에 포함된 모든 job이 성공했을 때에만 워크플로 실행의 결론을 `success`로 기록합니다. `ci.yml`의 세 job은 별도의 조건 없이 항상 실행되므로, 결론이 `success`라는 사실은 곧 test와 lint, security가 같은 커밋에서 모두 통과했다는 뜻입니다. 따라서 결과를 한 번 더 모으는 집계 job을 `ci.yml`에 추가하지 않았습니다. 다만 앞으로 `ci.yml`에 `if` 조건이나 `continue-on-error`가 붙은 job을 추가한다면 이 전제가 깨지므로, 그런 변경을 할 때에는 집계 job을 두는 방안을 함께 검토해야 합니다.

release가 다루는 커밋은 언제나 `github.event.workflow_run.head_sha`입니다. `workflow_run` 이벤트에서 `github.sha`는 이벤트가 전달된 시점의 기본 브랜치 최신 커밋을 가리키기 때문에, CI가 실제로 검증한 커밋과 어긋날 수 있습니다. 소스 checkout과 `sha-<짧은 커밋 해시>` 이미지 태그, 이미지 라벨의 revision 값은 모두 이 `head_sha`를 기준으로 삼습니다.

`workflow_run`으로 시작된 실행은 기본 브랜치에 정의된 내용을 따라 동작하며, 이때 secrets와 쓰기 권한이 있는 토큰을 사용할 수 있습니다. CI를 유발한 쪽이 fork의 pull request였더라도 이 점은 달라지지 않습니다. 게다가 `branches: [ main ]` 필터는 CI 실행의 head 브랜치 이름만 비교하므로, fork 쪽 브랜치 이름이 `main`이면 이 필터를 그대로 통과합니다. 그래서 `plan` job의 `if` 조건에서 `workflow_run.event == 'push'`와 `workflow_run.head_repository.full_name == github.repository`를 함께 확인하여, 이 저장소의 `main` push에서 시작된 실행만 배포까지 이어지도록 막아 두었습니다.

### 워크플로 구성

워크플로는 다음 세 개의 job으로 이루어져 있습니다.

| job | 실행 환경 | 하는 일 |
| --- | --- | --- |
| `plan` | `ubuntu-latest` | 배포 대상 커밋을 확정하고, 새 이미지를 빌드할지 아니면 이미 올라가 있는 태그를 그대로 배포할지 결정합니다. 수동 실행으로 새 코드를 빌드하는 경우에는 같은 커밋의 CI 성공 여부도 이 job에서 확인합니다. |
| `build` | `ubuntu-24.04-arm` | `ghcr.io/bngdrasil/bidar` 이미지를 `linux/arm64`로 빌드하여 push합니다. 태그는 `sha-<짧은 커밋 해시>`와 `main` 두 가지이고, 이후 단계에는 digest로 고정된 참조를 넘깁니다. |
| `deploy` | `ubuntu-latest` | `production` 환경에서 VM2에 SSH로 접속하여 `sudo /opt/bnbong/deploy-image.sh auth-server <이미지 참조>`를 실행하고, 그 뒤에 health 확인을 한 번 수행합니다. |

`deploy` job에는 `concurrency: vm2-deploy` 그룹이 걸려 있습니다. VM2에는 compose 프로젝트가 하나뿐이므로, 두 개의 배포가 동시에 컨테이너를 교체하지 않도록 뒤에 들어온 실행을 취소하지 않고 대기시킵니다.

배포 이후의 smoke 확인은 VM2에 SSH로 접속한 상태에서 `curl -fsS http://127.0.0.1:8001/health`를 한 번 호출하는 방식입니다. Bidar는 `/health`를 애플리케이션 루트에 두고 있는데, VM1 Nginx의 `location /auth` 블록이 URI를 바꾸지 않고 그대로 전달하기 때문에 `https://api.bnbong.com/auth/health`로 요청하면 Bidar에는 `/auth/health`가 도착하고 404가 반환됩니다. 즉 이 health 엔드포인트에 닿는 공개 경로가 현재로서는 존재하지 않으므로, 확인 대상을 VM2의 loopback 포트로 잡았습니다.

실제 컨테이너 교체는 Baedalus 저장소가 제공하는 `deploy-image.sh`가 담당합니다. 이 스크립트는 이미지를 pull하고, 직전 이미지를 `rollback/<컨테이너>:<UTC 시각>`으로 태그해 두고, `/opt/bnbong/.env`의 `AUTH_SERVER_IMAGE` 값을 갱신한 뒤 `docker compose up -d --no-deps auth-server`를 실행합니다. health 확인에 실패하면 직전 이미지로 스스로 되돌리고 0이 아닌 코드로 종료합니다. 워크플로는 이 종료 코드만 신뢰하며, 배포 절차 자체를 다시 구현하지 않습니다.

### 수동 실행의 두 가지 경로

`workflow_dispatch`로 실행하는 경우, 목적에 따라 서로 다른 규칙을 적용받습니다.

1. `image_tag`를 입력한 경우에는 롤백 전용 예외 경로로 동작합니다. 이미 GHCR에 올라가 있는 이미지를 그대로 다시 배포할 뿐이고, 새로 빌드하지 않습니다. 그 이미지는 과거에 CI 게이트를 통과한 커밋에서 만들어진 산출물이므로, CI 결과를 다시 조회하지 않습니다. 장애가 발생했을 때 곧바로 이전 버전으로 되돌릴 수 있도록 남겨 둔 예외입니다.
2. `image_tag`를 비워 둔 채 수동으로 실행한 경우에는 새 코드를 빌드하는 경로이므로, `workflow_run` 경로와 같은 기준을 적용합니다. `plan` job이 GitHub Actions API에 `repos/<owner>/<repo>/actions/workflows/ci.yml/runs?head_sha=<대상 커밋>`을 조회하여, 바로 그 커밋에 대한 CI 실행이 존재하고 모두 완료되었으며 전부 `success`로 끝났는지 확인합니다. 아직 끝나지 않은 실행이 있거나, 실패나 취소로 끝난 실행이 하나라도 있거나, 성공 기록이 아예 없으면 어떤 조건이 어긋났는지 밝히는 오류 메시지와 함께 중단됩니다. 다른 커밋에서 가장 최근에 성공한 CI 실행을 대신 인정하는 동작은 의도적으로 넣지 않았습니다.

이 조회를 수행하기 위해 `plan` job에 `actions: read` 권한을 부여했습니다.

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

Actions 화면에서 `Release` 워크플로를 선택한 뒤 `Run workflow`를 누르고, `image_tag`에 되돌리려는 커밋의 태그를 `sha-1a2b3c4` 형식으로 입력하십시오. `image_tag`를 지정하면 `build` job을 건너뛰고 그 태그를 그대로 배포합니다. `skip_build`를 체크하는 경우에도 `image_tag`는 반드시 함께 입력해야 하며, 비어 있으면 `plan` job이 오류로 중단됩니다. 앞의 "수동 실행의 두 가지 경로"에서 설명한 대로, 이 경로는 CI 결과를 다시 확인하지 않는 예외에 해당합니다.

VM2에서 직접 되돌려야 하는 상황이라면 `deploy-image.sh`가 남겨 둔 `rollback/vm2-auth:<UTC 시각>` 태그를 사용할 수 있습니다. 다만 이 경로로 되돌린 내용은 GitHub 쪽 기록에 남지 않으므로, 이후에 `image_tag`를 사용한 배포로 상태를 맞추어 두는 편이 좋습니다.

### 실제 Actions에서 확인해야 할 항목

지금까지 이 구성은 YAML 파싱과 actionlint 검사, 워크플로에 포함된 셸 스크립트의 문법 검사까지만 마쳤습니다. 다음 항목은 실제 GitHub Actions 실행으로 확인해야 합니다.

- 단위 테스트는 통과하지만 lint 또는 security가 실패하는 커밋을 `main`에 push했을 때, Release의 `plan` job이 건너뛰어지고 `build`와 `deploy`가 전혀 실행되지 않는지 확인해야 합니다.
- 세 job이 모두 성공한 커밋에서는 Release가 이어서 실행되고, 빌드된 이미지의 `sha-` 태그가 CI가 검증한 커밋의 짧은 해시와 일치하는지 확인해야 합니다.
- `image_tag`를 비워 둔 채 수동으로 실행했을 때, CI가 실패했거나 아직 끝나지 않은 커밋에서는 `plan` job이 오류 메시지와 함께 중단되는지 확인해야 합니다.
- `production` 환경에 설정한 승인 규칙과 배포 브랜치 정책이 실제 실행에서 적용되는지 확인해야 합니다.

## 운영 배포 시 주의 사항

- 토큰 검증 규칙이 강화되었으므로, 배포 이후 기존에 발급된 토큰은 모두 무효가 됩니다. 배포 후에는 모든 사용자가 다시 로그인해야 합니다.
- `ALLOWED_HOSTS`와 `ALLOWED_ORIGINS`, `DATABASE_URL`, `JWT_SECRET_KEY`가 production 환경에서 필수입니다. 값이 비어 있거나 예시 값이면 서버가 기동되지 않으므로, 배포 전에 환경 변수를 반드시 채워야 합니다. 자세한 규칙은 [환경 변수 문서](configuration.md)를 참고하십시오.
- Docker 이미지는 uid 10001의 비root 사용자로 실행되므로, 볼륨이나 마운트 경로의 소유권이 이 uid에 맞춰져 있는지 확인해야 합니다.

## 알려진 제한과 후속 과제

- refresh 토큰의 회전(rotation)과 서버 측 폐기(revocation) 저장소가 아직 없습니다. 탈취된 refresh 토큰은 만료 전까지 계속 유효합니다.
- 로그인 rate limit은 워커 프로세스 내부 메모리를 사용하며, 여러 워커나 여러 인스턴스에 걸쳐 공유되지 않습니다. 지속적인 제어는 게이트웨이 계층의 별도 limiter가 맡아야 합니다.
- `FORWARDED_ALLOW_IPS`를 신뢰 프록시 주소가 아니라 `*`로 설정한 채 포트가 외부에 직접 노출되면, 클라이언트가 자신의 출발지 주소를 위조해 rate limit을 우회할 수 있습니다. 운영 환경에서는 반드시 실제 리버스 프록시 주소로 좁혀야 합니다.
