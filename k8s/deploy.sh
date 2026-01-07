#!/bin/bash
# ==========================================
# Ansible Builder - 빌드 및 배포 스크립트
# ==========================================
# 사용법: ./deploy.sh [version]
# 예시: ./deploy.sh v18
# ==========================================

set -e

VERSION=${1:-v17}
NAMESPACE="awx"
IMAGE_NAME="ansible-builder-backend"

echo "=========================================="
echo "Ansible Builder 배포 시작"
echo "버전: $VERSION"
echo "=========================================="

# 1. Frontend 빌드
echo ""
echo "[1/5] Frontend 빌드 중..."
cd /root/ansible-builder/ansible-builder/frontend/frontend
npm run build

# 2. Frontend dist를 backend에 복사 (Docker 빌드 컨텍스트 내에 포함)
echo ""
echo "[2/5] Frontend dist 복사 중..."
mkdir -p /root/ansible-builder/ansible-builder/backend/static
cp -r /root/ansible-builder/ansible-builder/frontend/frontend/dist/* /root/ansible-builder/ansible-builder/backend/static/

# 3. Docker 이미지 빌드
echo ""
echo "[3/5] Docker 이미지 빌드 중..."
cd /root/ansible-builder/ansible-builder/backend
docker build -f Dockerfile.airgap -t ${IMAGE_NAME}:${VERSION} .

# 4. containerd로 이미지 가져오기
echo ""
echo "[4/5] Kubernetes로 이미지 import 중..."
docker save ${IMAGE_NAME}:${VERSION} | ctr -n=k8s.io images import -

# 4. Kubernetes ConfigMap/Secret 적용
echo ""
echo "[4/5] ConfigMap/Secret 적용 중..."
kubectl apply -f /root/ansible-builder/k8s/configmap.yaml
kubectl apply -f /root/ansible-builder/k8s/secret.yaml
# 참고: Service는 이미 존재하므로 별도 적용 불필요
# 필요시: kubectl apply -f /root/ansible-builder/k8s/service.yaml

# 5. Deployment 업데이트 및 롤아웃
echo ""
echo "[5/5] Deployment 업데이트 중..."
kubectl set image deployment/ansible-backend backend=docker.io/library/${IMAGE_NAME}:${VERSION} -n ${NAMESPACE}
kubectl rollout restart deployment/ansible-backend -n ${NAMESPACE}
kubectl rollout status deployment/ansible-backend -n ${NAMESPACE}

echo ""
echo "=========================================="
echo "✅ 배포 완료!"
echo "버전: $VERSION"
echo "접속 URL: http://$(hostname -I | awk '{print $1}'):30001"
echo "=========================================="
