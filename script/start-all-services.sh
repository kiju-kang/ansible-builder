#!/bin/bash

echo "====================================="
echo "모든 서비스 시작 중..."
echo "====================================="
echo ""

# 1. PostgreSQL 확인 (Kubernetes에서 실행 중)
echo "1. PostgreSQL 확인 중 (AWX Kubernetes)..."
if kubectl get pod awx-postgres-15-0 -n awx 2>/dev/null | grep -q Running; then
    echo "  ✅ PostgreSQL pod running"
else
    echo "  ⚠️  PostgreSQL pod not running - starting AWX first"
fi
echo ""

# 2. Keycloak 시작
echo "2. Keycloak 시작 중..."
docker start keycloak-postgres
sleep 5
docker start keycloak
sleep 10
docker ps | grep keycloak
echo ""

# 3. AWX 시작
echo "3. AWX 시작 중..."
kubectl scale deployment awx-web --replicas=1 -n awx
kubectl scale deployment awx-task --replicas=1 -n awx
echo "AWX pods 시작 대기 중..."
# Wait for deployments to be ready (not all pods, as migration is Completed)
kubectl rollout status deployment/awx-web -n awx --timeout=120s 2>/dev/null || echo "  ⚠️  awx-web taking longer than expected"
kubectl rollout status deployment/awx-task -n awx --timeout=120s 2>/dev/null || echo "  ⚠️  awx-task taking longer than expected"
kubectl get pods -n awx | grep -E "NAME|awx-web|awx-task|awx-postgres"
echo ""

# 4. Backend 시작
echo "4. Backend 시작 중..."
cd /root/ansible-builder/ansible-builder/backend
# 기존 프로세스 종료
pkill -f "uvicorn main:app" || true
sleep 2
# 새로 시작
nohup uvicorn main:app --host 0.0.0.0 --port 8000 --reload > backend.log 2>&1 &
sleep 5
echo ""

# 5. 상태 확인
echo "====================================="
echo "서비스 상태 확인"
echo "====================================="
echo ""

echo "Backend (Port 8000):"
if curl -s http://localhost:8000/docs > /dev/null; then
    echo "  ✅ Running"
else
    echo "  ❌ Not responding"
fi
echo ""

echo "Keycloak (Port 8080):"
if curl -s http://localhost:8080/health > /dev/null; then
    echo "  ✅ Running"
else
    echo "  ⚠️  Starting... (may take a minute)"
fi
echo ""

echo "AWX Pods:"
kubectl get pods -n awx --no-headers | awk '{print "  "$1": "$3}'
echo ""

echo "====================================="
echo "모든 서비스 시작 완료!"
echo "====================================="
echo ""
echo "접속 URL:"
echo "  - Ansible Builder: http://192.168.64.26:8000"
echo "  - Keycloak Admin: http://192.168.64.26:8080"
echo "  - AWX: http://192.168.64.26"
echo ""
