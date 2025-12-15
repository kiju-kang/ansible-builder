# AWX Keycloak OIDC 통합 완료 요약

## ✅ 완료된 작업

### 1. Keycloak OIDC 클라이언트 생성
- **Client ID**: `awx-oidc`
- **Client Secret**: `/root/awx-oidc-client-secret.txt`에 저장
- **Redirect URIs**: `http://192.168.64.26:30000/*` 등

### 2. AWX OIDC 설정 적용
```
SOCIAL_AUTH_OIDC_KEY: awx-oidc
SOCIAL_AUTH_OIDC_OIDC_ENDPOINT: http://192.168.64.26:8080/realms/master
SOCIAL_AUTH_OIDC_ORGANIZATION_MAP: {"Default": {"users": true}}
```

### 3. AWX Web Deployment 재시작
- 설정 적용을 위해 재시작 완료

---

## 🚀 테스트 방법

### 1. AWX OIDC 로그인 테스트

```bash
# 1. AWX 접속
http://192.168.64.26:30000

# 2. "Sign in with OIDC" 버튼 클릭

# 3. Keycloak 로그인
Username: admin
Password: admin123

# 4. 자동으로 AWX에 로그인됨 (Default 조직 권한)
```

### 2. 새 사용자 생성 테스트

```bash
# Keycloak Admin Console에서 사용자 생성
http://192.168.64.26:8080

# Users > Add User
# - Username: testuser
# - Email: testuser@example.com
# - Credentials: test123

# AWX에서 OIDC 로그인 시 자동으로 계정 생성됨
```

---

## 📝 해결된 문제

### 문제
Keycloak SSO로 로그인한 사용자가 AWX에 접속할 때 권한이 없어서 화면이 보이지 않음

### 해결
AWX에 Keycloak OIDC 인증을 설정하여:
1. Keycloak으로 로그인한 사용자가 AWX에서 자동으로 계정 생성
2. 자동으로 "Default" 조직에 추가되어 기본 권한 부여
3. Ansible Builder → AWX 리디렉션 시 SSO 세션 유지

---

## 🔧 관련 스크립트

| 스크립트 | 용도 |
|---------|------|
| `/root/configure-awx-keycloak-oidc.sh` | Keycloak 클라이언트 생성 |
| `/root/apply-awx-oidc-settings.sh` | AWX OIDC 설정 적용 (사용 안 함) |
| `/root/awx-oidc-client-secret.txt` | Client Secret (보안) |

---

## 🔄 설정 재적용 방법

만약 설정을 다시 적용해야 한다면:

```bash
# 1. AWX Web Pod 찾기
AWX_WEB_POD=$(kubectl get pods -n awx -l app.kubernetes.io/name=awx-web -o jsonpath='{.items[0].metadata.name}')

# 2. AWX Shell로 설정 적용
kubectl exec -it ${AWX_WEB_POD} -n awx -- awx-manage shell << 'PYTHON_EOF'
from awx.conf.models import Setting

Setting.objects.update_or_create(
    key='SOCIAL_AUTH_OIDC_KEY',
    defaults={'value': 'awx-oidc'}
)
Setting.objects.update_or_create(
    key='SOCIAL_AUTH_OIDC_SECRET',
    defaults={'value': 'YOUR_CLIENT_SECRET'}
)
Setting.objects.update_or_create(
    key='SOCIAL_AUTH_OIDC_OIDC_ENDPOINT',
    defaults={'value': 'http://192.168.64.26:8080/realms/master'}
)
Setting.objects.update_or_create(
    key='SOCIAL_AUTH_OIDC_VERIFY_SSL',
    defaults={'value': False}
)
Setting.objects.update_or_create(
    key='SOCIAL_AUTH_OIDC_ORGANIZATION_MAP',
    defaults={'value': {'Default': {'users': True}}}
)
PYTHON_EOF

# 3. AWX 재시작
kubectl rollout restart deployment/awx-web -n awx
```

---

## 🎯 다음 단계

### Ansible Builder Frontend 수정 (선택사항)

AWX로 리디렉션할 때 SSO 컨텍스트를 함께 전달하려면:

```javascript
// Frontend에서 AWX Job으로 이동
const redirectToAWXJob = (jobId) => {
  // AWX OIDC 로그인 페이지로 리디렉션
  // Keycloak 세션이 있으면 자동으로 AWX에 로그인됨
  window.open(
    `http://192.168.64.26:30000/#/jobs/${jobId}`,
    '_blank'
  );
};
```

---

**상태**: ✅ 설정 완료  
**작성일**: 2025-12-11  
**테스트**: 대기 중 (사용자가 AWX에서 OIDC 로그인 테스트 필요)
