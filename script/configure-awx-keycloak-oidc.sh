#!/bin/bash

echo "=========================================="
echo "AWX Keycloak OIDC 인증 설정"
echo "=========================================="
echo ""

# 설정 변수
KEYCLOAK_URL="http://192.168.64.26:30002"
KEYCLOAK_REALM="master"
KEYCLOAK_ADMIN="admin"
KEYCLOAK_ADMIN_PASSWORD="admin123"
AWX_URL="http://192.168.64.26"

echo "1. Keycloak에 AWX 클라이언트 생성 중..."

# Keycloak 관리자 토큰 획득
ADMIN_TOKEN=$(curl -s -X POST "${KEYCLOAK_URL}/realms/master/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=${KEYCLOAK_ADMIN}" \
  -d "password=${KEYCLOAK_ADMIN_PASSWORD}" \
  -d "grant_type=password" \
  -d "client_id=admin-cli" | jq -r '.access_token')

if [ -z "$ADMIN_TOKEN" ] || [ "$ADMIN_TOKEN" == "null" ]; then
    echo "❌ Keycloak 관리자 토큰 획득 실패"
    echo "응답:" 
    curl -s -X POST "${KEYCLOAK_URL}/realms/master/protocol/openid-connect/token" \
      -H "Content-Type: application/x-www-form-urlencoded" \
      -d "username=${KEYCLOAK_ADMIN}" \
      -d "password=${KEYCLOAK_ADMIN_PASSWORD}" \
      -d "grant_type=password" \
      -d "client_id=admin-cli"
    exit 1
fi
echo "✅ Keycloak 관리자 토큰 획득 완료"

# AWX OIDC 클라이언트 생성
echo ""
echo "2. AWX OIDC 클라이언트 생성 중..."

# 기존 클라이언트 확인
EXISTING_CLIENT=$(curl -s -X GET "${KEYCLOAK_URL}/admin/realms/${KEYCLOAK_REALM}/clients" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" | jq -r '.[] | select(.clientId=="awx-oidc") | .id')

if [ ! -z "$EXISTING_CLIENT" ] && [ "$EXISTING_CLIENT" != "null" ]; then
    echo "⚠️  AWX OIDC 클라이언트가 이미 존재합니다 (ID: ${EXISTING_CLIENT}). 삭제 후 재생성..."
    curl -s -X DELETE "${KEYCLOAK_URL}/admin/realms/${KEYCLOAK_REALM}/clients/${EXISTING_CLIENT}" \
      -H "Authorization: Bearer ${ADMIN_TOKEN}"
    echo "✅ 기존 클라이언트 삭제 완료"
fi

# Client Secret 생성
CLIENT_SECRET=$(openssl rand -hex 32)

# 새 클라이언트 생성
CREATE_RESPONSE=$(curl -s -X POST "${KEYCLOAK_URL}/admin/realms/${KEYCLOAK_REALM}/clients" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "clientId": "awx-oidc",
    "name": "AWX OIDC Client",
    "description": "AWX authentication via Keycloak OIDC",
    "enabled": true,
    "clientAuthenticatorType": "client-secret",
    "secret": "'${CLIENT_SECRET}'",
    "redirectUris": [
      "http://192.168.64.26/*",
      "http://192.168.64.26:80/*",
      "http://localhost/*",
      "http://192.168.64.26:30000/*"
    ],
    "webOrigins": [
      "http://192.168.64.26",
      "http://localhost",
      "+"
    ],
    "protocol": "openid-connect",
    "publicClient": false,
    "standardFlowEnabled": true,
    "implicitFlowEnabled": false,
    "directAccessGrantsEnabled": true,
    "serviceAccountsEnabled": true,
    "authorizationServicesEnabled": false,
    "fullScopeAllowed": true,
    "attributes": {
      "access.token.lifespan": "3600"
    }
  }')

echo "✅ AWX OIDC 클라이언트 생성 완료"
echo "   Client ID: awx-oidc"
echo "   Client Secret: ${CLIENT_SECRET}"

# Client Secret 저장
echo "${CLIENT_SECRET}" > /root/awx-oidc-client-secret.txt
chmod 600 /root/awx-oidc-client-secret.txt

echo ""
echo "3. AWX OIDC 설정 정보:"
echo "=========================================="
cat << SETTINGS
OIDC Key: awx-oidc
OIDC Secret: ${CLIENT_SECRET}
OIDC Provider URL: ${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}

엔드포인트:
- Authorization: ${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}/protocol/openid-connect/auth
- Token: ${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}/protocol/openid-connect/token
- UserInfo: ${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}/protocol/openid-connect/userinfo
SETTINGS

echo ""
echo "=========================================="
echo "✅ Keycloak 클라이언트 생성 완료!"
echo "=========================================="
echo ""
echo "Client Secret 저장 위치: /root/awx-oidc-client-secret.txt"
echo ""
