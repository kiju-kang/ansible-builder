# Keycloak SSO 통합 설정 완료

## 서비스 현황

### 실행 중인 서비스
1. **Keycloak SSO Server**: http://192.168.64.26:8080
2. **Ansible Builder Backend**: http://192.168.64.26:8000
3. **PostgreSQL Port-Forward**: localhost:5432 → Kubernetes AWX PostgreSQL

## Keycloak 설정 정보

### Realm 정보
- **Realm 이름**: ansible-realm
- **Admin Console**: http://192.168.64.26:8080/admin
- **Admin 계정**: admin / admin123

### 클라이언트 설정

#### 1. AWX Client
- **Client ID**: awx-client
- **Client Secret**: awx-secret-key
- **Redirect URIs**: http://192.168.64.26:8000/*, http://localhost:8000/*
- **Web Origins**: http://192.168.64.26:8000, http://localhost:8000
- **사용 목적**: AWX 백엔드 인증

#### 2. Ansible Builder Client
- **Client ID**: ansible-builder-client
- **Client Type**: Public (프론트엔드용)
- **Redirect URIs**: http://192.168.64.26:3000/*, http://192.168.64.26:8000/*, http://localhost:3000/*, http://localhost:8000/*
- **Web Origins**: All ('+')
- **사용 목적**: Ansible Builder 프론트엔드 인증

### Realm Roles
- **admin**: 관리자 권한
- **user**: 일반 사용자 권한
- **awx-admin**: AWX 관리자 권한
- **awx-user**: AWX 사용자 권한

### 테스트 계정

#### 1. Admin 계정
- **Username**: admin
- **Password**: admin123
- **Email**: admin@example.com
- **Roles**: admin, awx-admin

#### 2. Test User 계정
- **Username**: testuser
- **Password**: test123
- **Email**: testuser@example.com
- **Roles**: user, awx-user

## 애플리케이션 접속 방법

### Ansible Builder Web UI
1. 브라우저에서 **http://192.168.64.26:8000** 접속
2. 로그인 화면에서 두 가지 방식으로 로그인 가능:
   - **Keycloak SSO**: "Sign in with Keycloak SSO" 버튼 클릭
   - **Local JWT**: 기존 로컬 계정으로 로그인 (admin/admin123)

### Keycloak Admin Console
1. 브라우저에서 **http://192.168.64.26:8080/admin** 접속
2. Realm 선택: **ansible-realm**
3. Admin 계정으로 로그인: admin / admin123

## 인증 흐름

### Keycloak SSO 로그인
1. 사용자가 "Sign in with Keycloak SSO" 버튼 클릭
2. Keycloak 로그인 페이지로 리다이렉트
3. Keycloak에서 인증 성공 후 토큰 발급
4. 애플리케이션으로 리다이렉트하여 자동 로그인
5. JIT(Just-In-Time) 프로비저닝: 최초 로그인 시 자동으로 로컬 DB에 사용자 생성

### Local JWT 로그인
- 기존 방식 그대로 유지 (하위 호환성)
- Keycloak 없이도 동작 가능

## 환경 변수 설정

### Backend (.env)
```bash
KEYCLOAK_SERVER_URL=http://192.168.64.26:8080
KEYCLOAK_REALM=ansible-realm
KEYCLOAK_CLIENT_ID=ansible-builder-client
KEYCLOAK_CLIENT_SECRET=

JWT_SECRET_KEY=your-super-secret-key-change-this-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=1440

DATABASE_URL=postgresql://awx:password@localhost:5432/awx
```

### Frontend (.env)
```bash
REACT_APP_KEYCLOAK_URL=http://192.168.64.26:8080
REACT_APP_KEYCLOAK_REALM=ansible-realm
REACT_APP_KEYCLOAK_CLIENT_ID=ansible-builder-client
```

## 다음 단계: AWX Keycloak 통합

### AWX에 Keycloak 설정 추가
1. AWX Admin Console에 로그인
2. Settings → Authentication → SAML/OIDC 설정으로 이동
3. 아래 정보 입력:
   - **Authorization URL**: http://192.168.64.26:8080/realms/ansible-realm/protocol/openid-connect/auth
   - **Token URL**: http://192.168.64.26:8080/realms/ansible-realm/protocol/openid-connect/token
   - **User Info URL**: http://192.168.64.26:8080/realms/ansible-realm/protocol/openid-connect/userinfo
   - **Client ID**: awx-client
   - **Client Secret**: awx-secret-key
   - **Logout URL**: http://192.168.64.26:8080/realms/ansible-realm/protocol/openid-connect/logout

## 서비스 관리 명령어

### Keycloak 서버
```bash
# 시작
cd /root/keycloak && docker compose up -d

# 중지
cd /root/keycloak && docker compose down

# 로그 확인
docker logs keycloak -f

# 상태 확인
docker ps | grep keycloak
```

### Backend 서버
```bash
# 시작
cd /root/ansible-builder/ansible-builder/backend
python3 main.py > /tmp/backend.log 2>&1 &

# 중지
pkill -f "python3 main.py"

# 로그 확인
tail -f /tmp/backend.log
```

### PostgreSQL Port-Forward
```bash
# 시작
kubectl port-forward -n awx awx-postgres-15-0 5432:5432 > /tmp/postgres-port-forward.log 2>&1 &

# 중지
pkill -f "kubectl port-forward.*postgres"

# 상태 확인
ps aux | grep "kubectl port-forward"
```

## 보안 고려사항

### 프로덕션 환경 적용 시
1. **HTTPS 설정 필수**:
   - HTTP 환경에서는 Web Crypto API 제한으로 PKCE를 사용할 수 없음
   - 프로덕션에서는 반드시 HTTPS + PKCE 사용

2. **기본 비밀번호 변경**:
   - Keycloak admin 계정 비밀번호 변경
   - 로컬 JWT admin 계정 비밀번호 변경
   - Client Secret 변경

3. **JWT Secret Key 변경**:
   - .env 파일의 JWT_SECRET_KEY를 안전한 값으로 변경

4. **Database 접근 제어**:
   - 현재는 port-forward 사용 중
   - 프로덕션에서는 적절한 네트워크 정책 설정

## 문제 해결

### Keycloak 연결 실패 시
```bash
# Keycloak 헬스 체크
curl http://192.168.64.26:8080/health/ready

# 재시작
cd /root/keycloak && docker compose restart keycloak
```

### Backend 데이터베이스 연결 실패 시
```bash
# PostgreSQL port-forward 상태 확인
ps aux | grep "kubectl port-forward"

# port-forward 재시작
pkill -f "kubectl port-forward.*postgres"
kubectl port-forward -n awx awx-postgres-15-0 5432:5432 > /tmp/postgres-port-forward.log 2>&1 &
```

## 참고 문서
- Keycloak 통합 가이드: /root/ansible-builder/KEYCLOAK_INTEGRATION_GUIDE.md
- Keycloak 퀵스타트: /root/keycloak/QUICKSTART.md
- 설정 스크립트: /root/keycloak/setup-keycloak.sh
- 통합 테스트: /root/keycloak/test-integration.sh

---

**설정 완료 일시**: 2025-12-08
**Keycloak 버전**: 23.0
**설정 상태**: ✓ 완료
