# Ansible Builder Kubernetes 배포 가이드

## 개요
이 디렉토리는 Ansible Builder와 Keycloak SSO를 Kubernetes에 배포하기 위한 manifest 파일들을 포함합니다.

## 아키텍처
- **Keycloak**: SSO 인증 서버 (Port 30002)
- **Ansible Builder Frontend**: React 기반 UI (Port 30001)
- **Ansible Builder Backend**: FastAPI 기반 API 서버
- **PostgreSQL**: Keycloak 데이터베이스

## 배포 순서

### 1. Keycloak 데이터베이스 배포
```bash
kubectl apply -f 02-keycloak-db.yaml
```

### 2. Keycloak 배포
```bash
kubectl apply -f 03-keycloak.yaml
```

Keycloak이 완전히 시작될 때까지 대기 (약 1-2분):
```bash
kubectl wait --for=condition=ready pod -l app=keycloak -n awx --timeout=300s
```

### 3. ansible-realm 설정
Keycloak에 ansible-realm과 클라이언트를 생성:
```bash
# Keycloak URL을 30002 포트로 업데이트
sed -i 's|:8080|:30002|g' /root/configure-awx-ansible-realm.sh

# ansible-realm 생성
/root/configure-awx-ansible-realm.sh

# ansible-builder-client 생성
cat > /tmp/create-ansible-builder-client.sh <<'EOFSCRIPT'
#!/bin/bash
KEYCLOAK_URL="http://192.168.64.26:30002"
REALM="ansible-realm"

TOKEN=$(curl -s -X POST "${KEYCLOAK_URL}/realms/master/protocol/openid-connect/token" \
  -d "client_id=admin-cli" \
  -d "username=admin" \
  -d "password=admin123" \
  -d "grant_type=password" | jq -r '.access_token')

curl -s -X POST "${KEYCLOAK_URL}/admin/realms/${REALM}/clients" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "clientId": "ansible-builder-client",
    "enabled": true,
    "publicClient": true,
    "redirectUris": ["http://192.168.64.26:30001/*"],
    "webOrigins": ["http://192.168.64.26:30001"],
    "standardFlowEnabled": true,
    "implicitFlowEnabled": false,
    "directAccessGrantsEnabled": true,
    "protocol": "openid-connect"
  }'
echo "✅ ansible-builder-client created"
EOFSCRIPT

chmod +x /tmp/create-ansible-builder-client.sh
/tmp/create-ansible-builder-client.sh
```

### 4. Docker 이미지 준비

#### Backend 이미지
```bash
cd /root/ansible-builder/ansible-builder/backend
docker build -t ansible-builder-backend:v2 .
docker save ansible-builder-backend:v2 | ctr -n=k8s.io images import -
```

#### Frontend 이미지
Frontend는 올바른 Keycloak URL로 빌드되어야 합니다:
```bash
cd /root/ansible-builder/ansible-builder/frontend/frontend

# keycloak.js에서 포트 30002 사용 확인
cat > src/keycloak.js <<'EOF'
/**
 * Keycloak 클라이언트 설정
 * AWX와 통합 인증을 위한 Keycloak 초기화
 */
import Keycloak from 'keycloak-js';

// Keycloak 인스턴스 생성
const keycloak = new Keycloak({
  url: 'http://192.168.64.26:30002',
  realm: 'ansible-realm',
  clientId: 'ansible-builder-client'
});

export default keycloak;
EOF

# 로컬 빌드
rm -rf node_modules package-lock.json dist
npm install
npm run build

# Docker 이미지 생성 (pre-built dist 사용)
cat > /tmp/Dockerfile.simple <<'EOF'
FROM nginx:stable-alpine
COPY dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
EOF

docker build -f /tmp/Dockerfile.simple -t ansible-builder-frontend:v5 .
docker save ansible-builder-frontend:v5 | ctr -n=k8s.io images import -
```

### 5. Ansible Builder 배포
```bash
kubectl apply -f 04-ansible-builder.yaml
```

## 배포 확인

### Pod 상태 확인
```bash
kubectl get pods -n awx
```

모든 파드가 Running 상태여야 합니다:
- keycloak-*
- keycloak-postgres-*
- ansible-backend-*
- ansible-frontend-*

### 서비스 확인
```bash
kubectl get svc -n awx
```

### 접속 테스트
- **Frontend**: http://192.168.64.26:30001
- **Keycloak**: http://192.168.64.26:30002
- **Keycloak Admin**: http://192.168.64.26:30002/admin
  - Username: `admin`
  - Password: `admin123`

### 로그 확인
```bash
# Frontend 로그
kubectl logs -n awx -l app=ansible-frontend

# Backend 로그
kubectl logs -n awx -l app=ansible-backend

# Keycloak 로그
kubectl logs -n awx -l app=keycloak
```

## 설정 정보

### Keycloak
- **Admin Console**: http://192.168.64.26:30002/admin
- **Admin User**: admin / admin123
- **Realm**: ansible-realm
- **Clients**:
  - `ansible-builder-client` (Public Client)
  - `awx-oidc` (Confidential Client)

### Backend 환경 변수
ConfigMap `ansible-backend-env`에 정의:
- `KEYCLOAK_SERVER_URL`: http://192.168.64.26:30002
- `KEYCLOAK_REALM`: ansible-realm
- `KEYCLOAK_CLIENT_ID`: ansible-builder-client
- `AWX_URL`: http://192.168.64.26:30000
- `DATABASE_URL`: PostgreSQL connection string

### Frontend 설정
- Keycloak URL이 빌드 시 번들에 포함됨
- 이미지: ansible-builder-frontend:v5

## 재배포

Pod를 재시작해도 설정이 유지되도록 구성되어 있습니다:

### Frontend 재배포
```bash
kubectl rollout restart deployment ansible-frontend -n awx
```

### Backend 재배포
```bash
kubectl rollout restart deployment ansible-backend -n awx
```

### Keycloak 재배포
```bash
kubectl rollout restart deployment keycloak -n awx
```

**주의**: Keycloak을 재배포하면 realm 설정(ansible-realm, clients)을 다시 생성해야 합니다.

## 트러블슈팅

### Frontend가 8080 포트로 리다이렉트하는 경우
1. Frontend 이미지가 v5인지 확인:
   ```bash
   kubectl get deployment ansible-frontend -n awx -o jsonpath='{.spec.template.spec.containers[0].image}'
   ```

2. 이미지 재빌드 및 재배포 (위의 Frontend 이미지 빌드 참조)

### Backend에서 Keycloak 연결 실패
1. ConfigMap 확인:
   ```bash
   kubectl get configmap ansible-backend-env -n awx -o yaml
   ```

2. KEYCLOAK_SERVER_URL이 30002 포트를 사용하는지 확인

3. ConfigMap 업데이트 후 재배포:
   ```bash
   kubectl apply -f 04-ansible-builder.yaml
   kubectl rollout restart deployment ansible-backend -n awx
   ```

### ansible-realm이 없는 경우
위의 "3. ansible-realm 설정" 단계를 다시 실행하세요.

## 완전 재배포

모든 것을 처음부터 다시 배포:
```bash
# 삭제
kubectl delete -f 04-ansible-builder.yaml
kubectl delete -f 03-keycloak.yaml
kubectl delete -f 02-keycloak-db.yaml

# 재배포 (위의 배포 순서 참조)
kubectl apply -f 02-keycloak-db.yaml
kubectl apply -f 03-keycloak.yaml
# Keycloak 시작 대기 후...
kubectl apply -f 04-ansible-builder.yaml
```

## 참고 사항
- 프로덕션 환경에서는 HTTPS 사용을 권장합니다
- 데이터베이스 비밀번호는 Kubernetes Secret으로 관리하는 것이 좋습니다
- NodePort 대신 LoadBalancer 또는 Ingress 사용을 고려하세요
