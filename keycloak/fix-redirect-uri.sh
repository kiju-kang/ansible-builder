#!/bin/bash

# Keycloak Client Redirect URI 수정 스크립트

set -e

REALM_NAME="ansible-realm"
CLIENT_ID="ansible-builder-client"

echo "=========================================="
echo "Keycloak Client Redirect URI 수정"
echo "=========================================="

# Keycloak 컨테이너 확인
if ! docker ps | grep -q keycloak; then
    echo "✗ Keycloak 컨테이너가 실행 중이지 않습니다"
    exit 1
fi

echo ""
echo "[1/3] Keycloak Admin 로그인 중..."
docker exec keycloak /opt/keycloak/bin/kcadm.sh config credentials \
    --server http://localhost:8080 \
    --realm master \
    --user admin \
    --password admin123 2>&1 | grep -v "Logging" || true

echo "✓ 로그인 완료"

echo ""
echo "[2/3] ansible-builder-client ID 조회 중..."
CLIENT_UUID=$(docker exec keycloak /opt/keycloak/bin/kcadm.sh get clients \
    -r $REALM_NAME \
    --fields id,clientId \
    2>/dev/null | jq -r '.[] | select(.clientId=="'$CLIENT_ID'") | .id')

if [ -z "$CLIENT_UUID" ] || [ "$CLIENT_UUID" == "null" ]; then
    echo "✗ Client를 찾을 수 없습니다: $CLIENT_ID"
    exit 1
fi

echo "✓ Client ID: $CLIENT_UUID"

echo ""
echo "[3/3] Redirect URIs 업데이트 중..."

# Redirect URIs 및 Web Origins 업데이트
docker exec keycloak /opt/keycloak/bin/kcadm.sh update clients/$CLIENT_UUID \
    -r $REALM_NAME \
    -s 'redirectUris=["http://192.168.64.26:8000/*","http://192.168.64.26:8000","http://192.168.64.26:3000/*","http://localhost:8000/*","http://localhost:3000/*"]' \
    -s 'webOrigins=["+"]' 2>&1 | grep -v "^$" || true

echo "✓ Redirect URIs 업데이트 완료"

# 설정 확인
echo ""
echo "=========================================="
echo "현재 설정 확인"
echo "=========================================="

docker exec keycloak /opt/keycloak/bin/kcadm.sh get clients/$CLIENT_UUID \
    -r $REALM_NAME \
    --fields clientId,redirectUris,webOrigins \
    2>/dev/null | jq '.'

echo ""
echo "=========================================="
echo "Redirect URI 수정 완료!"
echo "=========================================="
echo ""
echo "설정된 Redirect URIs:"
echo "  - http://192.168.64.26:8000/*"
echo "  - http://192.168.64.26:8000"
echo "  - http://192.168.64.26:3000/*"
echo "  - http://localhost:8000/*"
echo "  - http://localhost:3000/*"
echo ""
echo "이제 Ansible Builder에서 SSO 로그인을 시도하세요!"
echo "URL: http://192.168.64.26:8000"
echo ""
