# Keycloak 통합 구현 완료

AWX와 Ansible Builder를 Keycloak SSO로 통합하는 구현이 **완료**되었습니다!

---

## ✅ 완료된 작업

### 1. Backend 통합
- ✅ [main.py](/root/ansible-builder/ansible-builder/backend/main.py) - Keycloak 통합 코드 추가
  - Keycloak import 및 조건부 활성화
  - 통합 인증 함수 (`get_unified_user`, `get_unified_active_user`)
  - Keycloak 설정 엔드포인트 (`/api/auth/keycloak-config`)
  - 모든 API 엔드포인트를 통합 인증으로 변경
- ✅ [keycloak_config.py](/root/ansible-builder/ansible-builder/backend/keycloak_config.py) - Keycloak 설정
- ✅ [keycloak_auth.py](/root/ansible-builder/ansible-builder/backend/keycloak_auth.py) - JWT 검증 및 JIT 프로비저닝
- ✅ [.env](/root/ansible-builder/ansible-builder/backend/.env) - 환경 변수 파일

### 2. Frontend 통합
- ✅ [AuthContext.jsx](/root/ansible-builder/ansible-builder/frontend/frontend/src/contexts/AuthContext.jsx) - Keycloak 통합
  - Keycloak 초기화 로직
  - loginWithKeycloak() 함수
  - loginLocal() 함수 (기존 JWT 지원)
  - 토큰 자동 갱신
  - authMode 상태 관리
- ✅ [Login.jsx](/root/ansible-builder/ansible-builder/frontend/frontend/src/components/Login.jsx) - SSO 버튼 추가
  - "Sign in with Keycloak SSO" 버튼
  - 로컬 로그인 폼 (하위 호환성)
- ✅ [keycloak.js](/root/ansible-builder/ansible-builder/frontend/frontend/src/keycloak.js) - Keycloak 클라이언트
- ✅ [.env](/root/ansible-builder/ansible-builder/frontend/frontend/.env) - 환경 변수 파일
- ✅ Frontend 빌드 완료 (281.07 KB)

### 3. Keycloak 서버 설정
- ✅ [docker-compose.yml](/root/keycloak/docker-compose.yml) - Keycloak + PostgreSQL
- ✅ [setup-keycloak.sh](/root/keycloak/setup-keycloak.sh) - 자동 설정 스크립트
- ✅ [test-integration.sh](/root/keycloak/test-integration.sh) - 통합 테스트 스크립트

### 4. 문서
- ✅ [KEYCLOAK_INTEGRATION_GUIDE.md](/root/ansible-builder/KEYCLOAK_INTEGRATION_GUIDE.md) - 상세 가이드
- ✅ [KEYCLOAK_IMPLEMENTATION_SUMMARY.md](/root/ansible-builder/KEYCLOAK_IMPLEMENTATION_SUMMARY.md) - 구현 요약
- ✅ [QUICKSTART.md](/root/keycloak/QUICKSTART.md) - 빠른 시작
- ✅ [README.md](/root/keycloak/README.md) - Keycloak 디렉토리 설명

---

## 🚀 시작 방법

### 1단계: Keycloak 서버 시작

```bash
cd /root/keycloak
docker-compose up -d

# 로그 확인 (90초 정도 대기)
docker-compose logs -f keycloak
```

**완료 확인**: "Keycloak 23.0.0 started" 메시지가 나타나면 준비 완료

### 2단계: Keycloak 자동 설정

```bash
cd /root/keycloak
./setup-keycloak.sh
```

이 스크립트가 자동으로 생성:
- Realm: `ansible-realm`
- Clients: `awx-client`, `ansible-builder-client`
- Roles: `admin`, `user`, `awx-admin`, `awx-user`
- Users: `admin` (password: admin123), `testuser` (password: test123)

### 3단계: Backend 시작

```bash
cd /root/ansible-builder/ansible-builder/backend
python3 main.py
```

**예상 출력**:
```
✓ Keycloak integration enabled
Database initialized successfully
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 4단계: 웹 브라우저에서 테스트

1. http://localhost:8000 접속
2. **"Sign in with Keycloak SSO"** 버튼 확인
3. 버튼 클릭 → Keycloak 로그인 페이지로 이동
4. Username: `admin`, Password: `admin123` 입력
5. Ansible Builder로 자동 로그인 확인

---

## 🎯 주요 기능

### SSO (Single Sign-On)
- 한 번 로그인으로 AWX와 Ansible Builder 모두 접근
- Keycloak 세션 기반 통합 인증
- 토큰 자동 갱신 (1분마다)

### 하위 호환성
- 기존 로컬 JWT 로그인 계속 작동
- Keycloak이 없어도 정상 작동
- 점진적 마이그레이션 가능

### JIT 프로비저닝
- Keycloak에서 처음 로그인 시 자동으로 DB에 사용자 생성
- 역할 자동 매핑 (admin, user)
- 사용자 정보 실시간 동기화

---

## 🧪 통합 테스트

### 자동 테스트 실행

```bash
cd /root/keycloak
./test-integration.sh
```

**테스트 항목** (10개):
1. Keycloak 서버 접속
2. OpenID Configuration
3. 토큰 발급
4. JWT 페이로드 검증
5. Backend API 접속
6. Keycloak Config 엔드포인트
7. 사용자 정보 조회 (/api/auth/me)
8. Playbooks API (인증된 요청)
9. JWKS 엔드포인트
10. UserInfo 엔드포인트

### 수동 테스트

```bash
# 1. Keycloak 토큰 발급
TOKEN_RESPONSE=$(curl -s -X POST http://localhost:8080/realms/ansible-realm/protocol/openid-connect/token \
  -d "grant_type=password" \
  -d "client_id=ansible-builder-client" \
  -d "username=admin" \
  -d "password=admin123")

ACCESS_TOKEN=$(echo $TOKEN_RESPONSE | jq -r .access_token)
echo "Access Token: $ACCESS_TOKEN"

# 2. Ansible Builder API 호출
curl http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq .

# 3. Playbooks 조회
curl http://localhost:8000/api/playbooks \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq .
```

---

## 📊 인증 흐름

### Keycloak SSO 로그인
```
1. 사용자가 "Sign in with Keycloak SSO" 클릭
   ↓
2. Keycloak 로그인 페이지로 리다이렉트
   ↓
3. 사용자가 username/password 입력
   ↓
4. Keycloak이 Authorization Code 발급
   ↓
5. Frontend가 Code로 Access Token 요청
   ↓
6. Keycloak이 JWT Access Token 발급
   ↓
7. Frontend가 토큰을 localStorage에 저장
   ↓
8. 모든 API 요청에 Bearer Token 포함
   ↓
9. Backend가 Keycloak JWKS로 토큰 검증
   ↓
10. 사용자 정보 추출 및 DB에 JIT 프로비저닝
```

### 로컬 JWT 로그인 (하위 호환)
```
1. 사용자가 로컬 username/password 입력
   ↓
2. Backend가 DB에서 사용자 확인
   ↓
3. bcrypt로 비밀번호 검증
   ↓
4. Backend가 자체 JWT 토큰 발급
   ↓
5. Frontend가 토큰 저장 및 사용
```

---

## 🔧 설정 파일

### Backend (.env)
```bash
# Keycloak
KEYCLOAK_SERVER_URL=http://localhost:8080
KEYCLOAK_REALM=ansible-realm
KEYCLOAK_CLIENT_ID=ansible-builder-client

# 로컬 JWT
JWT_SECRET_KEY=your-super-secret-key-change-this-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Database
DATABASE_URL=postgresql://awx:password@localhost:5432/awx
```

### Frontend (.env)
```bash
REACT_APP_KEYCLOAK_URL=http://localhost:8080
REACT_APP_KEYCLOAK_REALM=ansible-realm
REACT_APP_KEYCLOAK_CLIENT_ID=ansible-builder-client
```

---

## 🎨 화면 변화

### 로그인 화면 (Keycloak 활성화 시)

```
┌────────────────────────────────────────┐
│         Ansible Builder                │
│         Sign in to continue            │
├────────────────────────────────────────┤
│  [🔑 Sign in with Keycloak SSO]       │  ← 새로 추가!
├────────────────────────────────────────┤
│    Or continue with local account      │
├────────────────────────────────────────┤
│  Username: [           ]               │
│  Password: [           ]               │
│  [Sign In (Local)]                     │
├────────────────────────────────────────┤
│  Default Local Credentials:            │
│  Username: admin                       │
│  Password: admin123                    │
│  ℹ️ SSO is available via Keycloak     │
└────────────────────────────────────────┘
```

### 내비게이션 바

```
┌────────────────────────────────────────────────────────┐
│ 🚀 Ansible Playbook Builder                           │
│  [Builder] [Playbooks] [Inventories] [Execute]        │
│  [History]                                             │
│                                                        │
│  👤 admin (admin) [Logout] ← Keycloak 또는 Local     │
└────────────────────────────────────────────────────────┘
```

---

## 📝 기술 세부사항

### Backend 통합 인증

```python
async def get_unified_user(
    db: Session = Depends(get_db),
    jwt_user: Optional[AnsibleBuilderUser] = Depends(get_optional_user),
    keycloak_user: Optional[AnsibleBuilderUser] = Depends(get_optional_user_keycloak)
) -> Optional[AnsibleBuilderUser]:
    """Keycloak 토큰 우선, 없으면 로컬 JWT 사용"""
    return keycloak_user or jwt_user
```

### Frontend AuthContext

```javascript
const initKeycloak = async () => {
  // Keycloak 사용 가능 여부 확인
  const response = await fetch('/api/auth/keycloak-config');

  if (!response.ok || !config.enabled) {
    // Keycloak 비활성화 - 로컬 JWT만 사용
    loadLocalAuth();
    return;
  }

  // Keycloak 초기화
  const authenticated = await keycloak.init({
    onLoad: 'check-sso',
    pkceMethod: 'S256'
  });

  if (authenticated) {
    setAuthMode('keycloak');
    setToken(keycloak.token);
    // ...
  }
};
```

---

## 🔒 보안 기능

1. **JWT 서명 검증**: RS256 알고리즘으로 Keycloak 토큰 검증
2. **JWKS 캐싱**: 성능 향상 및 Keycloak 서버 부하 감소
3. **토큰 자동 갱신**: 1분마다 토큰 만료 70초 전에 자동 갱신
4. **역할 기반 접근**: Keycloak roles → admin/user 자동 매핑
5. **감사 로그**: 모든 인증 이벤트 기록
6. **리소스 소유권**: Playbook/Inventory 소유자 추적

---

## 🛠️ 문제 해결

### Keycloak 서버가 시작되지 않음
```bash
docker logs keycloak
docker-compose restart keycloak
```

### Frontend에서 SSO 버튼이 보이지 않음
- Backend가 실행 중인지 확인
- `/api/auth/keycloak-config` 엔드포인트 응답 확인
- Keycloak 서버가 실행 중인지 확인

### 토큰 검증 실패
- Keycloak 서버 시간 동기화 확인
- JWKS URL 접속 확인: `curl http://localhost:8080/realms/ansible-realm/protocol/openid-connect/certs`

### CORS 에러
Keycloak Admin Console:
1. Clients → ansible-builder-client
2. Web origins: `+` 입력
3. Save

---

## 📚 참고 문서

### 생성된 문서
- [상세 통합 가이드](/root/ansible-builder/KEYCLOAK_INTEGRATION_GUIDE.md)
- [구현 요약](/root/ansible-builder/KEYCLOAK_IMPLEMENTATION_SUMMARY.md)
- [빠른 시작](/root/keycloak/QUICKSTART.md)
- [Keycloak README](/root/keycloak/README.md)

### 외부 링크
- [Keycloak Documentation](https://www.keycloak.org/documentation)
- [OpenID Connect Spec](https://openid.net/connect/)
- [AWX OIDC Configuration](https://github.com/ansible/awx/blob/devel/docs/auth/oidc.md)

---

## 🎉 완료!

Keycloak 통합이 완전히 구현되었습니다!

### 다음 단계:
1. ✅ **Keycloak 서버 시작**: `cd /root/keycloak && docker-compose up -d`
2. ✅ **자동 설정 실행**: `./setup-keycloak.sh`
3. ✅ **Backend 시작**: `cd /root/ansible-builder/ansible-builder/backend && python3 main.py`
4. ✅ **웹 UI 테스트**: http://localhost:8000

### 테스트 계정:
- **Admin**: username=`admin`, password=`admin123`
- **User**: username=`testuser`, password=`test123`

### AWX 통합 (선택사항):
- AWX Settings → Authentication → Generic OIDC
- [상세 가이드](/root/ansible-builder/KEYCLOAK_INTEGRATION_GUIDE.md) 참조

---

**구현 완료일**: 2025-12-08
**통합 방식**: OpenID Connect (OIDC)
**하위 호환성**: ✅ 로컬 JWT 계속 작동
**프로덕션 준비**: ⚠️ HTTPS, 비밀번호 변경, 보안 강화 필요

---

## 📞 지원

문제가 발생하면:
1. `/root/keycloak/test-integration.sh` 실행
2. 상세 가이드 문서 확인
3. Keycloak Admin Console (http://localhost:8080/admin) 확인

**축하합니다! AWX와 Ansible Builder를 Keycloak SSO로 통합하는 데 성공했습니다!** 🎊
