# Keycloak SSO 통합 - AWX + Ansible Builder

이 디렉토리는 Keycloak을 사용하여 AWX와 Ansible Builder를 통합 인증 시스템(SSO)으로 구성하기 위한 모든 파일과 스크립트를 포함합니다.

## 파일 구조

```
/root/keycloak/
├── README.md                 # 이 파일
├── QUICKSTART.md            # 빠른 시작 가이드
├── docker-compose.yml       # Keycloak 서버 Docker Compose 설정
├── setup-keycloak.sh        # Keycloak 자동 설정 스크립트
└── test-integration.sh      # 통합 테스트 스크립트

/root/ansible-builder/
├── KEYCLOAK_INTEGRATION_GUIDE.md  # 상세 통합 가이드
└── ansible-builder/
    ├── backend/
    │   ├── keycloak_config.py     # Keycloak 설정
    │   └── keycloak_auth.py       # Keycloak 인증 모듈
    └── frontend/frontend/
        ├── src/keycloak.js        # Keycloak 클라이언트
        └── public/silent-check-sso.html
```

## 빠른 시작

### 1단계: Keycloak 서버 시작
```bash
cd /root/keycloak
docker-compose up -d
```

### 2단계: Keycloak 설정
```bash
./setup-keycloak.sh
```

### 3단계: 패키지 설치
```bash
# Backend
cd /root/ansible-builder/ansible-builder/backend
pip install python-keycloak authlib python-jose[cryptography]

# Frontend
cd /root/ansible-builder/ansible-builder/frontend/frontend
npm install keycloak-js
```

### 4단계: 통합 테스트
```bash
cd /root/keycloak
./test-integration.sh
```

## 주요 기능

### 🔐 SSO (Single Sign-On)
- 한 번 로그인으로 AWX와 Ansible Builder 모두 접근
- Keycloak 세션 기반 통합 인증

### 👥 중앙화된 사용자 관리
- Keycloak에서 모든 사용자 관리
- 역할 기반 접근 제어 (RBAC)
- JIT (Just-In-Time) 사용자 프로비저닝

### 🔄 자동 동기화
- Keycloak 사용자 정보 자동 동기화
- 역할 및 권한 실시간 업데이트

### 🛡️ 보안 강화
- OpenID Connect (OIDC) 표준 프로토콜
- JWT 토큰 기반 인증
- RS256 알고리즘 서명 검증

## 통합 아키텍처

```
          ┌─────────────────┐
          │    Keycloak     │
          │  (Identity IDP) │
          └────────┬─────┬──┘
                   │     │
        ┌──────────┘     └──────────┐
        │ OIDC                OIDC  │
        ▼                           ▼
   ┌────────┐              ┌─────────────┐
   │  AWX   │              │   Ansible   │
   │        │◄────SSO─────►│   Builder   │
   └────────┘              └─────────────┘
```

## 기본 계정 정보

### Keycloak Admin
- URL: http://localhost:8080/admin
- Username: `admin`
- Password: `admin123`

### 테스트 사용자
1. **Admin User**
   - Username: `admin`
   - Password: `admin123`
   - Roles: admin, awx-admin

2. **Regular User**
   - Username: `testuser`
   - Password: `test123`
   - Roles: user, awx-user

## 테스트 체크리스트

- [ ] Keycloak 서버 시작 확인
- [ ] Realm 및 Client 생성 확인
- [ ] 토큰 발급 테스트
- [ ] Ansible Builder 로그인 (Keycloak SSO)
- [ ] AWX 로그인 (Keycloak SSO)
- [ ] 통합 SSO 테스트 (한 곳 로그인 → 모두 로그인)
- [ ] 역할 기반 권한 확인
- [ ] 로그아웃 테스트

## 문서

- **빠른 시작**: [QUICKSTART.md](./QUICKSTART.md)
- **상세 가이드**: [KEYCLOAK_INTEGRATION_GUIDE.md](/root/ansible-builder/KEYCLOAK_INTEGRATION_GUIDE.md)
- **JWT 인증 가이드**: [JWT_IMPLEMENTATION_COMPLETE.md](/root/ansible-builder/JWT_IMPLEMENTATION_COMPLETE.md)

## API 엔드포인트

### Keycloak
- OpenID Configuration: `http://localhost:8080/realms/ansible-realm/.well-known/openid-configuration`
- Token Endpoint: `http://localhost:8080/realms/ansible-realm/protocol/openid-connect/token`
- UserInfo Endpoint: `http://localhost:8080/realms/ansible-realm/protocol/openid-connect/userinfo`
- JWKS: `http://localhost:8080/realms/ansible-realm/protocol/openid-connect/certs`

### Ansible Builder
- Keycloak Config: `http://localhost:8000/api/auth/keycloak-config`
- User Info: `http://localhost:8000/api/auth/me` (with Bearer token)
- Playbooks: `http://localhost:8000/api/playbooks` (with Bearer token)

## 환경 변수

### Backend (.env)
```bash
KEYCLOAK_SERVER_URL=http://localhost:8080
KEYCLOAK_REALM=ansible-realm
KEYCLOAK_CLIENT_ID=ansible-builder-client
```

### Frontend (.env)
```bash
REACT_APP_KEYCLOAK_URL=http://localhost:8080
REACT_APP_KEYCLOAK_REALM=ansible-realm
REACT_APP_KEYCLOAK_CLIENT_ID=ansible-builder-client
```

## 문제 해결

### Keycloak 컨테이너 실행 문제
```bash
docker-compose logs keycloak
docker-compose restart keycloak
```

### 토큰 검증 실패
- 시스템 시간 동기화 확인
- JWKS 캐시 초기화: 백엔드 재시작

### CORS 에러
- Keycloak Admin Console에서 Client의 Web Origins 설정 확인

## 프로덕션 배포

프로덕션 환경 배포 시:
1. ✅ HTTPS 적용 (Let's Encrypt)
2. ✅ 강력한 비밀번호 정책
3. ✅ 2FA 활성화
4. ✅ 세션 타임아웃 설정
5. ✅ IP 화이트리스트
6. ✅ 정기적인 보안 감사
7. ✅ 데이터베이스 백업 자동화

## 지원

문제가 발생하면:
1. [QUICKSTART.md](./QUICKSTART.md) 참조
2. [상세 가이드](/root/ansible-builder/KEYCLOAK_INTEGRATION_GUIDE.md) 확인
3. `./test-integration.sh` 실행하여 진단

## 라이선스

이 통합 구현은 기존 AWX와 Ansible Builder의 라이선스를 따릅니다.

---

**구현 완료**: Keycloak을 통한 AWX와 Ansible Builder의 통합 SSO 시스템
