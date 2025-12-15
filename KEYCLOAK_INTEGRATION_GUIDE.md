# Keycloak 통합 가이드
## AWX + Ansible Builder SSO 구현

이 가이드는 Keycloak을 사용하여 AWX와 Ansible Builder를 통합 인증 시스템으로 구성하는 방법을 설명합니다.

---

## 📋 목차
1. [아키텍처 개요](#아키텍처-개요)
2. [Keycloak 서버 설치](#keycloak-서버-설치)
3. [Keycloak 설정](#keycloak-설정)
4. [AWX Keycloak 통합](#awx-keycloak-통합)
5. [Ansible Builder 백엔드 통합](#ansible-builder-백엔드-통합)
6. [Ansible Builder 프론트엔드 통합](#ansible-builder-프론트엔드-통합)
7. [테스트 및 검증](#테스트-및-검증)

---

## 아키텍처 개요

```
┌─────────────────────────────────────────────────────────┐
│                    Keycloak Server                       │
│                  (Identity Provider)                     │
│  - User Management                                       │
│  - Role Management                                       │
│  - SSO Token Management                                  │
└──────────────┬──────────────────────┬────────────────────┘
               │                      │
               │ OIDC                 │ OIDC
               ▼                      ▼
    ┌──────────────────┐   ┌──────────────────────┐
    │       AWX        │   │  Ansible Builder     │
    │   (Service 1)    │   │   (Service 2)        │
    │                  │   │                      │
    │  - OIDC Auth     │   │  - OIDC Auth         │
    │  - Auto User     │   │  - JWT Validation    │
    │    Provisioning  │   │  - Role Mapping      │
    └──────────────────┘   └──────────────────────┘
```

### 통합 방식
- **프로토콜**: OpenID Connect (OIDC)
- **인증 흐름**: Authorization Code Flow with PKCE
- **토큰 형식**: JWT
- **사용자 프로비저닝**: JIT (Just-In-Time)

---

## Keycloak 서버 설치

### 1. Docker Compose로 Keycloak 설치

```bash
# Keycloak 디렉토리 생성
mkdir -p /root/keycloak
cd /root/keycloak
```

`docker-compose.yml` 파일 생성:

```yaml
version: '3.8'

services:
  keycloak-db:
    image: postgres:15
    container_name: keycloak-postgres
    environment:
      POSTGRES_DB: keycloak
      POSTGRES_USER: keycloak
      POSTGRES_PASSWORD: keycloak_password
    volumes:
      - keycloak_db_data:/var/lib/postgresql/data
    networks:
      - keycloak-network
    restart: unless-stopped

  keycloak:
    image: quay.io/keycloak/keycloak:23.0
    container_name: keycloak
    environment:
      KC_DB: postgres
      KC_DB_URL: jdbc:postgresql://keycloak-db:5432/keycloak
      KC_DB_USERNAME: keycloak
      KC_DB_PASSWORD: keycloak_password
      KC_HOSTNAME: localhost
      KC_HOSTNAME_PORT: 8080
      KC_HOSTNAME_STRICT: false
      KC_HOSTNAME_STRICT_HTTPS: false
      KC_HTTP_ENABLED: true
      KC_HEALTH_ENABLED: true
      KEYCLOAK_ADMIN: admin
      KEYCLOAK_ADMIN_PASSWORD: admin123
    ports:
      - "8080:8080"
    depends_on:
      - keycloak-db
    networks:
      - keycloak-network
    command: start-dev
    restart: unless-stopped

volumes:
  keycloak_db_data:

networks:
  keycloak-network:
    driver: bridge
```

### 2. Keycloak 시작

```bash
cd /root/keycloak
docker-compose up -d

# 로그 확인
docker-compose logs -f keycloak
```

Keycloak 접속: http://localhost:8080
- Admin Username: `admin`
- Admin Password: `admin123`

---

## Keycloak 설정

### 1. Realm 생성

1. Keycloak Admin Console 접속 (http://localhost:8080)
2. 좌측 상단 "Master" 드롭다운 → "Create Realm" 클릭
3. Realm 설정:
   - **Realm name**: `ansible-realm`
   - **Enabled**: ON
4. "Create" 클릭

### 2. Client 생성 - AWX

1. 좌측 메뉴 "Clients" → "Create client"
2. **General Settings**:
   - **Client type**: OpenID Connect
   - **Client ID**: `awx-client`
3. **Capability config**:
   - **Client authentication**: ON
   - **Authorization**: OFF
   - **Authentication flow**:
     - ✅ Standard flow
     - ✅ Direct access grants
4. **Login settings**:
   - **Root URL**: `http://localhost:8000`
   - **Valid redirect URIs**: `http://localhost:8000/*`
   - **Web origins**: `http://localhost:8000`
5. "Save" 클릭

### 3. Client 생성 - Ansible Builder

1. 좌측 메뉴 "Clients" → "Create client"
2. **General Settings**:
   - **Client type**: OpenID Connect
   - **Client ID**: `ansible-builder-client`
3. **Capability config**:
   - **Client authentication**: OFF (Public client)
   - **Authorization**: OFF
   - **Authentication flow**:
     - ✅ Standard flow
     - ✅ Direct access grants
4. **Login settings**:
   - **Root URL**: `http://localhost:3000`
   - **Valid redirect URIs**:
     - `http://localhost:3000/*`
     - `http://localhost:8000/*`
   - **Web origins**: `+`
5. "Save" 클릭

### 4. Client Credentials 저장

**AWX Client Secret**:
1. "Clients" → "awx-client" → "Credentials" 탭
2. **Client secret** 복사 및 저장

**Ansible Builder**는 Public Client이므로 Secret 불필요

### 5. Roles 생성

1. 좌측 메뉴 "Realm roles" → "Create role"
2. 다음 Role들 생성:
   - **admin**: 관리자 역할
   - **user**: 일반 사용자 역할
   - **awx-admin**: AWX 관리자
   - **awx-user**: AWX 사용자

### 6. 테스트 사용자 생성

1. 좌측 메뉴 "Users" → "Add user"
2. **User 1 (Admin)**:
   - **Username**: `admin`
   - **Email**: `admin@example.com`
   - **First name**: `Admin`
   - **Last name**: `User`
   - **Email verified**: ON
3. "Create" 클릭
4. **Credentials** 탭:
   - **Password**: `admin123`
   - **Password confirmation**: `admin123`
   - **Temporary**: OFF
5. **Role mapping** 탭:
   - "Assign role" 클릭
   - `admin`, `awx-admin` 역할 할당

6. **User 2 (일반 사용자)**:
   - Username: `testuser`
   - Password: `test123`
   - Role: `user`, `awx-user`

### 7. Client Scopes 설정

1. "Clients" → "ansible-builder-client" → "Client scopes" 탭
2. "ansible-builder-client-dedicated" 클릭
3. "Add mapper" → "By configuration" → "User Attribute"
4. **Mapper 생성**:
   - **Name**: `role`
   - **User Attribute**: `role`
   - **Token Claim Name**: `role`
   - **Claim JSON Type**: String
   - **Add to ID token**: ON
   - **Add to access token**: ON
   - **Add to userinfo**: ON

---

## AWX Keycloak 통합

### 1. AWX Settings에서 OIDC 설정

1. AWX 웹 UI 접속
2. Settings → Authentication → Generic OIDC
3. 다음 설정 입력:

```python
SOCIAL_AUTH_OIDC_OIDC_ENDPOINT = "http://localhost:8080/realms/ansible-realm"
SOCIAL_AUTH_OIDC_KEY = "awx-client"
SOCIAL_AUTH_OIDC_SECRET = "<awx-client-secret>"  # Keycloak에서 복사한 값

SOCIAL_AUTH_OIDC_VERIFY_SSL = False  # 개발 환경용
```

### 2. AWX Organization 및 Team 매핑

Settings → System → (고급 설정에서):

```python
# 자동 사용자 프로비저닝
SOCIAL_AUTH_OIDC_AUTO_CREATE_USERS = True

# Role 매핑
SOCIAL_AUTH_OIDC_ORGANIZATION_MAP = {
    "Default": {
        "users": True
    }
}

SOCIAL_AUTH_OIDC_TEAM_MAP = {
    "Admins": {
        "organization": "Default",
        "users": "/^.*@example\\.com$/",
        "remove": False
    }
}
```

---

## Ansible Builder 백엔드 통합

### 1. 필요한 패키지 설치

```bash
cd /root/ansible-builder/ansible-builder/backend
pip install python-keycloak authlib python-jose[cryptography]
```

### 2. Keycloak 설정 파일 생성

`keycloak_config.py` 파일 생성:

```python
import os

# Keycloak 서버 설정
KEYCLOAK_SERVER_URL = os.getenv("KEYCLOAK_SERVER_URL", "http://localhost:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "ansible-realm")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "ansible-builder-client")
KEYCLOAK_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", "")  # Public client는 비어있음

# OIDC 엔드포인트
KEYCLOAK_WELL_KNOWN_URL = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/.well-known/openid-configuration"
KEYCLOAK_TOKEN_URL = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
KEYCLOAK_USERINFO_URL = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/userinfo"
KEYCLOAK_JWKS_URL = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
KEYCLOAK_AUTHORIZATION_URL = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/auth"
KEYCLOAK_LOGOUT_URL = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/logout"

# JWT 검증 설정
KEYCLOAK_ALGORITHMS = ["RS256"]
KEYCLOAK_AUDIENCE = KEYCLOAK_CLIENT_ID
KEYCLOAK_ISSUER = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}"
```

### 3. Keycloak 인증 모듈 생성

`keycloak_auth.py` 파일 생성:

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.orm import Session
import requests
from typing import Optional
from database import get_db, AnsibleBuilderUser
from keycloak_config import (
    KEYCLOAK_JWKS_URL, KEYCLOAK_ALGORITHMS,
    KEYCLOAK_AUDIENCE, KEYCLOAK_ISSUER, KEYCLOAK_USERINFO_URL
)

security = HTTPBearer()

# JWKS 캐시 (성능 향상)
_jwks_cache = None

def get_jwks():
    """Keycloak의 JWKS(JSON Web Key Set) 가져오기"""
    global _jwks_cache
    if _jwks_cache is None:
        response = requests.get(KEYCLOAK_JWKS_URL)
        response.raise_for_status()
        _jwks_cache = response.json()
    return _jwks_cache

def verify_keycloak_token(token: str) -> dict:
    """Keycloak JWT 토큰 검증"""
    try:
        # JWKS에서 공개 키 가져오기
        jwks = get_jwks()

        # JWT 헤더에서 kid (key id) 추출
        unverified_header = jwt.get_unverified_header(token)

        # JWKS에서 해당 kid의 키 찾기
        rsa_key = {}
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"]
                }
                break

        if not rsa_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to find appropriate key"
            )

        # JWT 검증
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=KEYCLOAK_ALGORITHMS,
            audience=KEYCLOAK_AUDIENCE,
            issuer=KEYCLOAK_ISSUER
        )

        return payload

    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )

def get_or_create_user_from_keycloak(payload: dict, db: Session) -> AnsibleBuilderUser:
    """Keycloak 토큰에서 사용자 정보 추출 및 DB에 생성/업데이트"""
    username = payload.get("preferred_username")
    email = payload.get("email", f"{username}@example.com")

    # Role 추출 (realm_access 또는 custom claim에서)
    roles = payload.get("realm_access", {}).get("roles", [])
    role = "admin" if "admin" in roles else "user"

    # DB에서 사용자 조회
    user = db.query(AnsibleBuilderUser).filter(
        AnsibleBuilderUser.username == username
    ).first()

    if user:
        # 기존 사용자 업데이트
        user.email = email
        user.role = role
        user.is_active = True
        db.commit()
        db.refresh(user)
    else:
        # 새 사용자 생성
        user = AnsibleBuilderUser(
            username=username,
            email=email,
            hashed_password="",  # Keycloak에서 관리하므로 비어있음
            full_name=payload.get("name", username),
            role=role,
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return user

async def get_current_user_keycloak(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[AnsibleBuilderUser]:
    """Keycloak 토큰으로 현재 사용자 가져오기"""
    token = credentials.credentials

    # 토큰 검증
    payload = verify_keycloak_token(token)

    # 사용자 정보 가져오기 또는 생성
    user = get_or_create_user_from_keycloak(payload, db)

    return user

async def get_optional_user_keycloak(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
) -> Optional[AnsibleBuilderUser]:
    """선택적 Keycloak 인증 (토큰이 없어도 OK)"""
    if not credentials:
        return None

    try:
        return await get_current_user_keycloak(credentials, db)
    except:
        return None
```

### 4. main.py 수정 - Keycloak 인증 통합

`main.py`에서 기존 JWT 인증과 Keycloak 인증을 함께 지원하도록 수정:

```python
# keycloak_auth import 추가
from keycloak_auth import (
    get_current_user_keycloak,
    get_optional_user_keycloak,
    verify_keycloak_token
)
from keycloak_config import (
    KEYCLOAK_SERVER_URL, KEYCLOAK_REALM,
    KEYCLOAK_CLIENT_ID, KEYCLOAK_AUTHORIZATION_URL,
    KEYCLOAK_TOKEN_URL, KEYCLOAK_LOGOUT_URL
)

# Keycloak 설정 정보 제공 엔드포인트
@app.get("/api/auth/keycloak-config")
async def get_keycloak_config():
    """프론트엔드에서 사용할 Keycloak 설정 반환"""
    return {
        "server_url": KEYCLOAK_SERVER_URL,
        "realm": KEYCLOAK_REALM,
        "client_id": KEYCLOAK_CLIENT_ID,
        "authorization_url": KEYCLOAK_AUTHORIZATION_URL,
        "token_url": KEYCLOAK_TOKEN_URL,
        "logout_url": KEYCLOAK_LOGOUT_URL
    }

# 통합 인증 함수 (기존 JWT + Keycloak)
async def get_unified_user(
    db: Session = Depends(get_db),
    jwt_user: Optional[AnsibleBuilderUser] = Depends(get_optional_user),  # 기존 JWT
    keycloak_user: Optional[AnsibleBuilderUser] = Depends(get_optional_user_keycloak)  # Keycloak
) -> Optional[AnsibleBuilderUser]:
    """기존 JWT 또는 Keycloak 토큰 모두 지원"""
    return keycloak_user or jwt_user

# 기존 엔드포인트들의 인증을 get_unified_user로 변경
@app.post("/api/playbooks", response_model=Playbook)
async def create_playbook(
    playbook: Playbook,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[AnsibleBuilderUser] = Depends(get_unified_user)  # 통합 인증
):
    # 기존 로직 유지
    ...
```

---

## Ansible Builder 프론트엔드 통합

### 1. 필요한 패키지 설치

```bash
cd /root/ansible-builder/ansible-builder/frontend/frontend
npm install keycloak-js
```

### 2. Keycloak 클라이언트 설정

`src/keycloak.js` 파일 생성:

```javascript
import Keycloak from 'keycloak-js';

// Keycloak 인스턴스 생성
const keycloak = new Keycloak({
  url: 'http://localhost:8080',
  realm: 'ansible-realm',
  clientId: 'ansible-builder-client'
});

export default keycloak;
```

### 3. AuthContext 수정 - Keycloak 통합

`src/contexts/AuthContext.jsx` 수정:

```javascript
import React, { createContext, useContext, useState, useEffect } from 'react';
import keycloak from '../keycloak';

const AuthContext = createContext(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);
  const [authMode, setAuthMode] = useState('local'); // 'local' or 'keycloak'

  useEffect(() => {
    // Keycloak 초기화 시도
    keycloak.init({
      onLoad: 'check-sso',
      silentCheckSsoRedirectUri: window.location.origin + '/silent-check-sso.html',
      pkceMethod: 'S256'
    }).then(authenticated => {
      if (authenticated) {
        // Keycloak 인증됨
        setAuthMode('keycloak');
        setToken(keycloak.token);

        // 사용자 정보 가져오기
        keycloak.loadUserProfile().then(profile => {
          const userData = {
            id: profile.id,
            username: profile.username,
            email: profile.email,
            full_name: `${profile.firstName} ${profile.lastName}`,
            role: keycloak.hasRealmRole('admin') ? 'admin' : 'user'
          };
          setUser(userData);
          localStorage.setItem('user', JSON.stringify(userData));
          localStorage.setItem('auth_mode', 'keycloak');
        });

        // 토큰 자동 갱신
        setInterval(() => {
          keycloak.updateToken(70).then(refreshed => {
            if (refreshed) {
              setToken(keycloak.token);
            }
          }).catch(() => {
            console.error('Failed to refresh token');
          });
        }, 60000); // 1분마다 체크

      } else {
        // Keycloak 인증 안됨 - 로컬 JWT 확인
        const savedToken = localStorage.getItem('access_token');
        const savedUser = localStorage.getItem('user');
        const savedAuthMode = localStorage.getItem('auth_mode');

        if (savedToken && savedUser && savedAuthMode === 'local') {
          setAuthMode('local');
          setToken(savedToken);
          setUser(JSON.parse(savedUser));
        }
      }

      setLoading(false);
    }).catch(error => {
      console.error('Keycloak initialization failed', error);

      // Keycloak 실패 시 로컬 JWT 확인
      const savedToken = localStorage.getItem('access_token');
      const savedUser = localStorage.getItem('user');

      if (savedToken && savedUser) {
        setAuthMode('local');
        setToken(savedToken);
        setUser(JSON.parse(savedUser));
      }

      setLoading(false);
    });
  }, []);

  const loginWithKeycloak = () => {
    keycloak.login();
  };

  const loginLocal = (userData, accessToken) => {
    // 기존 로컬 JWT 로그인
    setAuthMode('local');
    setUser(userData);
    setToken(accessToken);
    localStorage.setItem('access_token', accessToken);
    localStorage.setItem('user', JSON.stringify(userData));
    localStorage.setItem('auth_mode', 'local');
  };

  const logout = () => {
    if (authMode === 'keycloak') {
      keycloak.logout({
        redirectUri: window.location.origin
      });
    } else {
      // 로컬 로그아웃
      setUser(null);
      setToken(null);
      setAuthMode('local');
      localStorage.removeItem('access_token');
      localStorage.removeItem('user');
      localStorage.removeItem('auth_mode');
    }
  };

  const getAuthHeader = () => {
    return token ? { 'Authorization': `Bearer ${token}` } : {};
  };

  const value = {
    user,
    token,
    loginWithKeycloak,
    loginLocal,
    logout,
    getAuthHeader,
    isAuthenticated: !!token,
    isAdmin: user?.role === 'admin',
    loading,
    authMode
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
```

### 4. Login 컴포넌트 수정 - Keycloak 버튼 추가

`src/components/Login.jsx` 수정:

```javascript
import React, { useState } from 'react';
import { LogIn, Key } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

const API_URL = '/api';

export default function Login() {
  const { loginLocal, loginWithKeycloak } = useAuth();
  const [credentials, setCredentials] = useState({
    username: '',
    password: ''
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLocalLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(credentials)
      });

      const data = await response.json();

      if (response.ok) {
        loginLocal(data.user, data.access_token);
      } else {
        setError(data.detail || 'Login failed');
      }
    } catch (err) {
      setError('Network error. Please try again.');
      console.error('Login error:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-500 to-purple-600 p-4">
      <div className="bg-white rounded-lg shadow-2xl p-8 w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-100 rounded-full mb-4">
            <LogIn className="text-blue-600" size={32} />
          </div>
          <h1 className="text-3xl font-bold text-gray-800">Ansible Builder</h1>
          <p className="text-gray-600 mt-2">Sign in to continue</p>
        </div>

        {/* Keycloak SSO 버튼 */}
        <div className="mb-6">
          <button
            onClick={loginWithKeycloak}
            className="w-full flex items-center justify-center gap-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white py-3 px-4 rounded-lg hover:from-purple-700 hover:to-blue-700 focus:ring-4 focus:ring-purple-300 font-medium transition"
          >
            <Key size={20} />
            Sign in with Keycloak SSO
          </button>
        </div>

        <div className="relative mb-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-gray-300"></div>
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="px-2 bg-white text-gray-500">Or continue with local account</span>
          </div>
        </div>

        <form onSubmit={handleLocalLogin} className="space-y-6">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Username
            </label>
            <input
              type="text"
              value={credentials.username}
              onChange={(e) => setCredentials({ ...credentials, username: e.target.value })}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition"
              placeholder="Enter your username"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Password
            </label>
            <input
              type="password"
              value={credentials.password}
              onChange={(e) => setCredentials({ ...credentials, password: e.target.value })}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition"
              placeholder="Enter your password"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 text-white py-3 px-4 rounded-lg hover:bg-blue-700 focus:ring-4 focus:ring-blue-300 font-medium transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Signing in...' : 'Sign In (Local)'}
          </button>
        </form>

        <div className="mt-6 p-4 bg-gray-50 rounded-lg">
          <p className="text-sm text-gray-600 font-medium mb-2">Default Local Credentials:</p>
          <p className="text-xs text-gray-500">Username: <code className="bg-gray-200 px-2 py-1 rounded">admin</code></p>
          <p className="text-xs text-gray-500">Password: <code className="bg-gray-200 px-2 py-1 rounded">admin123</code></p>
        </div>
      </div>
    </div>
  );
}
```

### 5. Silent SSO HTML 파일 생성

`public/silent-check-sso.html` 파일 생성:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Silent SSO Check</title>
</head>
<body>
    <script>
        parent.postMessage(location.href, location.origin);
    </script>
</body>
</html>
```

---

## 테스트 및 검증

### 1. Keycloak 서버 확인

```bash
# Keycloak 실행 확인
docker ps | grep keycloak

# Keycloak 로그 확인
docker logs keycloak

# Keycloak Admin Console 접속
# http://localhost:8080
```

### 2. 통합 테스트 체크리스트

#### Keycloak 설정 테스트
- [ ] Realm 생성 확인 (ansible-realm)
- [ ] Client 생성 확인 (awx-client, ansible-builder-client)
- [ ] Roles 생성 확인 (admin, user, awx-admin, awx-user)
- [ ] 테스트 사용자 생성 (admin, testuser)

#### AWX 통합 테스트
- [ ] AWX에서 "Sign in with OIDC" 버튼 표시
- [ ] Keycloak 로그인 리다이렉트
- [ ] 로그인 후 AWX 자동 사용자 생성
- [ ] Role 매핑 확인 (admin → AWX Admin)

#### Ansible Builder 통합 테스트
- [ ] "Sign in with Keycloak SSO" 버튼 표시
- [ ] Keycloak 로그인 성공
- [ ] 사용자 정보 자동 동기화
- [ ] Role 기반 권한 확인
- [ ] 토큰 자동 갱신 작동
- [ ] 로그아웃 후 Keycloak 세션 종료
- [ ] 로컬 JWT 로그인도 여전히 작동

#### SSO 테스트
- [ ] Keycloak 로그인 → AWX 자동 로그인
- [ ] Keycloak 로그인 → Ansible Builder 자동 로그인
- [ ] 한 곳에서 로그아웃 → 모든 곳에서 로그아웃

### 3. 통합 테스트 스크립트

```bash
#!/bin/bash

echo "=== Keycloak 통합 테스트 ==="

# 1. Keycloak 접속 확인
echo "1. Keycloak 서버 접속 확인..."
curl -s http://localhost:8080/realms/ansible-realm/.well-known/openid-configuration | jq .

# 2. Keycloak 토큰 발급 테스트
echo -e "\n2. Keycloak 토큰 발급 테스트..."
TOKEN_RESPONSE=$(curl -s -X POST http://localhost:8080/realms/ansible-realm/protocol/openid-connect/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id=ansible-builder-client" \
  -d "username=admin" \
  -d "password=admin123")

ACCESS_TOKEN=$(echo $TOKEN_RESPONSE | jq -r .access_token)
echo "Access Token: ${ACCESS_TOKEN:0:50}..."

# 3. Ansible Builder API 테스트 (Keycloak 토큰 사용)
echo -e "\n3. Ansible Builder API 테스트..."
curl -s http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq .

echo -e "\n4. Playbooks 조회 테스트..."
curl -s http://localhost:8000/api/playbooks \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq .

echo -e "\n=== 테스트 완료 ==="
```

---

## 환경 변수 설정

### Backend `.env` 파일

```bash
# Keycloak 설정
KEYCLOAK_SERVER_URL=http://localhost:8080
KEYCLOAK_REALM=ansible-realm
KEYCLOAK_CLIENT_ID=ansible-builder-client
KEYCLOAK_CLIENT_SECRET=

# 기존 JWT 설정 (하위 호환성)
JWT_SECRET_KEY=your-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

### Frontend 환경 변수

`.env` 파일:

```bash
REACT_APP_KEYCLOAK_URL=http://localhost:8080
REACT_APP_KEYCLOAK_REALM=ansible-realm
REACT_APP_KEYCLOAK_CLIENT_ID=ansible-builder-client
```

---

## 문제 해결

### 1. Keycloak 접속 불가

```bash
# 방화벽 확인
sudo firewall-cmd --list-ports

# 포트 열기
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --reload

# Docker 로그 확인
docker logs keycloak
```

### 2. CORS 에러

Keycloak Admin Console:
1. Clients → ansible-builder-client
2. Web origins: `+` 또는 구체적인 도메인 추가

### 3. 토큰 검증 실패

- Keycloak 서버 시간 동기화 확인
- JWT 알고리즘 확인 (RS256)
- Audience, Issuer 설정 확인

### 4. 사용자 자동 생성 안됨

- Client Scopes에서 필요한 Claim 포함 확인
- Backend의 `get_or_create_user_from_keycloak` 로직 디버깅

---

## 프로덕션 배포 시 고려사항

### 1. HTTPS 설정

```yaml
# docker-compose.yml에 Nginx 추가
nginx:
  image: nginx:latest
  ports:
    - "443:443"
  volumes:
    - ./nginx.conf:/etc/nginx/nginx.conf
    - ./ssl:/etc/nginx/ssl
```

### 2. Keycloak 데이터베이스 백업

```bash
# PostgreSQL 백업
docker exec keycloak-postgres pg_dump -U keycloak keycloak > keycloak_backup.sql
```

### 3. 세션 타임아웃 설정

Keycloak Admin Console:
- Realm Settings → Tokens
- Access Token Lifespan: 5 minutes
- SSO Session Idle: 30 minutes
- SSO Session Max: 10 hours

### 4. 보안 강화

- [ ] HTTPS 적용
- [ ] Strong Password Policy
- [ ] 2FA 활성화
- [ ] Rate Limiting
- [ ] IP Whitelist

---

## 마이그레이션 계획

### 기존 사용자 마이그레이션

1. **Keycloak으로 사용자 가져오기**:
   - Keycloak Admin Console → Users → Import
   - CSV 또는 JSON 형식으로 일괄 가져오기

2. **비밀번호 재설정**:
   - 이메일을 통한 비밀번호 재설정 링크 발송
   - 임시 비밀번호 제공

3. **점진적 마이그레이션**:
   - 로컬 JWT와 Keycloak 병행 운영
   - 사용자별로 점진적 전환
   - 일정 기간 후 로컬 JWT 비활성화

---

## 참고 자료

- [Keycloak Documentation](https://www.keycloak.org/documentation)
- [AWX OIDC Configuration](https://github.com/ansible/awx/blob/devel/docs/auth/oidc.md)
- [OpenID Connect Specification](https://openid.net/connect/)
- [keycloak-js Documentation](https://www.keycloak.org/docs/latest/securing_apps/#_javascript_adapter)

---

## 다음 단계

1. ✅ Keycloak 서버 설치
2. ✅ Realm 및 Client 설정
3. ✅ AWX 통합
4. ✅ Ansible Builder 백엔드 통합
5. ✅ Ansible Builder 프론트엔드 통합
6. ⏭ 통합 테스트
7. ⏭ 프로덕션 배포

---

**구현 완료 후 Keycloak을 통해 AWX와 Ansible Builder를 하나의 인증 시스템으로 통합 관리할 수 있습니다!**
