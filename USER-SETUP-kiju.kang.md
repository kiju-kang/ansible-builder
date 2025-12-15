# kiju.kang@kt.com 사용자 설정 완료

## 작업 내용

### 1. 문제 진단
- **증상**: kiju.kang@kt.com 사용자로 OIDC 로그인 불가
- **원인**:
  1. 초기 비밀번호가 설정되지 않았거나 잘못됨
  2. AWX Organization Map이 모든 사용자를 관리자로 요구 (이미 수정됨)

### 2. 해결 작업

#### 사용자 재생성
```bash
# 기존 사용자 삭제
DELETE /admin/realms/ansible-realm/users/{user-id}

# 새 사용자 생성
POST /admin/realms/ansible-realm/users
{
  "username": "kiju.kang@kt.com",
  "email": "kiju.kang@kt.com",
  "enabled": true,
  "emailVerified": true,
  "firstName": "Kiju",
  "lastName": "Kang"
}

# 비밀번호 설정
PUT /admin/realms/ansible-realm/users/{user-id}/reset-password
{
  "type": "password",
  "value": "Q4171838q!",
  "temporary": false
}
```

#### developer 그룹 추가
```bash
PUT /admin/realms/ansible-realm/users/{user-id}/groups/{group-id}
```

#### Keycloak 인증 테스트
```bash
✅ 성공
POST /realms/ansible-realm/protocol/openid-connect/token
- client_id: ansible-builder-client
- username: kiju.kang@kt.com
- password: Q4171838q!
- grant_type: password

Response: Access Token 획득 성공
```

## 사용자 정보

| 항목 | 값 |
|------|-----|
| Username | kiju.kang@kt.com |
| Email | kiju.kang@kt.com |
| Password | Q4171838q! |
| Enabled | ✅ true |
| Email Verified | ✅ true |
| Keycloak Realm | ansible-realm |
| Keycloak 그룹 | developer |
| Keycloak Role | (없음 - 일반 사용자) |
| User ID | b9d3223d-de31-4dc7-8c02-9e25c577bf99 |

## AWX 권한 (OIDC 로그인 후)

### 조직 권한
- **조직**: Default
- **역할**: 일반 멤버 (Member)
- **관리자 권한**: ❌ 없음 (정상)

### 팀 멤버십
- **팀**: developer
- **자동 추가**: ✅ OIDC 로그인 시 자동으로 developer 팀에 추가됨

### 접근 가능한 리소스
- ✅ developer 팀에 할당된 프로젝트
- ✅ developer 팀에 할당된 인벤토리
- ✅ developer 팀에 할당된 Job Template
- ✅ developer 팀에 할당된 Credential
- ❌ 조직 관리 기능 (사용자 관리, 조직 설정 등)

## OIDC 로그인 절차

### 1. AWX 접속
```
http://192.168.64.26:30000
```

### 2. OIDC 로그인 버튼 클릭
- 화면에서 **"Sign in with OIDC"** 버튼 클릭
- Keycloak ansible-realm 로그인 페이지로 리다이렉트됨

### 3. Keycloak 로그인
```
Username or Email: kiju.kang@kt.com
Password: Q4171838q!
```

### 4. AWX 리다이렉트
- 로그인 성공 시 자동으로 AWX 대시보드로 이동
- 처음 로그인 시:
  - Default 조직의 일반 멤버로 자동 추가
  - developer 팀에 자동 추가

## 예상 AWX UI 메뉴

### 일반 사용자로 보이는 메뉴
- ✅ Dashboard
- ✅ Jobs
- ✅ Templates (developer 팀 권한에 따라)
- ✅ Projects (developer 팀 권한에 따라)
- ✅ Inventories (developer 팀 권한에 따라)
- ✅ Credentials (developer 팀 권한에 따라)

### 보이지 않는 메뉴 (관리자 전용)
- ❌ Organizations
- ❌ Users
- ❌ Teams (읽기만 가능)
- ❌ Settings
- ❌ Subscriptions

## 로그인 테스트 결과 확인

### Keycloak 인증
```bash
✅ 성공
- 사용자: kiju.kang@kt.com
- 비밀번호: Q4171838q!
- Access Token: 획득 성공
```

### AWX OIDC 설정
```python
✅ 정상
SOCIAL_AUTH_OIDC_ORGANIZATION_MAP = {
    'Default': {
        'users': True,                    # 모든 OIDC 사용자 로그인 가능
        'admins': 'realm_role:admin',     # admin role 보유자만 관리자
        'remove_users': False,
        'remove_admins': False
    }
}

SOCIAL_AUTH_OIDC_TEAM_MAP = {
    'developer': {
        'organization': 'Default',
        'users': '/developer',            # developer 그룹 → developer 팀
        'remove': False
    }
}
```

## 트러블슈팅

### 문제: 로그인 시 "Your credentials aren't allowed" 에러

**해결됨**: AWX Organization Map이 이미 수정되어 일반 사용자 로그인 가능

### 문제: Keycloak 로그인 후 AWX로 리다이렉트되지 않음

**확인사항**:
1. awx-oidc 클라이언트 redirect URI 확인
   ```bash
   # Keycloak Admin Console
   # Clients → awx-oidc → Valid Redirect URIs
   # http://192.168.64.26:30000/* 포함되어야 함
   ```

2. AWX 로그 확인
   ```bash
   kubectl logs -n awx -l app.kubernetes.io/name=awx-web --tail=100
   ```

### 문제: 로그인은 되지만 아무 리소스도 보이지 않음

**원인**: developer 팀에 권한이 부여되지 않음

**해결**:
```bash
# AWX 관리자로 로그인
# Access → Teams → developer → Permissions
# Add 버튼으로 프로젝트/인벤토리/템플릿 권한 추가
```

## 관리자 권한이 필요한 경우

kiju.kang@kt.com 사용자에게 관리자 권한을 부여하려면:

### 방법 1: Keycloak에서 admin realm role 부여

```bash
KEYCLOAK_URL="http://192.168.64.26:30002"
TOKEN=$(curl -s -X POST "${KEYCLOAK_URL}/realms/master/protocol/openid-connect/token" \
  -d "client_id=admin-cli" \
  -d "username=admin" \
  -d "password=admin123" \
  -d "grant_type=password" | jq -r '.access_token')

USER_ID="b9d3223d-de31-4dc7-8c02-9e25c577bf99"

# Get admin role
ADMIN_ROLE=$(curl -s -X GET "${KEYCLOAK_URL}/admin/realms/ansible-realm/roles/admin" \
  -H "Authorization: Bearer ${TOKEN}")

# Assign admin role
curl -X POST "${KEYCLOAK_URL}/admin/realms/ansible-realm/users/${USER_ID}/role-mappings/realm" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "[${ADMIN_ROLE}]"
```

**효과**: 다음 로그인부터 Default 조직의 관리자로 승격

### 방법 2: AWX UI에서 수동으로 권한 부여

```
1. AWX 관리자로 로그인
2. Access → Users → kiju.kang@kt.com 선택
3. Roles 탭
4. Add → Organization Admin (Default) 선택
```

**효과**: 즉시 관리자 권한 부여 (재로그인 불필요)

## 최종 확인 체크리스트

- [x] Keycloak에 사용자 생성 (kiju.kang@kt.com)
- [x] 비밀번호 설정 (Q4171838q!)
- [x] developer 그룹에 추가
- [x] Keycloak 직접 인증 테스트 성공
- [x] AWX Organization Map 수정 (일반 사용자 로그인 허용)
- [x] AWX Team Map 설정 (developer 그룹 → developer 팀)
- [x] AWX Web Pod 재시작 완료
- [ ] **사용자가 실제 OIDC 로그인 테스트** ⬅️ 다음 단계

## 다음 단계

1. **OIDC 로그인 테스트**
   - http://192.168.64.26:30000 접속
   - "Sign in with OIDC" 클릭
   - kiju.kang@kt.com / Q4171838q! 로그인

2. **로그인 성공 확인**
   - AWX 대시보드 접근 확인
   - 사용자 프로필에서 조직/팀 확인
   - 메뉴 접근 권한 확인

3. **developer 팀 권한 설정** (관리자 작업)
   - developer 팀에 프로젝트 권한 부여
   - developer 팀에 인벤토리 권한 부여
   - developer 팀에 Job Template 실행 권한 부여

## 참고 문서

- [OIDC-LOGIN-FIX.md](./sh/OIDC-LOGIN-FIX.md) - OIDC 로그인 문제 해결 가이드
- [README-KEYCLOAK-AWX-INTEGRATION.md](./sh/README-KEYCLOAK-AWX-INTEGRATION.md) - Keycloak + AWX 통합 가이드
- [SCRIPT-SUMMARY.md](./sh/SCRIPT-SUMMARY.md) - 스크립트 요약
