#!/bin/bash

# AWX Keycloak Client 자동 생성 스크립트
# SSO 통합을 위한 AWX Client 설정

set -e

KEYCLOAK_URL="http://192.168.64.26:8080"
REALM="ansible-realm"
ADMIN_USER="admin"
ADMIN_PASSWORD="admin"
AWX_CLIENT_ID="awx-client"
AWX_URL="${AWX_URL:-http://192.168.64.26:8081}"  # AWX URL (기본값)

echo "=========================================="
echo "AWX Keycloak Client 생성 시작"
echo "=========================================="

# 1. Admin 토큰 획득
echo ""
echo "[1/5] Keycloak Admin 토큰 획득 중..."
TOKEN=$(curl -s -X POST "$KEYCLOAK_URL/realms/master/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$ADMIN_USER" \
  -d "password=$ADMIN_PASSWORD" \
  -d "grant_type=password" \
  -d "client_id=admin-cli" | jq -r '.access_token')

if [ -z "$TOKEN" ] || [ "$TOKEN" == "null" ]; then
    echo "✗ 토큰 획득 실패"
    exit 1
fi
echo "✓ 토큰 획득 성공"

# 2. AWX Client 존재 확인
echo ""
echo "[2/5] 기존 AWX Client 확인 중..."
EXISTING_CLIENT=$(curl -s -X GET "$KEYCLOAK_URL/admin/realms/$REALM/clients" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | jq -r ".[] | select(.clientId==\"$AWX_CLIENT_ID\") | .id")

if [ -n "$EXISTING_CLIENT" ] && [ "$EXISTING_CLIENT" != "null" ]; then
    echo "⚠ AWX Client가 이미 존재합니다 (ID: $EXISTING_CLIENT)"
    echo "  기존 Client를 삭제하고 다시 생성하시겠습니까? (y/N)"
    read -r RESPONSE
    if [[ "$RESPONSE" =~ ^[Yy]$ ]]; then
        curl -s -X DELETE "$KEYCLOAK_URL/admin/realms/$REALM/clients/$EXISTING_CLIENT" \
          -H "Authorization: Bearer $TOKEN"
        echo "✓ 기존 Client 삭제 완료"
    else
        echo "기존 Client 유지. 스크립트 종료."
        exit 0
    fi
fi

# 3. AWX Client 생성
echo ""
echo "[3/5] AWX Client 생성 중..."
CLIENT_CONFIG=$(cat <<EOF
{
  "clientId": "$AWX_CLIENT_ID",
  "name": "AWX Application",
  "description": "AWX Tower/Controller OIDC Client for SSO",
  "enabled": true,
  "protocol": "openid-connect",
  "publicClient": false,
  "bearerOnly": false,
  "standardFlowEnabled": true,
  "implicitFlowEnabled": false,
  "directAccessGrantsEnabled": true,
  "serviceAccountsEnabled": false,
  "redirectUris": [
    "$AWX_URL/sso/complete/oidc/*",
    "$AWX_URL/*"
  ],
  "webOrigins": [
    "$AWX_URL"
  ],
  "attributes": {
    "saml.assertion.signature": "false",
    "saml.force.post.binding": "false",
    "saml.multivalued.roles": "false",
    "saml.encrypt": "false",
    "saml.server.signature": "false",
    "saml.server.signature.keyinfo.ext": "false",
    "exclude.session.state.from.auth.response": "false",
    "saml_force_name_id_format": "false",
    "saml.client.signature": "false",
    "tls.client.certificate.bound.access.tokens": "false",
    "saml.authnstatement": "false",
    "display.on.consent.screen": "false",
    "saml.onetimeuse.condition": "false"
  }
}
EOF
)

CREATE_RESPONSE=$(curl -s -X POST "$KEYCLOAK_URL/admin/realms/$REALM/clients" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$CLIENT_CONFIG" -w "%{http_code}")

if [[ "$CREATE_RESPONSE" == "201" ]]; then
    echo "✓ AWX Client 생성 성공"
else
    echo "✗ AWX Client 생성 실패 (HTTP $CREATE_RESPONSE)"
    exit 1
fi

# 4. Client Secret 조회
echo ""
echo "[4/5] Client Secret 조회 중..."
sleep 1

# 새로 생성된 Client ID 조회
NEW_CLIENT_ID=$(curl -s -X GET "$KEYCLOAK_URL/admin/realms/$REALM/clients" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | jq -r ".[] | select(.clientId==\"$AWX_CLIENT_ID\") | .id")

if [ -z "$NEW_CLIENT_ID" ] || [ "$NEW_CLIENT_ID" == "null" ]; then
    echo "✗ Client ID 조회 실패"
    exit 1
fi

# Client Secret 조회
CLIENT_SECRET=$(curl -s -X GET "$KEYCLOAK_URL/admin/realms/$REALM/clients/$NEW_CLIENT_ID/client-secret" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | jq -r '.value')

echo "✓ Client Secret 조회 성공"

# 5. OIDC Mappers 생성
echo ""
echo "[5/5] OIDC Mappers 생성 중..."

# Username Mapper
curl -s -X POST "$KEYCLOAK_URL/admin/realms/$REALM/clients/$NEW_CLIENT_ID/protocol-mappers/models" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "username",
    "protocol": "openid-connect",
    "protocolMapper": "oidc-usermodel-property-mapper",
    "config": {
      "user.attribute": "username",
      "claim.name": "preferred_username",
      "jsonType.label": "String",
      "id.token.claim": "true",
      "access.token.claim": "true",
      "userinfo.token.claim": "true"
    }
  }' > /dev/null

# Email Mapper
curl -s -X POST "$KEYCLOAK_URL/admin/realms/$REALM/clients/$NEW_CLIENT_ID/protocol-mappers/models" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "email",
    "protocol": "openid-connect",
    "protocolMapper": "oidc-usermodel-property-mapper",
    "config": {
      "user.attribute": "email",
      "claim.name": "email",
      "jsonType.label": "String",
      "id.token.claim": "true",
      "access.token.claim": "true",
      "userinfo.token.claim": "true"
    }
  }' > /dev/null

# Groups Mapper
curl -s -X POST "$KEYCLOAK_URL/admin/realms/$REALM/clients/$NEW_CLIENT_ID/protocol-mappers/models" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "groups",
    "protocol": "openid-connect",
    "protocolMapper": "oidc-group-membership-mapper",
    "config": {
      "claim.name": "groups",
      "full.path": "false",
      "id.token.claim": "true",
      "access.token.claim": "true",
      "userinfo.token.claim": "true"
    }
  }' > /dev/null

echo "✓ Mappers 생성 완료 (username, email, groups)"

# 결과 출력
echo ""
echo "=========================================="
echo "AWX Keycloak Client 생성 완료!"
echo "=========================================="
echo ""
echo "다음 정보를 AWX 설정에 사용하세요:"
echo ""
echo "Client ID: $AWX_CLIENT_ID"
echo "Client Secret: $CLIENT_SECRET"
echo "OIDC Endpoint: $KEYCLOAK_URL/realms/$REALM"
echo ""
echo "=========================================="
echo "AWX 환경변수 설정 예시:"
echo "=========================================="
cat <<EOF

# AWX docker-compose.yml 또는 환경변수에 추가:
environment:
  SOCIAL_AUTH_OIDC_KEY: $AWX_CLIENT_ID
  SOCIAL_AUTH_OIDC_SECRET: $CLIENT_SECRET
  SOCIAL_AUTH_OIDC_OIDC_ENDPOINT: $KEYCLOAK_URL/realms/$REALM
  SOCIAL_AUTH_OIDC_VERIFY_SSL: "false"
  SOCIAL_AUTH_CREATE_USERS: "true"

EOF

echo ""
echo "또는 AWX UI에서 설정:"
echo "Settings → Authentication → Generic OIDC Settings"
echo ""
echo "=========================================="
echo "테스트 방법:"
echo "=========================================="
echo "1. Ansible Builder에서 Keycloak SSO 로그인"
echo "2. AWX 페이지로 이동 ($AWX_URL)"
echo "3. 자동 로그인 확인!"
echo "=========================================="

# 설정 파일 저장
cat > /root/keycloak/awx-oidc-config.env <<EOF
# AWX Keycloak OIDC 설정
# 생성일: $(date)

SOCIAL_AUTH_OIDC_KEY=$AWX_CLIENT_ID
SOCIAL_AUTH_OIDC_SECRET=$CLIENT_SECRET
SOCIAL_AUTH_OIDC_OIDC_ENDPOINT=$KEYCLOAK_URL/realms/$REALM
SOCIAL_AUTH_OIDC_VERIFY_SSL=false
SOCIAL_AUTH_CREATE_USERS=true
SOCIAL_AUTH_REMOVE_DISABLED_USERS=false
SOCIAL_AUTH_OIDC_USERNAME_KEY=preferred_username
EOF

echo ""
echo "설정 파일 저장: /root/keycloak/awx-oidc-config.env"
echo ""
