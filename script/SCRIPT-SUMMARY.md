# Ansible Builder 스크립트 요약

## 📋 스크립트 목록 및 상태

### ✅ Keycloak + AWX 통합 스크립트 (30002 포트 사용)

| 스크립트 | 상태 | 포트 | 설명 |
|---------|------|------|------|
| `configure-awx-ansible-realm.sh` | ✅ 수정됨 | 30002 | ansible-realm 초기 설정, awx-oidc 클라이언트 생성 |
| `apply-awx-ansible-realm-settings.sh` | ✅ 수정됨 | 30002 | AWX OIDC 설정을 ansible-realm으로 적용 |
| `setup-awx-teams-and-permissions.sh` | ✅ 정상 | N/A | AWX developer 팀 생성 및 OIDC 매핑 설정 |
| `add-users-to-keycloak-group.sh` | ✅ 정상 | 30002 | 사용자를 developer 그룹에 추가 |
| `check-keycloak-groups.sh` | ✅ 수정됨 | 30002 | Keycloak 그룹 및 사용자 확인 |
| `fix-awx-user-permissions.sh` | ✅ 정상 | N/A | AWX 사용자 권한 수동 수정 |
| `verify-awx-ansible-realm.sh` | ✅ 수정됨 | 30002 | ansible-realm 설정 확인 |

### 🔧 레거시 스크립트 (master realm용, 30002 포트 사용)

| 스크립트 | 상태 | 포트 | 설명 |
|---------|------|------|------|
| `configure-awx-keycloak-oidc.sh` | ✅ 수정됨 | 30002 | master realm에 awx-oidc 클라이언트 생성 (레거시) |
| `apply-awx-oidc-settings.sh` | ✅ 수정됨 | 30002 | AWX OIDC 설정을 master realm으로 적용 (레거시) |
| `fix-redirect-uri.sh` | ✅ 수정됨 | 30002 | master realm의 redirect URI 확인 (레거시) |

### 🛠️ 기타 유틸리티 스크립트

| 스크립트 | 상태 | 설명 |
|---------|------|------|
| `check-services.sh` | ✅ 정상 | 시스템 서비스 상태 확인 (localhost:8080은 정상) |
| `start-all-services.sh` | ✅ 정상 | 모든 서비스 시작 (localhost:8080은 정상) |
| `stop-all-services.sh` | ✅ 정상 | 모든 서비스 중지 |
| `backup-ansible-builder.sh` | ✅ 정상 | 백업 스크립트 |
| `create-ansible-builder-project.sh` | ✅ 정상 | 프로젝트 생성 |
| `assign-instance-group.sh` | ✅ 정상 | Instance Group 할당 |

---

## 🎯 권장 설정 워크플로우

### **ansible-realm 사용 (권장)**

ansible-realm은 AWX 전용 realm으로 더 나은 격리와 관리를 제공합니다.

```bash
# 1단계: ansible-realm 설정
./configure-awx-ansible-realm.sh

# 2단계: AWX OIDC 설정 적용
./apply-awx-ansible-realm-settings.sh

# 3단계: AWX Web Pod 재시작
kubectl rollout restart deployment/awx-web -n awx
kubectl rollout status deployment/awx-web -n awx

# 4단계: AWX Teams 및 매핑 설정
./setup-awx-teams-and-permissions.sh

# 5단계: AWX Web Pod 재시작 (팀 매핑 적용)
kubectl rollout restart deployment/awx-web -n awx

# 6단계: Keycloak 사용자를 그룹에 추가
./add-users-to-keycloak-group.sh

# 7단계: 설정 확인
./check-keycloak-groups.sh
./verify-awx-ansible-realm.sh
```

### **master realm 사용 (레거시)**

이전 방식으로, master realm을 직접 사용합니다. 새로운 설치에는 권장하지 않습니다.

```bash
# 1단계: master realm에 클라이언트 생성
./configure-awx-keycloak-oidc.sh

# 2단계: AWX OIDC 설정 적용
./apply-awx-oidc-settings.sh

# 3단계: AWX Web Pod 재시작
kubectl rollout restart deployment/awx-web -n awx
```

---

## 🔍 주요 수정 사항

### 포트 변경: 8080 → 30002

**이유**: Kubernetes 환경에서 Keycloak은 NodePort 30002로 노출됨

| 변경 전 | 변경 후 |
|---------|---------|
| `http://192.168.64.26:8080` | `http://192.168.64.26:30002` |

**영향받은 스크립트**:
- ✅ configure-awx-ansible-realm.sh
- ✅ apply-awx-ansible-realm-settings.sh
- ✅ check-keycloak-groups.sh
- ✅ verify-awx-ansible-realm.sh
- ✅ configure-awx-keycloak-oidc.sh
- ✅ apply-awx-oidc-settings.sh
- ✅ fix-redirect-uri.sh

**영향받지 않는 스크립트** (localhost:8080 사용):
- ✅ check-services.sh (로컬 health check용)
- ✅ start-all-services.sh (로컬 서비스 시작용)

---

## 📊 Keycloak Realms 비교

### ansible-realm (권장)

**장점**:
- AWX 전용 realm으로 격리
- master realm과 분리된 사용자 관리
- 더 나은 보안 (master realm 노출 최소화)
- 프로덕션 환경에 적합

**설정**:
- Realm: `ansible-realm`
- Client ID: `awx-oidc`
- Client Type: Confidential
- Groups: `developer`
- Users: `admin` (테스트용)

**OIDC Endpoint**:
```
http://192.168.64.26:30002/realms/ansible-realm
```

### master realm (레거시)

**단점**:
- master realm은 Keycloak 관리용
- 애플리케이션 인증에 사용 권장하지 않음
- 보안 위험 증가

**설정**:
- Realm: `master`
- Client ID: `awx-oidc`

**OIDC Endpoint**:
```
http://192.168.64.26:30002/realms/master
```

---

## 🚀 빠른 시작 가이드

### 새로 설치하는 경우

```bash
cd /root/ansible-builder/sh

# 모든 스크립트 실행 (한 번에)
./configure-awx-ansible-realm.sh && \
./apply-awx-ansible-realm-settings.sh && \
kubectl rollout restart deployment/awx-web -n awx && \
kubectl rollout status deployment/awx-web -n awx && \
./setup-awx-teams-and-permissions.sh && \
kubectl rollout restart deployment/awx-web -n awx && \
./add-users-to-keycloak-group.sh

# 설정 확인
./check-keycloak-groups.sh
```

### 기존 설정이 있는 경우

```bash
# Keycloak 그룹 확인
./check-keycloak-groups.sh

# ansible-realm 설정 확인
./verify-awx-ansible-realm.sh

# 필요시 사용자 권한 수정
./fix-awx-user-permissions.sh
```

---

## 🧪 테스트 방법

### 1. Keycloak 접속 테스트
```bash
curl -s http://192.168.64.26:30002/realms/ansible-realm | jq -r '.realm'
# 출력: ansible-realm
```

### 2. OIDC 로그인 테스트
1. AWX 접속: http://192.168.64.26:30000
2. "Sign in with OIDC" 클릭
3. Keycloak ansible-realm 로그인 페이지 확인
4. 사용자 인증: `admin` / `admin123`
5. AWX 대시보드 자동 로그인 확인

### 3. 팀 매핑 확인
1. AWX UI에서 "Teams" 메뉴 확인
2. `developer` 팀이 보이는지 확인
3. 팀 멤버에 OIDC 사용자가 포함되었는지 확인

---

## 🔐 보안 고려사항

### 현재 상태
⚠️ 개발/테스트 환경 설정:
- HTTP 사용 (암호화 없음)
- 하드코딩된 비밀번호
- SSL 검증 비활성화

### 프로덕션 권장사항
✅ 다음 항목들을 적용하세요:

1. **HTTPS 사용**
   ```bash
   KEYCLOAK_URL="https://keycloak.example.com"
   ```

2. **SSL 검증 활성화**
   ```python
   SOCIAL_AUTH_OIDC_VERIFY_SSL: True
   ```

3. **Secret 관리**
   - Kubernetes Secret 사용
   - 파일 권한 강화 (`chmod 600`)
   - 정기적인 시크릿 로테이션

4. **비밀번호 정책**
   - 강력한 비밀번호 요구
   - 정기적인 비밀번호 변경
   - 다중 인증(MFA) 활성화

5. **네트워크 보안**
   - Ingress + TLS 사용
   - Network Policy 적용
   - 방화벽 규칙 설정

---

## 📝 트러블슈팅

### 문제: Connection refused (30002)
```bash
# Keycloak Pod 확인
kubectl get pods -n awx -l app=keycloak

# Keycloak 로그 확인
kubectl logs -n awx -l app=keycloak --tail=50

# Keycloak 재시작
kubectl rollout restart deployment keycloak -n awx
```

### 문제: ansible-realm이 없음
```bash
# realm 재생성
./configure-awx-ansible-realm.sh
```

### 문제: OIDC 로그인 후 권한 없음
```bash
# 팀 매핑 재설정
./setup-awx-teams-and-permissions.sh
kubectl rollout restart deployment/awx-web -n awx

# 사용자 그룹 확인
./check-keycloak-groups.sh

# 필요시 사용자를 그룹에 추가
./add-users-to-keycloak-group.sh

# 수동 권한 수정
./fix-awx-user-permissions.sh
```

### 문제: 스크립트 실행 권한 없음
```bash
chmod +x /root/ansible-builder/sh/*.sh
```

---

## 📚 관련 문서

- [README-KEYCLOAK-AWX-INTEGRATION.md](./README-KEYCLOAK-AWX-INTEGRATION.md) - 상세 통합 가이드
- [../k8s-migration/README.md](../k8s-migration/README.md) - Kubernetes 배포 가이드
- [../k8s-migration/DEPLOYMENT-STATUS.md](../k8s-migration/DEPLOYMENT-STATUS.md) - 배포 현황

---

## ✅ 검증 체크리스트

배포 후 다음 항목들을 확인하세요:

- [ ] Keycloak이 30002 포트로 접근 가능
- [ ] ansible-realm이 생성됨
- [ ] awx-oidc 클라이언트가 ansible-realm에 존재
- [ ] developer 그룹이 생성됨
- [ ] 테스트 사용자 (admin)가 developer 그룹에 속함
- [ ] AWX OIDC 설정이 ansible-realm을 가리킴
- [ ] AWX developer 팀이 생성됨
- [ ] OIDC 팀 매핑이 설정됨 (/developer → developer)
- [ ] OIDC 로그인 성공
- [ ] 로그인 후 developer 팀에 자동 추가됨
- [ ] 조직 관리자 권한 부여됨

---

## 🎉 마무리

모든 스크립트가 Kubernetes 환경(NodePort 30002)에 맞게 업데이트되었습니다!

**다음 단계**:
1. 위의 빠른 시작 가이드를 따라 설정
2. OIDC 로그인 테스트
3. 새 사용자 추가 및 그룹 할당 테스트
4. 프로덕션 배포 시 보안 고려사항 적용

**질문이나 문제가 있으면**:
- 트러블슈팅 섹션 참조
- Keycloak/AWX 로그 확인
- 관련 문서 참조
