#!/bin/bash

# AWX Keycloak OIDC 설정 스크립트
# AWX Settings API를 통해 Keycloak SSO 설정

set -e

AWX_URL="http://192.168.64.26:30000"
AWX_USERNAME="admin"
AWX_PASSWORD="UDXVGspozrOjvhgQvZgzDVmvKcxZz3Dn"

KEYCLOAK_URL="http://192.168.64.26:8080"
KEYCLOAK_REALM="ansible-realm"
KEYCLOAK_CLIENT_ID="awx-client"
KEYCLOAK_CLIENT_SECRET="awx-secret-key"

echo "=========================================="
echo "AWX Keycloak OIDC 설정"
echo "=========================================="

# 1. AWX 로그인 (토큰 획득)
echo ""
echo "[1/4] AWX 로그인 중..."
AUTH_TOKEN=$(curl -s -X POST "$AWX_URL/api/v2/tokens/" \
  -u "$AWX_USERNAME:$AWX_PASSWORD" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Keycloak OIDC Configuration Token",
    "application": null,
    "scope": "write"
  }' | jq -r '.token')

if [ -z "$AUTH_TOKEN" ] || [ "$AUTH_TOKEN" == "null" ]; then
    echo "✗ AWX 로그인 실패"
    echo "  Username: $AWX_USERNAME를 확인하세요"
    exit 1
fi
echo "✓ AWX 로그인 성공 (Token: ${AUTH_TOKEN:0:20}...)"

# 2. 현재 Settings 확인
echo ""
echo "[2/4] 현재 OIDC 설정 확인 중..."
CURRENT_SETTINGS=$(curl -s -X GET "$AWX_URL/api/v2/settings/oidc/" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json")

echo "현재 설정:"
echo "$CURRENT_SETTINGS" | jq '.'

# 3. OIDC 설정 적용
echo ""
echo "[3/4] Keycloak OIDC 설정 적용 중..."

OIDC_CONFIG=$(cat <<EOF
{
  "SOCIAL_AUTH_OIDC_KEY": "$KEYCLOAK_CLIENT_ID",
  "SOCIAL_AUTH_OIDC_SECRET": "$KEYCLOAK_CLIENT_SECRET",
  "SOCIAL_AUTH_OIDC_OIDC_ENDPOINT": "$KEYCLOAK_URL/realms/$KEYCLOAK_REALM",
  "SOCIAL_AUTH_OIDC_VERIFY_SSL": false
}
EOF
)

UPDATE_RESPONSE=$(curl -s -w "\n%{http_code}" -X PATCH "$AWX_URL/api/v2/settings/oidc/" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$OIDC_CONFIG")

HTTP_CODE=$(echo "$UPDATE_RESPONSE" | tail -n 1)
RESPONSE_BODY=$(echo "$UPDATE_RESPONSE" | head -n -1)

if [ "$HTTP_CODE" == "200" ]; then
    echo "✓ OIDC 설정 업데이트 성공"
    echo "$RESPONSE_BODY" | jq '.'
else
    echo "✗ OIDC 설정 업데이트 실패 (HTTP $HTTP_CODE)"
    echo "$RESPONSE_BODY"
    exit 1
fi

# 4. System 설정 - OIDC 사용자 자동 생성 활성화
echo ""
echo "[4/4] OIDC 사용자 자동 생성 설정 중..."

SYSTEM_CONFIG=$(cat <<EOF
{
  "SOCIAL_AUTH_CREATE_USERS": true,
  "SOCIAL_AUTH_REMOVE_DISABLED_USERS": false
}
EOF
)

SYSTEM_RESPONSE=$(curl -s -w "\n%{http_code}" -X PATCH "$AWX_URL/api/v2/settings/system/" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$SYSTEM_CONFIG")

HTTP_CODE=$(echo "$SYSTEM_RESPONSE" | tail -n 1)
RESPONSE_BODY=$(echo "$SYSTEM_RESPONSE" | head -n -1)

if [ "$HTTP_CODE" == "200" ]; then
    echo "✓ System 설정 업데이트 성공"
else
    echo "⚠ System 설정 업데이트 실패 (HTTP $HTTP_CODE) - 수동 설정 필요"
    echo "$RESPONSE_BODY"
fi

# 결과 출력
echo ""
echo "=========================================="
echo "AWX Keycloak OIDC 설정 완료!"
echo "=========================================="
echo ""
echo "설정 정보:"
echo "  AWX URL: $AWX_URL"
echo "  Keycloak URL: $KEYCLOAK_URL"
echo "  Realm: $KEYCLOAK_REALM"
echo "  Client ID: $KEYCLOAK_CLIENT_ID"
echo ""
echo "=========================================="
echo "SSO 로그인 테스트:"
echo "=========================================="
echo ""
echo "1. 브라우저에서 Ansible Builder 접속:"
echo "   http://192.168.64.26:8000"
echo ""
echo "2. Keycloak SSO로 로그인"
echo "   - Admin: admin / admin123"
echo "   - User: testuser / test123"
echo ""
echo "3. 새 탭에서 AWX 접속:"
echo "   $AWX_URL"
echo ""
echo "4. AWX 로그인 페이지에서 'Sign in with OIDC' 버튼 클릭"
echo ""
echo "5. 자동으로 로그인됩니다! (재인증 불필요)"
echo ""
echo "=========================================="
echo "참고사항:"
echo "=========================================="
echo ""
echo "- AWX에서 처음 SSO 로그인 시 사용자가 자동 생성됩니다"
echo "- Keycloak의 'admin' role을 가진 사용자는 AWX에서도 admin 권한을 갖습니다"
echo "- 로그아웃은 Keycloak에서 해야 완전히 로그아웃됩니다"
echo ""
