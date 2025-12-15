#!/bin/bash

echo "====================================="
echo "모든 서비스 정지 중..."
echo "====================================="
echo ""

# 1. Backend 정지
echo "1. Backend 정지 중..."
pkill -f "uvicorn main:app" || true
sleep 2
echo "  ✅ Backend 정지 완료"
echo ""

# 2. AWX 정지
echo "2. AWX 정지 중..."
kubectl scale deployment awx-web --replicas=0 -n awx
kubectl scale deployment awx-task --replicas=0 -n awx
sleep 5
echo "  ✅ AWX 정지 완료"
kubectl get pods -n awx
echo ""

# 3. Keycloak 정지
echo "3. Keycloak 정지 중..."
docker stop keycloak
docker stop keycloak-postgres
echo "  ✅ Keycloak 정지 완료"
echo ""

echo "====================================="
echo "모든 서비스 정지 완료!"
echo "====================================="
echo ""
echo "참고: "
echo "  - AWX PostgreSQL은 Kubernetes에서 계속 실행됩니다."
echo "  - AWX를 정지하려면 다음 명령을 실행하세요:"
echo "    kubectl scale statefulset awx-postgres-15 --replicas=0 -n awx"
echo ""
