# AWX - Ansible Builder Keycloak SSO 통합 완료!

## 설정 완료 사항

### 1. Keycloak 설정 ✓
- **Realm**: ansible-realm
- **Clients**:
  - `ansible-builder-client`: Ansible Builder용
  - `awx-client`: AWX용 (Client Secret: awx-secret-key)
- **Users**:
  - Admin: username=admin, password=admin123
  - Test User: username=testuser, password=test123

### 2. Ansible Builder 설정 ✓
- **URL**: http://192.168.64.26:8000
- **인증**: Keycloak SSO Only (JWT 제거 완료)
- **Keycloak 연동**: 완료

### 3. AWX 설정 ✓
- **URL**: http://192.168.64.26:30000
- **Admin 계정**: admin / UDXVGspozrOjvhgQvZgzDVmvKcxZz3Dn
- **OIDC 설정**: 완료
  - SOCIAL_AUTH_OIDC_KEY: awx-client
  - SOCIAL_AUTH_OIDC_SECRET: awx-secret-key
  - SOCIAL_AUTH_OIDC_OIDC_ENDPOINT: http://192.168.64.26:8080/realms/ansible-realm
  - SOCIAL_AUTH_CREATE_USERS: true

---

## SSO 통합 테스트 방법

### 시나리오 1: Ansible Builder → AWX 자동 로그인

1. **브라우저를 열고 Ansible Builder 접속**
   ```
   http://192.168.64.26:8000
   ```

2. **"Sign in with Keycloak SSO" 버튼 클릭**

3. **Keycloak 로그인**
   - Admin 계정: `admin` / `admin123`
   - 또는 Test 계정: `testuser` / `test123`

4. **Ansible Builder에 로그인 완료!**
   - 우측 상단에 사용자 이름 표시 확인

5. **새 탭에서 AWX 접속**
   ```
   http://192.168.64.26:30000
   ```

6. **AWX 로그인 페이지에서 "SIGN IN WITH OIDC" 버튼 클릭**
   - 또는 직접 URL: http://192.168.64.26:30000/sso/login/oidc/

7. **자동으로 AWX에 로그인됩니다!**
   - 재인증 필요 없음
   - 같은 Keycloak 세션 사용

---

### 시나리오 2: AWX → Ansible Builder 자동 로그인

1. **브라우저를 열고 AWX 접속**
   ```
   http://192.168.64.26:30000
   ```

2. **"SIGN IN WITH OIDC" 버튼 클릭**

3. **Keycloak 로그인**
   - Admin 또는 Test 계정으로 로그인

4. **AWX에 로그인 완료!**

5. **새 탭에서 Ansible Builder 접속**
   ```
   http://192.168.64.26:8000
   ```

6. **자동으로 Ansible Builder에 로그인됩니다!**

---

## SSO 작동 원리

```
┌─────────────────────┐         ┌──────────────────┐         ┌─────────────┐
│  Ansible Builder    │         │    Keycloak      │         │     AWX     │
│  (8000)             │◀────────│   (8080)         │────────▶│   (30000)   │
└─────────────────────┘         │  ansible-realm   │         └─────────────┘
                                └──────────────────┘
                                        │
                                 Single Sign-On
                               (하나의 세션으로 통합)
```

1. 사용자가 Ansible Builder 또는 AWX 중 하나에 로그인
2. Keycloak이 세션 생성 (브라우저 쿠키 저장)
3. 다른 애플리케이션 접속 시 Keycloak 세션 확인
4. **자동 로그인!** (재인증 불필요)

---

## 로그아웃

### 단일 애플리케이션 로그아웃
- Ansible Builder 또는 AWX에서 로그아웃하면 해당 앱에서만 로그아웃됩니다.
- 다른 앱은 여전히 로그인 상태 유지

### 완전 로그아웃 (SSO 로그아웃)
Keycloak에서 로그아웃하면 모든 연결된 애플리케이션에서 로그아웃됩니다:
```
http://192.168.64.26:8080/realms/ansible-realm/protocol/openid-connect/logout
```

---

## 사용자 관리

### 새 사용자 추가
1. Keycloak Admin Console 접속
   ```
   http://192.168.64.26:8080/admin
   ```
   - Admin: admin / admin

2. `ansible-realm` 선택

3. Users → Add User

4. 사용자 정보 입력 후 생성

5. Credentials 탭에서 비밀번호 설정

6. **자동으로 Ansible Builder와 AWX에서 사용 가능!**
   - `SOCIAL_AUTH_CREATE_USERS=true` 설정으로 JIT 프로비저닝

### 권한 관리
- **Keycloak Role**:
  - `admin` role → AWX와 Ansible Builder에서 admin 권한
  - `user` role → 일반 사용자 권한

- **Role 할당**: Keycloak Admin Console → Users → [사용자] → Role Mappings

---

## 문제 해결

### 1. "Invalid redirect URI" 오류
**원인**: Keycloak Client의 Redirect URI 설정 오류

**해결**:
```bash
# Keycloak Admin Console → Clients → awx-client 또는 ansible-builder-client
Valid Redirect URIs:
  - http://192.168.64.26:8000/*
  - http://192.168.64.26:30000/*
```

### 2. "User does not exist" 오류
**원인**: 사용자 자동 생성 미활성화

**해결**:
```bash
# AWX에서 확인
kubectl exec -n awx awx-task-67c7c4fdcd-9z85t -- \
  awx-manage shell -c "from awx.conf.models import Setting; \
  print(Setting.objects.filter(key='SOCIAL_AUTH_CREATE_USERS').first().value)"

# true여야 함. false이면 재설정:
# (위 스크립트 재실행)
```

### 3. Keycloak 세션 만료
**원인**: 기본 세션 타임아웃

**해결**:
- Keycloak Admin Console → Realm Settings → Tokens
- SSO Session Idle / SSO Session Max 조정

### 4. AWX "SIGN IN WITH OIDC" 버튼이 보이지 않음
**원인**: AWX OIDC 설정 미적용 또는 캐시 문제

**해결**:
```bash
# AWX Pods 재시작
kubectl rollout restart deployment -n awx awx-web
kubectl rollout restart deployment -n awx awx-task

# 브라우저 캐시 클리어 (Ctrl+Shift+Delete)
```

---

## 참고 자료

- Keycloak Documentation: https://www.keycloak.org/docs/
- AWX OIDC Configuration: https://docs.ansible.com/ansible-tower/latest/html/administration/social_auth.html
- OpenID Connect Protocol: https://openid.net/connect/

---

## 서비스 URL 정리

| 서비스 | URL | 용도 |
|--------|-----|------|
| **Keycloak Admin** | http://192.168.64.26:8080/admin | SSO 관리 (admin/admin) |
| **Keycloak Realm** | http://192.168.64.26:8080/realms/ansible-realm | 로그인 페이지 |
| **Ansible Builder** | http://192.168.64.26:8000 | Playbook 빌더 |
| **AWX** | http://192.168.64.26:30000 | Automation Controller |

---

## 축하합니다!

AWX와 Ansible Builder가 Keycloak SSO로 통합되었습니다! 🎉

이제 하나의 계정으로 두 시스템을 모두 사용할 수 있습니다.
