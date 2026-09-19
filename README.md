<p align="center">
    <img align="top" width="30%" src="https://raw.githubusercontent.com/BNGdrasil/.github/main/images/Bidar.png" alt="Bidar"/>
</p>

<div align="center">

# Bidar (Bnbong + Vidar)

**BNGdrasil의 중앙 인증 서버**

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)

*[BNGdrasil](https://github.com/BNGdrasil) 생태계의 일부입니다*

</div>

---

## 소개

Bidar는 BNGdrasil의 중앙 인증 서버입니다. 사용자 계정과 역할을 관리합니다. JWT 로그인과 토큰 갱신, 사용자 관리 API를 제공합니다. 다른 서비스는 Bidar에 권한 확인을 위임합니다.

## 주요 기능

- JWT 토큰을 발급하고 검증합니다.
- 4단계 역할 권한을 관리합니다.
- 다른 서비스의 권한 확인을 위임받습니다.
- 마지막 super_admin 계정을 보호합니다.
- CLI로 관리자 계정을 생성합니다.
- 헬스체크와 Prometheus 지표를 제공합니다.

## 빠른 시작

```bash
uv sync                                    # 의존성 설치
cp env.example .env                        # 환경 변수 준비
./scripts/dev.sh                           # 개발 서버 실행
./scripts/test.sh                          # 테스트 실행

# 최초 관리자 계정 생성
BIDAR_ADMIN_PASSWORD='...' uv run python -m src.cli create-admin --username admin --email admin@example.com
```

## 문서

| 문서 | 설명 |
| --- | --- |
| [API 참조](docs/api.md) | 엔드포인트와 필요 권한, 상태 코드 |
| [인증·권한 모델](docs/auth-model.md) | 역할 계층과 권한, 토큰 규칙 |
| [환경 변수](docs/configuration.md) | 설정값과 production 검증 규칙 |
| [운영 가이드](docs/operations.md) | 계정 관리와 배포, 롤백 절차 |
| [로컬 개발](docs/development.md) | 실행과 테스트, 린트, Docker 빌드 |

## 관련 프로젝트

- [Bifrost](https://github.com/BNGdrasil/Bifrost): API 게이트웨이
- [Bantheon](https://github.com/BNGdrasil/Bantheon): 웹 클라이언트와 VM1 Nginx 설정
- [Baedalus](https://github.com/BNGdrasil/Baedalus): 인프라 코드와 운영 도구
