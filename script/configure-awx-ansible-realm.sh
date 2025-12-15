#!/bin/bash

echo "=========================================="
echo "AWX ansible-realm 설정 스크립트"
echo "=========================================="
echo ""

KEYCLOAK_URL="http://192.168.64.26:30002"
KEYCLOAK_ADMIN="admin"
KEYCLOAK_ADMIN_PASSWORD="admin123"
AWX_URL="http://192.168.64.26:30000"

# Get admin token
echo "1. Keycloak 관리자 토큰 획득 중..."
ADMIN_TOKEN=$(curl -s -X POST "${KEYCLOAK_URL}/realms/master/protocol/openid-connect/token" \
  -d "client_id=admin-cli" \
  -d "username=${KEYCLOAK_ADMIN}" \
  -d "password=${KEYCLOAK_ADMIN_PASSWORD}" \
  -d "grant_type=password" | jq -r '.access_token')

if [ -z "$ADMIN_TOKEN" ] || [ "$ADMIN_TOKEN" == "null" ]; then
    echo "❌ Keycloak 관리자 토큰 획득 실패"
    exit 1
fi
echo "✅ 토큰 획득 완료"

# Check if ansible-realm exists
echo ""
echo "2. ansible-realm 확인 중..."
REALMS=$(curl -s -X GET "${KEYCLOAK_URL}/admin/realms" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}")

echo "현재 Keycloak Realms:"
echo "$REALMS" | jq -r '.[] | "  - " + .realm + " (enabled: " + (.enabled|tostring) + ")"'

ANSIBLE_REALM=$(echo "$REALMS" | jq -r '.[] | select(.realm == "ansible-realm") | .realm')

if [ -z "$ANSIBLE_REALM" ] || [ "$ANSIBLE_REALM" == "null" ]; then
    echo ""
    echo "⚠️  ansible-realm이 존재하지 않습니다. 생성합니다..."

    # Create ansible-realm
    curl -s -X POST "${KEYCLOAK_URL}/admin/realms" \
      -H "Authorization: Bearer ${ADMIN_TOKEN}" \
      -H "Content-Type: application/json" \
      -d '{
        "realm": "ansible-realm",
        "enabled": true,
        "displayName": "Ansible Realm",
        "registrationAllowed": false,
        "loginWithEmailAllowed": true,
        "duplicateEmailsAllowed": false,
        "resetPasswordAllowed": true,
        "editUsernameAllowed": false,
        "bruteForceProtected": true
      }'

    if [ $? -eq 0 ]; then
        echo "✅ ansible-realm 생성 완료"
    else
        echo "❌ ansible-realm 생성 실패"
        exit 1
    fi
else
    echo "✅ ansible-realm이 이미 존재합니다"
fi

# Check for AWX client in ansible-realm
echo ""
echo "3. ansible-realm에 AWX 클라이언트 확인 중..."

CLIENTS=$(curl -s -X GET "${KEYCLOAK_URL}/admin/realms/ansible-realm/clients" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}")

EXISTING_CLIENT=$(echo "$CLIENTS" | jq -r '.[] | select(.clientId == "awx-oidc") | .id')

if [ ! -z "$EXISTING_CLIENT" ] && [ "$EXISTING_CLIENT" != "null" ]; then
    echo "⚠️  AWX OIDC 클라이언트가 이미 존재합니다 (ID: ${EXISTING_CLIENT}). 삭제 후 재생성..."
    curl -s -X DELETE "${KEYCLOAK_URL}/admin/realms/ansible-realm/clients/${EXISTING_CLIENT}" \
      -H "Authorization: Bearer ${ADMIN_TOKEN}"
    echo "✅ 기존 클라이언트 삭제 완료"
fi

# Generate client secret
CLIENT_SECRET=$(openssl rand -hex 32)

# Create AWX OIDC client in ansible-realm
echo ""
echo "4. ansible-realm에 AWX OIDC 클라이언트 생성 중..."

curl -s -X POST "${KEYCLOAK_URL}/admin/realms/ansible-realm/clients" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "clientId": "awx-oidc",
    "name": "AWX OIDC Client",
    "description": "AWX authentication via Keycloak OIDC (ansible-realm)",
    "enabled": true,
    "clientAuthenticatorType": "client-secret",
    "secret": "'${CLIENT_SECRET}'",
    "redirectUris": [
      "http://192.168.64.26:30000/sso/complete/oidc/",
      "http://192.168.64.26:30000/*",
      "http://192.168.64.26/sso/complete/oidc/",
      "http://192.168.64.26/*"
    ],
    "webOrigins": [
      "http://192.168.64.26:30000",
      "http://192.168.64.26",
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
  }'

if [ $? -eq 0 ]; then
    echo "✅ AWX OIDC 클라이언트 생성 완료"
    echo "   Client ID: awx-oidc"
    echo "   Client Secret: ${CLIENT_SECRET}"

    # Save client secret
    echo "${CLIENT_SECRET}" > /root/awx-ansible-realm-client-secret.txt
    chmod 600 /root/awx-ansible-realm-client-secret.txt
    echo "   Secret 저장 위치: /root/awx-ansible-realm-client-secret.txt"
else
    echo "❌ 클라이언트 생성 실패"
    exit 1
fi

# Create a test user in ansible-realm if doesn't exist
echo ""
echo "5. ansible-realm에 테스트 사용자 확인/생성 중..."

USERS=$(curl -s -X GET "${KEYCLOAK_URL}/admin/realms/ansible-realm/users?username=admin" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}")

EXISTING_USER=$(echo "$USERS" | jq -r '.[0].id // empty')

if [ -z "$EXISTING_USER" ]; then
    echo "   admin 사용자 생성 중..."

    # Create admin user
    USER_CREATE=$(curl -s -w "%{http_code}" -X POST "${KEYCLOAK_URL}/admin/realms/ansible-realm/users" \
      -H "Authorization: Bearer ${ADMIN_TOKEN}" \
      -H "Content-Type: application/json" \
      -d '{
        "username": "admin",
        "enabled": true,
        "emailVerified": true,
        "firstName": "Admin",
        "lastName": "User",
        "email": "admin@example.com",
        "credentials": [{
          "type": "password",
          "value": "admin123",
          "temporary": false
        }]
      }')

    HTTP_CODE="${USER_CREATE: -3}"
    if [ "$HTTP_CODE" == "201" ]; then
        echo "   ✅ admin 사용자 생성 완료 (admin/admin123)"
    else
        echo "   ⚠️  사용자 생성 실패 (HTTP $HTTP_CODE)"
    fi
else
    echo "   ✅ admin 사용자가 이미 존재합니다"
fi

echo ""
echo "=========================================="
echo "✅ ansible-realm 설정 완료!"
echo "=========================================="
echo ""
echo "OIDC 설정 정보:"
echo "  - Realm: ansible-realm"
echo "  - Client ID: awx-oidc"
echo "  - Client Secret: ${CLIENT_SECRET}"
echo "  - OIDC Endpoint: ${KEYCLOAK_URL}/realms/ansible-realm"
echo "  - Test User: admin / admin123"
echo ""
echo "다음 단계: AWX OIDC 설정 업데이트"
echo "  ./apply-awx-ansible-realm-settings.sh"
echo ""
