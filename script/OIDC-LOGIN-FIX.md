# AWX OIDC 로그인 문제 해결

## 문제 상황

**증상**: kiju.kang@kt.com 일반 사용자로 OIDC 로그인 시 에러 발생
```
ERROR social Your credentials aren't allowed.
```

## 원인 분석

### 1. 에러 로그 분석
```bash
kubectl logs -n awx -l app.kubernetes.io/name=awx-web --tail=100 | grep ERROR
```

**에러 메시지**: `Your credentials aren't allowed.`

### 2. 기존 AWX OIDC 설정
```python
SOCIAL_AUTH_OIDC_ORGANIZATION_MAP = {
    'Default': {
        'users': True,
        'admins': True,  # ❌ 문제: 모든 사용자가 관리자여야 로그인 가능
        'remove_users': False,
        'remove_admins': False
    }
}
```

**문제**: `'admins': True` 설정으로 인해 모든 OIDC 사용자가 조직 관리자 권한을 가져야만 로그인할 수 있었음.

### 3. Keycloak 사용자 확인
```bash
# kiju.kang@kt.com 사용자는 Keycloak에 존재하고 developer 그룹에도 속함
✅ 사용자: kiju.kang@kt.com
✅ 그룹: developer
❌ 하지만 AWX는 관리자만 허용
```

## 해결 방법

### 수정된 AWX OIDC 설정

```python
SOCIAL_AUTH_OIDC_ORGANIZATION_MAP = {
    'Default': {
        'users': True,                    # ✅ 모든 OIDC 사용자를 조직 멤버로 추가
        'admins': 'realm_role:admin',     # ✅ Keycloak에서 'admin' role을 가진 사용자만 관리자
        'remove_users': False,
        'remove_admins': False
    }
}
```

### 변경 사항

| 항목 | 변경 전 | 변경 후 |
|------|---------|---------|
| Organization 일반 사용자 | ❌ 불가능 | ✅ 가능 |
| Organization 관리자 | 모든 OIDC 사용자 | Keycloak `admin` role 보유자만 |
| 로그인 가능 여부 | 관리자만 | 모든 사용자 |

## 적용 절차

### 1. AWX OIDC 설정 업데이트

```bash
AWX_WEB_POD=$(kubectl get pods -n awx -l app.kubernetes.io/name=awx-web -o jsonpath='{.items[0].metadata.name}')

kubectl exec -n awx ${AWX_WEB_POD} -c awx-web -- bash -c "awx-manage shell << 'PYEOF'
from awx.conf.models import Setting

# Organization Map 업데이트
org_map = {
    'Default': {
        'users': True,
        'admins': 'realm_role:admin',
        'remove_users': False,
        'remove_admins': False
    }
}

setting = Setting.objects.get(key='SOCIAL_AUTH_OIDC_ORGANIZATION_MAP')
setting.value = org_map
setting.save()

print('✅ Organization Map 업데이트 완료')
PYEOF
"
```

### 2. AWX Web Pod 재시작

```bash
kubectl rollout restart deployment/awx-web -n awx
kubectl rollout status deployment/awx-web -n awx
```

## 현재 OIDC 매핑 설정

### Organization Map (조직 매핑)

```python
{
    'Default': {
        'users': True,                    # 모든 OIDC 사용자 → Default 조직 일반 멤버
        'admins': 'realm_role:admin',     # Keycloak admin role → Default 조직 관리자
        'remove_users': False,
        'remove_admins': False
    }
}
```

**의미**:
- ✅ 모든 OIDC 사용자는 Default 조직의 일반 멤버로 로그인 가능
- ✅ Keycloak에서 `admin` realm role을 가진 사용자만 조직 관리자 권한 획득
- ✅ 일반 사용자도 팀 멤버십을 통해 리소스 접근 가능

### Team Map (팀 매핑)

```python
{
    'developer': {
        'organization': 'Default',
        'users': '/developer',            # Keycloak developer 그룹 → AWX developer 팀
        'remove': False
    }
}
```

**의미**:
- ✅ Keycloak의 `developer` 그룹에 속한 사용자 → AWX `developer` 팀에 자동 추가
- ✅ developer 팀을 통해 프로젝트, 인벤토리, Job Template 등 접근 가능

## 사용자 역할 구조

### 일반 사용자 (예: kiju.kang@kt.com)

**Keycloak**:
- 그룹: `developer`
- Realm Role: (없음)

**AWX 로그인 후**:
- 조직: `Default` (일반 멤버)
- 팀: `developer`
- 권한: developer 팀에 부여된 권한에 따라 제한됨

**접근 가능한 리소스**:
- ✅ developer 팀에 할당된 프로젝트
- ✅ developer 팀에 할당된 인벤토리
- ✅ developer 팀에 할당된 Job Template
- ❌ 조직 관리 기능 (사용자 관리, 조직 설정 등)

### 관리자 사용자 (예: admin)

**Keycloak**:
- 그룹: `developer`
- Realm Role: `admin` ⭐

**AWX 로그인 후**:
- 조직: `Default` (관리자)
- 팀: `developer`
- 권한: 조직 전체 관리 권한

**접근 가능한 리소스**:
- ✅ 모든 프로젝트, 인벤토리, Job Template
- ✅ 사용자 관리
- ✅ 조직 설정
- ✅ 팀 관리

## Keycloak Realm Role 설정

### admin 사용자에게 admin role 부여

1. **Keycloak Admin Console 접속**
   ```
   http://192.168.64.26:30002/admin
   Username: admin
   Password: admin123
   ```

2. **ansible-realm 선택**

3. **Users 메뉴 → 사용자 선택**

4. **Role Mapping 탭**

5. **Assign Role 클릭**

6. **Filter by realm roles 선택**

7. **admin role 체크 → Assign 클릭**

### 스크립트로 admin role 부여

```bash
KEYCLOAK_URL="http://192.168.64.26:30002"

# Get admin token
TOKEN=$(curl -s -X POST "${KEYCLOAK_URL}/realms/master/protocol/openid-connect/token" \
  -d "client_id=admin-cli" \
  -d "username=admin" \
  -d "password=admin123" \
  -d "grant_type=password" | jq -r '.access_token')

# Get user ID (admin 사용자)
USER_ID=$(curl -s -X GET "${KEYCLOAK_URL}/admin/realms/ansible-realm/users?username=admin" \
  -H "Authorization: Bearer ${TOKEN}" | jq -r '.[0].id')

# Get admin role ID
ADMIN_ROLE=$(curl -s -X GET "${KEYCLOAK_URL}/admin/realms/ansible-realm/roles/admin" \
  -H "Authorization: Bearer ${TOKEN}")

# Assign admin role to user
curl -s -X POST "${KEYCLOAK_URL}/admin/realms/ansible-realm/users/${USER_ID}/role-mappings/realm" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "[${ADMIN_ROLE}]"

echo "✅ admin 사용자에게 admin role 부여 완료"
```

## 테스트 시나리오

### 시나리오 1: 일반 사용자 로그인

1. **AWX 로그아웃** (기존 세션 종료)
   ```
   http://192.168.64.26:30000
   ```

2. **Sign in with OIDC 클릭**

3. **Keycloak 로그인**
   ```
   Username: kiju.kang@kt.com
   Password: [사용자 비밀번호]
   ```

4. **예상 결과**:
   - ✅ 로그인 성공
   - ✅ AWX 대시보드 접근
   - ✅ developer 팀 메뉴 보임
   - ❌ 조직 관리 메뉴 없음 (일반 사용자이므로)

### 시나리오 2: 관리자 로그인

1. **AWX 로그아웃**

2. **Sign in with OIDC 클릭**

3. **Keycloak 로그인**
   ```
   Username: admin
   Password: admin123
   ```

4. **예상 결과**:
   - ✅ 로그인 성공
   - ✅ AWX 대시보드 접근
   - ✅ developer 팀 메뉴 보임
   - ✅ 조직 관리 메뉴 보임 (admin role 보유)

### 시나리오 3: 새 일반 사용자 추가

1. **Keycloak Admin Console에서 사용자 생성**
   - Username: `new.user@kt.com`
   - Email: `new.user@kt.com`
   - Password: `user123`

2. **사용자를 developer 그룹에 추가**
   ```bash
   ./add-users-to-keycloak-group.sh
   ```

3. **AWX OIDC 로그인 테스트**
   - ✅ 로그인 성공 (조직 일반 멤버)
   - ✅ developer 팀 자동 추가

## developer 팀 권한 설정

developer 팀이 리소스를 사용하려면 AWX에서 권한을 부여해야 합니다.

### AWX UI에서 권한 부여

1. **AWX 관리자로 로그인**

2. **Access → Teams → developer 클릭**

3. **Permissions 탭**

4. **Add 클릭**

5. **리소스 선택** (예: Project, Inventory, Job Template)

6. **Role 선택** (예: Admin, Use, Read)

7. **Save**

### API로 권한 부여 (예시)

```bash
AWX_URL="http://192.168.64.26:30000"
AWX_TOKEN="A6tZWbC5pFXUynXvhogzzC0BDWulOj"

# developer 팀에 프로젝트 사용 권한 부여
curl -X POST "${AWX_URL}/api/v2/projects/1/object_roles/use_role/teams/" \
  -H "Authorization: Bearer ${AWX_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"id": 1}'  # Team ID: 1 (developer)
```

## 트러블슈팅

### 문제: 여전히 "Your credentials aren't allowed" 에러

**해결**:
1. AWX 설정 확인
   ```bash
   AWX_WEB_POD=$(kubectl get pods -n awx -l app.kubernetes.io/name=awx-web -o jsonpath='{.items[0].metadata.name}')
   kubectl exec -n awx ${AWX_WEB_POD} -c awx-web -- awx-manage shell << 'EOF'
   from awx.conf.models import Setting
   org_map = Setting.objects.get(key='SOCIAL_AUTH_OIDC_ORGANIZATION_MAP')
   print(org_map.value)
   EOF
   ```

2. 사용자가 developer 그룹에 속해있는지 확인
   ```bash
   ./check-keycloak-groups.sh
   ```

3. AWX Web Pod 재시작
   ```bash
   kubectl rollout restart deployment/awx-web -n awx
   ```

### 문제: 로그인은 되지만 아무것도 보이지 않음

**원인**: developer 팀에 권한이 부여되지 않음

**해결**:
- AWX UI에서 developer 팀에 프로젝트/인벤토리/Job Template 권한 부여
- 또는 ansible-builder에서 생성한 리소스를 developer 팀과 공유

### 문제: 관리자 사용자가 조직 관리 메뉴를 볼 수 없음

**원인**: Keycloak에서 admin realm role이 부여되지 않음

**해결**:
```bash
# 위의 "admin role 부여" 스크립트 실행
# 또는 Keycloak Admin Console에서 수동으로 role 할당
```

## 요약

### 수정 사항
- ✅ AWX Organization Map에서 `'admins': True` → `'admins': 'realm_role:admin'`으로 변경
- ✅ 일반 사용자도 OIDC 로그인 가능
- ✅ 관리자 권한은 Keycloak realm role 기반으로 부여

### 사용자 권한 구조
| 사용자 | Keycloak 그룹 | Keycloak Role | AWX 조직 권한 | AWX 팀 |
|--------|--------------|---------------|---------------|--------|
| admin | developer | admin | 조직 관리자 | developer |
| kiju.kang@kt.com | developer | (없음) | 조직 일반 멤버 | developer |
| new.user@kt.com | developer | (없음) | 조직 일반 멤버 | developer |

### 다음 단계
1. ✅ kiju.kang@kt.com으로 로그인 테스트
2. ✅ developer 팀 권한 설정
3. ✅ 필요시 admin 사용자에게 admin realm role 부여
