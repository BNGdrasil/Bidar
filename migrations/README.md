# Database migrations

Bidar 인증 서버의 PostgreSQL 스키마 변경 스크립트를 모아 둔 폴더입니다.

## 대상 데이터베이스

운영 데이터는 VM3의 **호스트 PostgreSQL** 인스턴스에 있고, 데이터베이스 이름은
`bngdrasil`입니다. `users` 테이블도 이 데이터베이스에 있습니다. PostgreSQL 컨테이너는
사용하지 않으므로 `docker exec ... psql` 형태의 옛 명령은 더 이상 유효하지 않습니다.

## 실행 방법

VM3에 접속한 뒤 `postgres` 사용자로 실행합니다. `ON_ERROR_STOP=1`을 반드시 붙여서
중간 구문이 실패하면 즉시 중단되도록 합니다.

```bash
# 1) 읽기 전용 감사
sudo -u postgres psql -d bngdrasil -v ON_ERROR_STOP=1 \
  -f migrations/002_preflight.sql

# 2) 출력을 확인한 뒤 적용
sudo -u postgres psql -d bngdrasil -v ON_ERROR_STOP=1 \
  -f migrations/002_align_role_and_superuser.sql
```

워크스테이션에서 파일만 전송하는 경우는 다음과 같습니다.

```bash
scp migrations/002_align_role_and_superuser.sql ubuntu@<VM3_HOST>:/tmp/
ssh ubuntu@<VM3_HOST> 'sudo -u postgres psql -d bngdrasil -v ON_ERROR_STOP=1 \
  -f /tmp/002_align_role_and_superuser.sql'
```

저장소의 `scripts/run-migration.sh`는 위 명령을 감싼 래퍼이며 VM3에서 실행합니다.

## 마이그레이션 목록

| ID | 파일명 | 설명 |
|----|--------|------|
| 001 | `001_add_role_to_users.sql` | `users` 테이블에 `role` 컬럼과 check 제약, 인덱스 추가 |
| 002 | `002_preflight.sql` | **읽기 전용 감사.** 002가 무엇을 바꿀지 미리 보여 줍니다 |
| 002 | `002_align_role_and_superuser.sql` | `role`을 단일 기준으로 삼고 `is_superuser`를 파생값으로 정합, `role`/`is_active`/`is_superuser`에 NOT NULL과 기본값 부여 |

두 마이그레이션 모두 반복 실행해도 같은 결과가 되도록 작성했습니다.

## 적용 전 준비

1. 적용 직전에 논리 백업을 남깁니다.
   ```bash
   sudo -u postgres pg_dump -Fc -d bngdrasil -f /var/backups/bngdrasil-$(date +%F).dump
   ```
2. 001을 먼저 적용합니다.
3. **preflight를 실행하고 출력을 읽습니다.** 002는 값을 되돌리는 자동 롤백이 없으므로
   무엇이 바뀌는지 먼저 확인합니다.
   ```bash
   sudo -u postgres psql -d bngdrasil -v ON_ERROR_STOP=1 \
     -f migrations/002_preflight.sql
   ```
   확인할 항목은 다음과 같습니다.
   - **섹션 3**: `role`이 비어 있거나 `user`인 채로 `is_superuser=TRUE`인 행입니다. 002가
     이 행만 `super_admin`으로 승격합니다.
   - **섹션 4**: `role`이 `moderator`나 `admin`인데 `is_superuser=TRUE`인 행입니다. 002는
     role을 의도된 값으로 신뢰하고 플래그 쪽을 `FALSE`로 정정합니다. 이 행들을 실제로
     super_admin으로 올려야 한다면 002 적용 전에 role을 직접 수정하십시오.
   - **섹션 5**: 002 적용 후 남을 활성 super_admin 수입니다. **0이면 002를 적용하기 전에**
     CLI로 계정을 만듭니다.
   - **섹션 6**: `is_active`가 NULL인 행 수입니다. 002는 이 값을 `TRUE`가 아니라 `FALSE`로
     채웁니다. 기존 앱이 NULL을 비활성으로 취급해 거부했기 때문에 동작을 보존하는
     선택이며, 필요한 계정은 적용 후 의도적으로 활성화합니다.
   - **섹션 7**: 허용 목록 밖의 role입니다. 비어 있지 않으면 002의 check 제약이 실패하므로
     먼저 정리해야 합니다.
4. preflight 결과가 의도와 맞으면 002를 적용합니다. 002는 `RAISE NOTICE`로 승격·정정·
   비활성화 건수를 출력하므로 preflight에서 본 숫자와 대조합니다.
5. 활성 super_admin이 한 명도 없다면 CLI로 계정을 만듭니다. 서버는 마지막 super_admin의
   삭제·강등·비활성화를 거부하지만, 애초에 한 명도 없으면 관리 API에 접근할 수 없습니다.
   ```bash
   BIDAR_ADMIN_PASSWORD='...' uv run python -m src.cli create-admin \
     --username <name> --email <email>
   ```

## 검증

```sql
\d users

SELECT role, is_superuser, is_active, COUNT(*)
FROM users
GROUP BY role, is_superuser, is_active
ORDER BY role;

SELECT COUNT(*) AS active_super_admins
FROM users
WHERE role = 'super_admin' AND is_active;
```

`role`과 `is_superuser`가 어긋난 행은 0건이어야 합니다.

## 롤백

002는 데이터 정합만 맞추므로 되돌릴 필요가 거의 없습니다. 제약과 기본값만 해제하려면
다음을 실행합니다.

```sql
ALTER TABLE users ALTER COLUMN role DROP NOT NULL;
ALTER TABLE users ALTER COLUMN is_superuser DROP NOT NULL;
ALTER TABLE users ALTER COLUMN is_active DROP NOT NULL;
ALTER TABLE users DROP CONSTRAINT IF EXISTS check_user_role;
```

001까지 되돌리려면 `role` 컬럼과 인덱스를 함께 제거합니다.

```sql
DROP INDEX IF EXISTS idx_users_role;
ALTER TABLE users DROP CONSTRAINT IF EXISTS check_user_role;
ALTER TABLE users DROP COLUMN IF EXISTS role;
```

## 주의

Alembic은 도입하지 않습니다. 애플리케이션의 `init_db()`는 `create_all`이라서 기존
테이블의 스키마를 변경하지 않으므로, 컬럼 변경은 이 폴더의 SQL로만 적용합니다.
