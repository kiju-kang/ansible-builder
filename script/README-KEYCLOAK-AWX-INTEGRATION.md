# Keycloak + AWX 통합 가이드

## 개요
이 문서는 Keycloak SSO와 AWX를 통합하여 사용자, 그룹, 조직, 팀, 권한을 설정하는 전체 워크플로우를 설명합니다.

## 아키텍처

```
Keycloak (ansible-realm)
├── Groups
│   └── developer (Keycloak 그룹)
└── Users
    └── admin (테스트 사용자)

AWX
├── Organizations
│   └── Default (OIDC 사용자 자동 추가)
└── Teams
    └── developer (Keycloak /developer 그룹 매핑)
```

## 전체 설정 워크플로우

### 1단계: Keycloak ansible-realm 설정

**스크립트**: `configure-awx-ansible-realm.sh`

**기능**:
- ansible-realm 생성 (없는 경우)
- awx-oidc 클라이언트 생성 (Confidential Client)
- 클라이언트 시크릿 생성 및 저장 (`/root/awx-ansible-realm-client-secret.txt`)
- 테스트 사용자 생성 (admin/admin123)
- developer 그룹 생성

**실행**:
```bash
cd /root/ansible-builder/sh
./configure-awx-ansible-realm.sh
```

**출력**:
```
✅ ansible-realm 생성 완료
✅ AWX OIDC 클라이언트 생성 완료
   Client ID: awx-oidc
   Client Secret: [32-byte hex string]
   Secret 저장 위치: /root/awx-ansible-realm-client-secret.txt
✅ admin 사용자 생성 완료 (admin/admin123)
✅ developer 그룹 생성 완료
```

---

### 2단계: AWX OIDC 설정 적용

**스크립트**: `apply-awx-ansible-realm-settings.sh`

**기능**:
- AWX에 Keycloak OIDC 설정 적용
- OIDC 엔드포인트를 ansible-realm으로 변경
- 조직 매핑 설정 (모든 OIDC 사용자를 Default 조직에 추가)
- 팀 매핑 초기화

**실행**:
```bash
./apply-awx-ansible-realm-settings.sh
```

**출력**:
```
✅ SOCIAL_AUTH_OIDC_KEY: awx-oidc
✅ SOCIAL_AUTH_OIDC_SECRET: [secret]
✅ SOCIAL_AUTH_OIDC_OIDC_ENDPOINT: http://192.168.64.26:30002/realms/ansible-realm
✅ SOCIAL_AUTH_OIDC_ORGANIZATION_MAP 설정 완료
✅ SOCIAL_AUTH_OIDC_TEAM_MAP 설정 완료
```

**후속 작업**:
```bash
# AWX Web Pod 재시작 (OIDC 설정 적용)
kubectl rollout restart deployment/awx-web -n awx
kubectl rollout status deployment/awx-web -n awx
```

---

### 3단계: AWX Teams 및 OIDC 매핑 설정

**스크립트**: `setup-awx-teams-and-permissions.sh`

**기능**:
- AWX에 developer 팀 생성 (Default 조직에 속함)
- developer 팀에 조직 관리자 권한 부여
- OIDC 조직 매핑 업데이트 (사용자를 조직 관리자로 자동 추가)
- OIDC 팀 매핑 업데이트 (Keycloak /developer 그룹 → AWX developer 팀)

**실행**:
```bash
./setup-awx-teams-and-permissions.sh
```

**출력**:
```
✅ developer 팀 생성 완료 (ID: 1)
✅ developer 팀에 조직 관리자 권한 부여 완료
✅ Organization Map 업데이트:
   {'Default': {'users': True, 'admins': True, 'remove_users': False, 'remove_admins': False}}
✅ Team Map 업데이트:
   {'developer': {'organization': 'Default', 'users': '/developer', 'remove': False}}
```

**후속 작업**:
```bash
# AWX Web Pod 재시작 (팀 매핑 적용)
kubectl rollout restart deployment/awx-web -n awx
```

---

### 4단계: Keycloak 사용자를 developer 그룹에 추가

**스크립트**: `add-users-to-keycloak-group.sh`

**기능**:
- ansible-realm의 모든 사용자 조회
- 각 사용자를 developer 그룹에 추가
- 그룹 멤버십 확인

**실행**:
```bash
./add-users-to-keycloak-group.sh
```

**출력**:
```
✅ developer 그룹 ID: [group-uuid]
  - admin 추가 중...
    ✅ admin → developer 그룹 추가 완료

developer 그룹 멤버:
  - admin (admin@example.com)
```

---

### 5단계: AWX 사용자 권한 수정 (선택사항)

**스크립트**: `fix-awx-user-permissions.sh`

**기능**:
- 이미 AWX에 로그인한 OIDC 사용자 확인
- 사용자를 Default 조직의 관리자로 추가
- 사용자를 developer 팀에 추가

**사용 시점**:
- OIDC 매핑이 제대로 작동하지 않는 경우
- 기존 사용자의 권한을 수동으로 수정해야 하는 경우

**실행**:
```bash
./fix-awx-user-permissions.sh
```

**출력**:
```
OIDC 사용자:
  - admin (ID: 2)

    ✅ admin → Default 조직 관리자
    ✅ admin → developer 팀
```

---

### 6단계: 설정 확인

**스크립트**: `check-keycloak-groups.sh`

**기능**:
- Keycloak ansible-realm의 그룹 목록 확인
- Keycloak ansible-realm의 사용자 목록 확인

**실행**:
```bash
./check-keycloak-groups.sh
```

**출력**:
```
Keycloak ansible-realm Groups:
================================
  - developer (path: /developer)

Keycloak ansible-realm Users:
================================
  - admin (email: admin@example.com)
```

---

## 전체 설정 순서 (한 번에 실행)

```bash
cd /root/ansible-builder/sh

# 1. Keycloak ansible-realm 설정
./configure-awx-ansible-realm.sh

# 2. AWX OIDC 설정 적용
./apply-awx-ansible-realm-settings.sh

# 3. AWX Web Pod 재시작
kubectl rollout restart deployment/awx-web -n awx
kubectl rollout status deployment/awx-web -n awx

# 4. AWX Teams 및 OIDC 매핑 설정
./setup-awx-teams-and-permissions.sh

# 5. AWX Web Pod 재시작 (팀 매핑 적용)
kubectl rollout restart deployment/awx-web -n awx
kubectl rollout status deployment/awx-web -n awx

# 6. Keycloak 사용자를 developer 그룹에 추가
./add-users-to-keycloak-group.sh

# 7. 설정 확인
./check-keycloak-groups.sh
```

---

## OIDC 로그인 흐름

1. **AWX 로그인 페이지 접속**: http://192.168.64.26:30000
2. **"Sign in with OIDC" 클릭**
3. **Keycloak ansible-realm 로그인 페이지로 리다이렉트**
4. **사용자 인증** (admin/admin123)
5. **AWX로 리다이렉트** (OIDC 토큰과 함께)
6. **AWX에서 자동 처리**:
   - 사용자가 없으면 생성
   - Default 조직에 관리자로 추가 (Organization Map 설정)
   - developer 팀에 추가 (Team Map 설정)
7. **AWX 대시보드 접속 완료**

---

## 주요 설정 내용

### Keycloak ansible-realm 설정

| 항목 | 값 |
|------|-----|
| Realm 이름 | ansible-realm |
| Client ID | awx-oidc |
| Client Type | Confidential |
| Client Secret | /root/awx-ansible-realm-client-secret.txt |
| Redirect URIs | http://192.168.64.26:30000/* |
| Test User | admin / admin123 |
| Groups | developer |

### AWX OIDC 설정

| 설정 키 | 값 |
|---------|-----|
| SOCIAL_AUTH_OIDC_KEY | awx-oidc |
| SOCIAL_AUTH_OIDC_SECRET | [from client-secret.txt] |
| SOCIAL_AUTH_OIDC_OIDC_ENDPOINT | http://192.168.64.26:30002/realms/ansible-realm |
| SOCIAL_AUTH_OIDC_VERIFY_SSL | False |

### AWX Organization Map

```python
{
    'Default': {
        'users': True,        # OIDC 사용자를 조직에 추가
        'admins': True,       # OIDC 사용자를 조직 관리자로 설정
        'remove_users': False,
        'remove_admins': False
    }
}
```

### AWX Team Map

```python
{
    'developer': {
        'organization': 'Default',
        'users': '/developer',  # Keycloak 그룹 경로
        'remove': False
    }
}
```

---

## 트러블슈팅

### 문제: Keycloak 연결 실패
**증상**: `curl: (7) Failed to connect to 192.168.64.26 port 30002`
**해결**:
```bash
# Keycloak 상태 확인
kubectl get pods -n awx -l app=keycloak

# Keycloak 로그 확인
kubectl logs -n awx -l app=keycloak --tail=50

# Keycloak 재시작
kubectl rollout restart deployment keycloak -n awx
```

### 문제: ansible-realm이 없음
**증상**: `{"error":"Realm does not exist"}`
**해결**:
```bash
./configure-awx-ansible-realm.sh
```

### 문제: OIDC 로그인 후 팀이 없음
**증상**: 사용자가 로그인했지만 developer 팀이 보이지 않음
**해결**:
```bash
# 팀 매핑 재설정
./setup-awx-teams-and-permissions.sh

# AWX Web Pod 재시작
kubectl rollout restart deployment/awx-web -n awx

# Keycloak 그룹 확인
./check-keycloak-groups.sh

# 사용자가 developer 그룹에 속하지 않은 경우
./add-users-to-keycloak-group.sh
```

### 문제: OIDC 사용자 권한 부족
**증상**: 사용자가 리소스를 볼 수 없음
**해결**:
```bash
# 수동으로 권한 수정
./fix-awx-user-permissions.sh

# AWX UI 새로고침 (F5)
```

---

## 스크립트 파일 목록

| 스크립트 | 목적 | Keycloak URL |
|----------|------|--------------|
| configure-awx-ansible-realm.sh | ansible-realm 초기 설정 | ✅ 30002 |
| apply-awx-ansible-realm-settings.sh | AWX OIDC 설정 적용 | ✅ 30002 |
| setup-awx-teams-and-permissions.sh | AWX 팀 및 매핑 설정 | N/A (AWX API만 사용) |
| add-users-to-keycloak-group.sh | 사용자를 developer 그룹에 추가 | ✅ 30002 |
| check-keycloak-groups.sh | Keycloak 그룹/사용자 확인 | ✅ 30002 |
| fix-awx-user-permissions.sh | 수동 권한 수정 | N/A (AWX API만 사용) |

---

## 참고 사항

### 프로덕션 환경 권장사항
1. **HTTPS 사용**: Keycloak와 AWX 모두 HTTPS로 변경
2. **Secret 관리**: Kubernetes Secret으로 클라이언트 시크릿 관리
3. **비밀번호 정책**: 강력한 비밀번호 정책 적용
4. **SSL 검증**: `SOCIAL_AUTH_OIDC_VERIFY_SSL: True` 설정
5. **감사 로그**: Keycloak 이벤트 로깅 활성화

### 새 사용자 추가 절차
1. Keycloak Admin Console에서 사용자 생성
2. 사용자를 developer 그룹에 추가 (또는 `add-users-to-keycloak-group.sh` 실행)
3. 사용자가 OIDC로 AWX에 로그인
4. AWX가 자동으로 조직 및 팀 매핑 적용

### 추가 그룹 생성 방법
1. Keycloak Admin Console에서 새 그룹 생성 (예: `/operators`)
2. `setup-awx-teams-and-permissions.sh` 수정:
   ```python
   team_map = {
       'developer': {
           'organization': 'Default',
           'users': '/developer',
           'remove': False
       },
       'operators': {
           'organization': 'Default',
           'users': '/operators',
           'remove': False
       }
   }
   ```
3. AWX에서 operators 팀 생성
4. 스크립트 재실행 및 AWX 재시작

---

## 관련 문서
- [Keycloak Documentation](https://www.keycloak.org/documentation)
- [AWX OIDC Authentication](https://docs.ansible.com/automation-controller/latest/html/administration/ent_auth.html#openid-connect-oidc-authentication-settings)
- [Kubernetes Deployment Guide](../k8s-migration/README.md)
