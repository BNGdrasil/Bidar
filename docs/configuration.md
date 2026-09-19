# 환경 변수

Bidar가 읽는 환경 변수와 production 환경에서 적용되는 검증 규칙을 정리한 문서입니다.

`env.example`을 복사해 `.env`로 사용합니다. 값은 프로세스 환경에서 먼저 읽고, 없으면 `.env` 파일에서 읽습니다. 빈 값은 설정하지 않은 것과 동일하게 취급하므로, compose 파일이 미설정 변수를 빈 문자열로 확장해도 기본값으로 되돌아갑니다.

`ENVIRONMENT=production`일 때는 아래 표의 검증 규칙이 적용됩니다. 조건을 만족하지 못하면 서버가 아예 기동되지 않습니다.

## 변수 목록

| 변수 | 필수 여부 | 설명 |
|---|---|---|
| `ENVIRONMENT` | 아니오 | `development`, `production`, `test` 가운데 하나입니다. 기본값은 `development`입니다. |
| `JWT_SECRET_KEY` | production에서 필수 | 32자 이상이어야 합니다. `changethis`, `example`, `placeholder` 등 예시 값으로 흔히 쓰이는 문자열이 포함되어 있으면 거절됩니다. development와 test에서 비워 두면 재시작마다 바뀌는 임시 키가 자동으로 발급됩니다. |
| `JWT_ALGORITHM` | 아니오 | 기본값은 `HS256`입니다. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 아니오 | 기본값은 30입니다. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | 아니오 | 기본값은 7입니다. |
| `DATABASE_URL` | production에서 필수 | development에서 비워 두면 로컬용 기본값으로 대체됩니다. |
| `ALLOWED_HOSTS` | production에서 필수 | 쉼표로 구분한 호스트 목록이며 `TrustedHostMiddleware`에 그대로 전달됩니다. production에서는 빈 값과 `*`가 모두 기동 실패로 이어집니다. `auth-server`와 `localhost`를 반드시 포함해야 합니다. |
| `ALLOWED_ORIGINS` | production에서 필수 | 쉼표로 구분한 CORS origin 목록입니다. production에서는 빈 값과 `*`가 모두 기동 실패로 이어집니다. |
| `FORWARDED_ALLOW_IPS` | 아니오 | uvicorn이 `X-Forwarded-For`와 `X-Forwarded-Proto` 헤더를 신뢰할 리버스 프록시 주소입니다. 기본값은 `127.0.0.1`이며, 운영 환경에서는 실제 프록시(VM1 Nginx) 주소로 지정해야 합니다. 로그인 rate limit이 이 값을 거쳐 계산된 클라이언트 주소를 키로 사용하기 때문입니다. |
| `LOGIN_RATE_LIMIT_PER_MINUTE` | 아니오 | `POST /auth/token`에만 적용되는 분당 요청 제한이며 기본값은 10입니다. 워커 프로세스 내부 메모리를 사용하므로 완화 수단일 뿐 엄격한 쿼터는 아닙니다. |
| `HOST`, `PORT` | 아니오 | 서비스가 바인드할 주소와 포트입니다. 기본값은 `0.0.0.0:8001`입니다. |
| `DEBUG`, `LOG_LEVEL` | 아니오 | 로깅 관련 설정입니다. |

## production 검증 규칙

서버는 기동 시점에 다음 항목을 차례로 확인합니다.

1. `JWT_SECRET_KEY`가 비어 있지 않고, 32자 이상이며, 예시 값 표지를 포함하지 않는지 확인합니다.
2. `DATABASE_URL`이 비어 있지 않은지 확인합니다. production에는 대체 기본값이 없습니다.
3. `ALLOWED_HOSTS`와 `ALLOWED_ORIGINS`가 비어 있지 않고 `*`를 포함하지 않는지 확인합니다.

development와 test에서는 같은 항목이 완화되어 적용됩니다. 비밀 키는 임시 값으로 대체되고, 데이터베이스 주소는 로컬용 기본값으로 대체되며, 호스트 목록과 origin 목록은 `*`로 대체됩니다.

권장하는 production 값은 다음과 같습니다.

```bash
ALLOWED_HOSTS=api.bnbong.com,auth-server,localhost
ALLOWED_ORIGINS=https://admin.bnbong.com,https://bnbong.com
```

`ALLOWED_HOSTS`가 공개 도메인만으로는 부족한 이유는 `TrustedHostMiddleware`가 내부 요청을 포함한 모든 요청의 Host 헤더를 검사하기 때문입니다. Bifrost는 compose 서비스 이름인 `auth-server`로 이 서비스를 호출하고, 컨테이너 HEALTHCHECK는 `http://localhost:8001`을 호출합니다.

비밀 키는 다음 명령으로 생성할 수 있습니다.

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

배포 시 확인해야 할 사항은 [운영 가이드](operations.md)에 정리되어 있습니다.
