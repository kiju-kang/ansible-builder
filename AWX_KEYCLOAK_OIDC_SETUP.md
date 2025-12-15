# AWX Keycloak OIDC 통합 설정 완료

## 📋 설정 개요

Keycloak SSO로 인증된 사용자가 AWX에서 자동으로 권한을 받을 수 있도록 OIDC 통합을 설정했습니다.

### 해결된 문제
- ❌ **이전**: Keycloak SSO 로그인 → AWX에서 권한 없음
- ✅ **현재**: Keycloak SSO 로그인 → AWX에 자동 계정 생성 + Default 조직 권한 부여

---

## 🔧 설정 내용

### 1. Keycloak 클라이언트 생성

**Client ID**: `awx-oidc`  
**Client Type**: Confidential  
**Valid Redirect URIs**:
- `http://192.168.64.26/*`
- `http://192.168.64.26:30000/*`
- `http://localhost/*`

**Client Secret**: `/root/awx-oidc-client-secret.txt` 파일에 저장됨

### 2. AWX OIDC 설정

다음 설정이 AWX에 적용되었습니다:

| 설정 항목 | 값 |
|-----------|-----|
| `SOCIAL_AUTH_OIDC_KEY` | `awx-oidc` |
| `SOCIAL_AUTH_OIDC_SECRET` | (파일 참조) |
| `SOCIAL_AUTH_OIDC_OIDC_ENDPOINT` | `http://192.168.64.26:8080/realms/master` |
| `SOCIAL_AUTH_OIDC_VERIFY_SSL` | `false` |
| `SOCIAL_AUTH_OIDC_ORGANIZATION_MAP` | `{"Default": {"users": true}}` |

**의미**:
- Keycloak master realm을 인증 제공자로 사용
- SSL 검증 비활성화 (HTTP 환경)
- 모든 OIDC 사용자를 AWX의 "Default" 조직에 자동 추가

---

## 🚀 사용 방법

### 1. AWX에서 OIDC로 로그인

1. **AWX 접속**: http://192.168.64.26:30000
2. 로그인 페이지에서 **"Sign in with OIDC"** 버튼 클릭
3. Keycloak 로그인 페이지로 리디렉션
4. Keycloak 계정으로 로그인:
   - Username: `admin` (또는 다른 Keycloak 사용자)
   - Password: `admin123`
5. AWX로 자동 리디렉션 → Default 조직 권한으로 로그인 완료

### 2. Ansible Builder에서 AWX 연동

Ansible Builder에서 AWX로 리디렉션할 때 사용자 정보도 함께 전달됩니다:

```javascript
// Frontend에서 AWX로 리디렉션 시
window.open(`http://192.168.64.26:30000/#/jobs`, '_blank');
```

사용자가 이미 Keycloak으로 로그인되어 있으면, AWX에서도 자동으로 인증됩니다.

---

## 🧪 테스트

### 새 사용자 생성 및 테스트

1. **Keycloak에서 테스트 사용자 생성**:
   ```bash
   # Keycloak Admin Console 접속
   # http://192.168.64.26:8080
   # 
   # Users > Add User
   #   Username: testuser
   #   Email: testuser@example.com
   #   Email Verified: ON
   # 
   # Credentials 탭
   #   Password: test123
   #   Temporary: OFF
   ```

2. **AWX에서 OIDC 로그인 테스트**:
   - http://192.168.64.26:30000
   - "Sign in with OIDC" 클릭
   - testuser / test123로 로그인
   - AWX에서 자동으로 계정 생성 확인

3. **권한 확인**:
   - AWX > Users 메뉴에서 testuser 생성 확인
   - Default 조직 멤버십 확인

---

## 🔍 문제 해결

### OIDC 버튼이 보이지 않음

**원인**: AWX Web pod가 설정을 아직 로드하지 않음

**해결**:
```bash
kubectl rollout restart deployment/awx-web -n awx
```

### 로그인 후 권한 없음

**원인**: Organization Map 설정 문제

**확인**:
```bash
AWX_WEB_POD=$(kubectl get pods -n awx -l app.kubernetes.io/name=awx-web -o jsonpath='{.items[0].metadata.name}')
kubectl exec -it ${AWX_WEB_POD} -n awx -- awx-manage shell << 'EOF'
from awx.conf.models import Setting
print(Setting.objects.get(key='SOCIAL_AUTH_OIDC_ORGANIZATION_MAP').value)
