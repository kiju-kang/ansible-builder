# Ansible Builder Kubernetes 배포 현황

**최종 업데이트**: 2025-12-15

## 배포된 구성 요소

### 1. Keycloak (SSO 인증 서버)
- **이미지**: quay.io/keycloak/keycloak:23.0
- **포트**: 8080 (내부), 30002 (NodePort)
- **Admin 계정**: admin / admin123
- **데이터베이스**: keycloak-postgres (PostgreSQL)
- **Manifest**: `03-keycloak.yaml`

### 2. Ansible Builder Frontend
- **이미지**: ansible-builder-frontend:v5
- **포트**: 80 (내부), 30001 (NodePort)
- **Keycloak 설정**:
  - URL: http://192.168.64.26:30002
  - Realm: ansible-realm
  - Client ID: ansible-builder-client
- **Manifest**: `04-ansible-builder.yaml` (frontend 섹션)

### 3. Ansible Builder Backend
- **이미지**: ansible-builder-backend:v2
- **포트**: 8000 (ClusterIP)
- **환경 변수**: ConfigMap `ansible-backend-env`로 관리
- **Manifest**: `04-ansible-builder.yaml` (backend 섹션 + ConfigMap)

## 주요 설정 변경 사항

### Keycloak URL 수정
모든 컴포넌트에서 Keycloak URL이 올바른 NodePort(30002)를 사용하도록 수정:
- ❌ 이전: `http://192.168.64.26:8080` 또는 `http://localhost:8080`
- ✅ 현재: `http://192.168.64.26:30002`

### Frontend 빌드
- keycloak.js에서 환경 변수 fallback 제거
- 하드코딩된 URL 사용으로 변경
- 이유: Vite 빌드 시 환경 변수가 올바르게 번들되지 않는 문제 해결

### Backend 설정
- .env 파일을 ConfigMap으로 관리
- Pod 재시작 시에도 설정 유지
- volumeMount를 통해 /app/.env에 마운트

## Keycloak 설정

### Realms
1. **master** (기본)
   - Admin 계정 관리

2. **ansible-realm** (커스텀)
   - Ansible Builder 및 AWX용 realm
   - 테스트 사용자: admin / admin123

### Clients (ansible-realm)
1. **ansible-builder-client**
   - Type: Public Client
   - Protocol: openid-connect
   - Redirect URIs: http://192.168.64.26:30001/*
   - Web Origins: http://192.168.64.26:30001
   - Direct Access Grants: Enabled

2. **awx-oidc**
   - Type: Confidential Client
   - Protocol: openid-connect
   - Client Secret: (저장됨)

## 접속 정보

### 사용자 URL
- **Ansible Builder UI**: http://192.168.64.26:30001
- **Keycloak Login**: http://192.168.64.26:30002/realms/ansible-realm
- **AWX**: http://192.168.64.26:30000

### 관리자 URL
- **Keycloak Admin Console**: http://192.168.64.26:30002/admin
  - Username: admin
  - Password: admin123

## 영속성 (Persistence)

### 파드 재시작 시 유지되는 것
✅ Backend 환경 변수 (ConfigMap)
✅ Frontend Keycloak 설정 (이미지에 번들됨)
✅ Keycloak 데이터베이스 (PVC 사용)

### 파드 재시작 시 재설정 필요한 것
⚠️ Keycloak realm 및 clients (DB에 저장되지만 Keycloak 파드 재생성 시 재설정 권장)

## 배포 검증

### Pod 상태 확인
```bash
kubectl get pods -n awx
```

예상 출력:
```
NAME                                READY   STATUS    RESTARTS   AGE
ansible-backend-*                   1/1     Running   0          *
ansible-frontend-*                  1/1     Running   0          *
keycloak-*                          1/1     Running   0          *
keycloak-postgres-*                 1/1     Running   0          *
```

### 서비스 확인
```bash
kubectl get svc -n awx
```

예상 출력:
```
NAME                TYPE        CLUSTER-IP       PORT(S)          AGE
ansible-frontend    NodePort    *                80:30001/TCP     *
backend             ClusterIP   *                8000/TCP         *
keycloak            NodePort    *                8080:30002/TCP   *
keycloak-postgres   ClusterIP   *                5432/TCP         *
```

### ConfigMap 확인
```bash
kubectl get configmap -n awx ansible-backend-env -o yaml
```

KEYCLOAK_SERVER_URL이 `http://192.168.64.26:30002`여야 함

### 이미지 확인
```bash
kubectl get deployment -n awx ansible-frontend -o jsonpath='{.spec.template.spec.containers[0].image}'
# 출력: ansible-builder-frontend:v5

kubectl get deployment -n awx ansible-backend -o jsonpath='{.spec.template.spec.containers[0].image}'
# 출력: ansible-builder-backend:v2
```

## 재배포 절차

### 단순 재시작 (설정 변경 없음)
```bash
# Frontend만 재시작
kubectl rollout restart deployment ansible-frontend -n awx

# Backend만 재시작
kubectl rollout restart deployment ansible-backend -n awx

# 모두 재시작
kubectl rollout restart deployment -n awx
```

### 설정 변경 후 재배포
```bash
# Manifest 수정 후
kubectl apply -f /root/ansible-builder/k8s-migration/04-ansible-builder.yaml

# 변경 사항 확인
kubectl rollout status deployment ansible-frontend -n awx
kubectl rollout status deployment ansible-backend -n awx
```

### Keycloak 재배포 시
```bash
# Keycloak 재시작
kubectl rollout restart deployment keycloak -n awx

# Keycloak 완전 시작 대기 (약 1-2분)
kubectl wait --for=condition=ready pod -l app=keycloak -n awx --timeout=300s

# ansible-realm 재생성
/root/configure-awx-ansible-realm.sh
/tmp/create-ansible-builder-client.sh
```

## 트러블슈팅 가이드

### 문제: Frontend가 8080 포트로 리다이렉트
**원인**: Frontend 이미지가 이전 버전 또는 캐시된 빌드 사용

**해결**:
1. 이미지 버전 확인: `kubectl get deployment ansible-frontend -n awx -o jsonpath='{.spec.template.spec.containers[0].image}'`
2. v5가 아닌 경우: README.md의 "Frontend 이미지" 섹션 참조하여 재빌드
3. 재배포: `kubectl rollout restart deployment ansible-frontend -n awx`

### 문제: Backend에서 "Realm does not exist" 에러
**원인**: ansible-realm이 생성되지 않음

**해결**:
```bash
/root/configure-awx-ansible-realm.sh
/tmp/create-ansible-builder-client.sh
```

### 문제: Keycloak 접속 불가 (Connection refused)
**원인**: Keycloak이 아직 시작 중

**해결**:
1. 로그 확인: `kubectl logs -n awx -l app=keycloak --tail=50`
2. 시작 완료 대기 (1-2분 소요)
3. Health check: `curl http://192.168.64.26:30002/`

### 문제: Backend ConfigMap 변경이 반영 안 됨
**원인**: ConfigMap 변경은 파드 재시작 필요

**해결**:
```bash
kubectl apply -f 04-ansible-builder.yaml
kubectl rollout restart deployment ansible-backend -n awx
```

## 보안 고려사항

### 현재 상태
⚠️ HTTP 사용 (암호화 없음)
⚠️ 하드코딩된 비밀번호 (manifest 파일에 포함)
⚠️ NodePort 사용 (외부 노출)

### 프로덕션 권장사항
1. HTTPS/TLS 사용
2. Kubernetes Secrets로 비밀번호 관리
3. Ingress + TLS 사용
4. Network Policy 적용
5. RBAC 설정
6. 비밀번호 정기 변경

## 백업 및 복구

### 백업해야 할 항목
1. Keycloak 데이터베이스 (PVC)
2. ansible-realm 설정 (export 가능)
3. Docker 이미지 (ansible-builder-frontend:v5, ansible-builder-backend:v2)
4. Manifest 파일 (k8s-migration 디렉토리)

### 복구 절차
1. Manifest 파일로 리소스 재생성
2. Docker 이미지 재임포트
3. Keycloak realm 재설정

## 참조 문서
- [README.md](./README.md) - 상세 배포 가이드
- [Keycloak Documentation](https://www.keycloak.org/documentation)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
