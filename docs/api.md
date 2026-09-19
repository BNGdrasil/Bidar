# API 참조

Bidar가 제공하는 HTTP 엔드포인트와 각 엔드포인트가 요구하는 권한, 주요 응답 상태 코드를 정리한 문서입니다.

공개 회원가입 엔드포인트는 존재하지 않습니다. 계정은 `super_admin` 권한을 가진 사용자가 `POST /users`로 생성하거나, `python -m src.cli create-admin` CLI로만 생성할 수 있습니다. CLI 사용법은 [운영 가이드](operations.md)를 참고하십시오.

## 엔드포인트 목록

| 메서드 · 경로 | 설명 | 필요 권한 | 주요 상태 코드 |
|---|---|---|---|
| `POST /auth/token` | OAuth2 호환 폼 로그인입니다. 로그인 시도는 IP당 분당 요청 수로 제한됩니다. | 없음 | 401(자격 증명 오류·비활성 계정), 429(요청 과다) |
| `POST /auth/refresh` | refresh 토큰으로 access 토큰을 재발급합니다. refresh 토큰만 받아들이며 access 토큰을 넣으면 거절됩니다. | refresh 토큰 | 401(토큰 종류 불일치·만료·비활성 계정) |
| `GET /auth/me` | 현재 로그인한 사용자 정보를 반환합니다. | access 토큰 | 401 |
| `POST /users` | 사용자를 생성합니다. 성공하면 201을 반환합니다. | super_admin | 400(아이디·이메일 중복), 401, 403, 422 |
| `GET /users/users` | 전체 사용자 목록을 조회합니다. | admin 이상 | 401, 403 |
| `GET /users/users/{id}` | 단일 사용자를 조회합니다. | admin 이상 | 401, 403, 404 |
| `PATCH /users/users/{id}` | 사용자의 프로필과 역할, 활성 상태를 수정합니다. | super_admin | 401, 403, 404, 409(마지막 활성 super_admin 보호), 422 |
| `DELETE /users/users/{id}` | 사용자를 삭제합니다. 성공하면 204를 반환합니다. | super_admin | 400(자기 자신 삭제 시도), 401, 403, 404, 409(마지막 활성 super_admin 보호) |
| `PUT /users/users/{id}/activate` | 사용자를 활성화합니다. | admin 이상(대상이 admin 이상이면 super_admin) | 401, 403, 404 |
| `PUT /users/users/{id}/deactivate` | 사용자를 비활성화합니다. | admin 이상(대상이 admin 이상이면 super_admin) | 400(자기 자신 비활성화 시도), 401, 403, 404, 409(마지막 활성 super_admin 보호) |
| `POST /rbac/verify-permission` | Bearer 토큰과 요구 역할을 받아 데이터베이스의 현재 역할과 활성 상태로 권한을 확인합니다. Bifrost가 위임 확인용으로 호출합니다. | access 토큰 | 401, 403 |
| `GET /rbac/my-role` | 현재 로그인한 사용자의 역할 정보를 반환합니다. | access 토큰 | 401 |
| `GET /health` | 서비스 상태 확인용 헬스체크입니다. | 없음 | 200 |
| `GET /metrics` | Prometheus 형식의 메트릭을 노출합니다. | 없음 | 200 |
| `GET /` | 서비스 이름과 버전, 문서 경로를 반환합니다. production에서는 문서 경로가 `null`이 됩니다. | 없음 | 200 |

## 권한 판정 방식

각 엔드포인트가 요구하는 역할은 토큰에 담긴 역할 claim이 아니라 데이터베이스의 현재 값으로 판정합니다. 역할 계층과 권한 경계의 자세한 규칙은 [인증·권한 모델](auth-model.md)에 정리되어 있습니다.
