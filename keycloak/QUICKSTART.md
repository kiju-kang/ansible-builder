# Keycloak 통합 빠른 시작 가이드

AWX와 Ansible Builder를 Keycloak SSO로 통합하는 빠른 시작 가이드입니다.

## 1단계: Keycloak 서버 시작

```bash
cd /root/keycloak
docker-compose up -d

# 로그 확인 (Keycloak이 시작될 때까지 대기)
docker-compose logs -f keycloak
```

**시작 완료 확인**: 다음 메시지가 나오면 준비 완료
```
Keycloak 23.0.0 started
Listening on: http://0.0.0.0:8080
```

웹 브라우저에서 접속 테스트: http://localhost:8080

## 2단계: Keycloak 자동 설정

```bash
cd /root/keycloak
./setup-keycloak.sh
```

이 스크립트가 자동으로 다음을 생성합니다:
- ✅ Realm: `ansible-realm`
- ✅ Clients: `awx-client`, `ansible-builder-client`
- ✅ Roles: `admin`, `user`, `awx-admin`, `awx-user`
- ✅ Users: `admin` (password: admin123), `testuser` (password: test123)

## 3단계: Ansible Builder 패키지 설치

```bash
cd /root/ansible-builder/ansible-builder/backend
pip install python-keycloak authlib python-jose[cryptography]

cd /root/ansible-builder/ansible-builder/frontend/frontend
npm install keycloak-js
```

## 4단계: 환경 변수 설정

### Backend `.env` 파일 생성

```bash
cat > /root/ansible-builder/ansible-builder/backend/.env << 'EOF'
# Keycloak 설정
KEYCLOAK_SERVER_URL=http://localhost:8080
KEYCLOAK_REALM=ansible-realm
KEYCLOAK_CLIENT_ID=ansible-builder-client
KEYCLOAK_CLIENT_SECRET=

# 기존 JWT 설정 (하위 호환성)
JWT_SECRET_KEY=your-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Database
DATABASE_URL=postgresql://awx:password@localhost:5432/awx
EOF
```

### Frontend `.env` 파일 생성

```bash
cat > /root/ansible-builder/ansible-builder/frontend/frontend/.env << 'EOF'
REACT_APP_KEYCLOAK_URL=http://localhost:8080
REACT_APP_KEYCLOAK_REALM=ansible-realm
REACT_APP_KEYCLOAK_CLIENT_ID=ansible-builder-client
EOF
```

## 5단계: Ansible Builder 백엔드 수정

`main.py`에 다음 코드를 추가해야 합니다:

```python
# Import 추가
from keycloak_auth import get_current_user_keycloak, get_optional_user_keycloak
from keycloak_config import (
    KEYCLOAK_SERVER_URL, KEYCLOAK_REALM, KEYCLOAK_CLIENT_ID,
    KEYCLOAK_AUTHORIZATION_URL, KEYCLOAK_TOKEN_URL, KEYCLOAK_LOGOUT_URL
)

# Keycloak 설정 엔드포인트 추가
@app.get("/api/auth/keycloak-config")
async def get_keycloak_config():
    return {
        "server_url": KEYCLOAK_SERVER_URL,
        "realm": KEYCLOAK_REALM,
        "client_id": KEYCLOAK_CLIENT_ID,
        "authorization_url": KEYCLOAK_AUTHORIZATION_URL,
        "token_url": KEYCLOAK_TOKEN_URL,
        "logout_url": KEYCLOAK_LOGOUT_URL
    }

# 통합 인증 함수
async def get_unified_user(
    db: Session = Depends(get_db),
    jwt_user: Optional[AnsibleBuilderUser] = Depends(get_optional_user),
    keycloak_user: Optional[AnsibleBuilderUser] = Depends(get_optional_user_keycloak)
) -> Optional[AnsibleBuilderUser]:
    return keycloak_user or jwt_user
```

그리고 기존 엔드포인트들의 `current_user` 파라미터를 `get_unified_user`로 변경합니다.

## 6단계: Ansible Builder 프론트엔드 수정

이미 생성된 파일들:
- ✅ `/root/ansible-builder/ansible-builder/frontend/frontend/src/keycloak.js`
- ✅ `/root/ansible-builder/ansible-builder/frontend/frontend/public/silent-check-sso.html`

`AuthContext.jsx`와 `Login.jsx`는 상세 가이드 문서를 참조하여 수정해야 합니다:
- [KEYCLOAK_INTEGRATION_GUIDE.md](/root/ansible-builder/KEYCLOAK_INTEGRATION_GUIDE.md)

## 7단계: 서비스 시작

### Backend 시작
```bash
cd /root/ansible-builder/ansible-builder/backend
python3 main.py
```

### Frontend 빌드 및 시작
```bash
cd /root/ansible-builder/ansible-builder/frontend/frontend
npm run build
```

## 8단계: 테스트

### 1. Keycloak Admin Console 접속
- URL: http://localhost:8080/admin
- Username: `admin`
- Password: `admin123`
- Realm: `ansible-realm`로 변경

### 2. Ansible Builder 접속
- URL: http://localhost:8000
- "Sign in with Keycloak SSO" 버튼 클릭
- Keycloak 로그인 페이지로 리다이렉트
- Username: `admin`, Password: `admin123` 입력
- Ansible Builder로 자동 로그인 확인

### 3. SSO 테스트
- Ansible Builder에서 로그인
- 새 탭에서 AWX 열기
- 자동으로 로그인되어 있는지 확인 (SSO)

## 9단계: AWX Keycloak 통합 (선택사항)

AWX에서 Keycloak 통합 설정:

1. AWX 웹 UI → Settings → Authentication → Generic OIDC
2. 다음 값 입력:
   ```python
   SOCIAL_AUTH_OIDC_OIDC_ENDPOINT = "http://localhost:8080/realms/ansible-realm"
   SOCIAL_AUTH_OIDC_KEY = "awx-client"
   SOCIAL_AUTH_OIDC_SECRET = "<setup-keycloak.sh에서 출력된 값>"
   SOCIAL_AUTH_OIDC_VERIFY_SSL = False
   ```

## 문제 해결

### Keycloak 서버가 시작되지 않음
```bash
# 로그 확인
docker-compose logs keycloak

# 컨테이너 재시작
docker-compose restart keycloak

# 완전 재시작
docker-compose down
docker-compose up -d
```

### 토큰 검증 실패
```bash
# JWKS 엔드포인트 확인
curl http://localhost:8080/realms/ansible-realm/protocol/openid-connect/certs

# 토큰 발급 테스트
curl -X POST http://localhost:8080/realms/ansible-realm/protocol/openid-connect/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id=ansible-builder-client" \
  -d "username=admin" \
  -d "password=admin123"
```

### CORS 에러
Keycloak Admin Console에서:
1. Clients → ansible-builder-client
2. Settings → Web origins: `+` 입력 (모든 origin 허용)
3. Save

## 다음 단계

1. ✅ Keycloak 설정 완료
2. ⏭ AuthContext.jsx 수정 (상세 가이드 참조)
3. ⏭ Login.jsx 수정 (상세 가이드 참조)
4. ⏭ main.py 수정 (상세 가이드 참조)
5. ⏭ 프로덕션 배포 준비 (HTTPS, 보안 강화)

## 참고 문서

- [상세 통합 가이드](/root/ansible-builder/KEYCLOAK_INTEGRATION_GUIDE.md)
- [Keycloak Documentation](https://www.keycloak.org/documentation)
- [AWX OIDC Configuration](https://github.com/ansible/awx/blob/devel/docs/auth/oidc.md)
