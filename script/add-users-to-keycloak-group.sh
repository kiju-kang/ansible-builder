#!/bin/bash

echo "=========================================="
echo "Keycloak 사용자를 developer 그룹에 추가"
echo "=========================================="
echo ""

KEYCLOAK_URL="http://192.168.64.26:30002"

# Get admin token
echo "1. Keycloak 관리자 토큰 획득 중..."
TOKEN=$(curl -s -X POST "${KEYCLOAK_URL}/realms/master/protocol/openid-connect/token" \
  -d "client_id=admin-cli" \
  -d "username=admin" \
  -d "password=admin123" \
  -d "grant_type=password" | jq -r '.access_token')

if [ -z "$TOKEN" ] || [ "$TOKEN" == "null" ]; then
    echo "❌ 토큰 획득 실패"
    exit 1
fi
echo "✅ 토큰 획득 완료"

# Get developer group ID
echo ""
echo "2. developer 그룹 ID 조회 중..."
GROUP_ID=$(curl -s -X GET "${KEYCLOAK_URL}/admin/realms/ansible-realm/groups" \
  -H "Authorization: Bearer ${TOKEN}" | jq -r '.[] | select(.name == "developer") | .id')

if [ -z "$GROUP_ID" ] || [ "$GROUP_ID" == "null" ]; then
    echo "❌ developer 그룹을 찾을 수 없습니다"
    exit 1
fi
echo "✅ developer 그룹 ID: ${GROUP_ID}"

# Get all users
echo ""
echo "3. ansible-realm 사용자 조회 중..."
USERS=$(curl -s -X GET "${KEYCLOAK_URL}/admin/realms/ansible-realm/users" \
  -H "Authorization: Bearer ${TOKEN}")

echo ""
echo "4. 사용자를 developer 그룹에 추가 중..."

echo "$USERS" | jq -r '.[] | .id + " " + .username' | while read USER_ID USERNAME; do
    echo "  - ${USERNAME} 추가 중..."

    # Add user to developer group
    RESPONSE=$(curl -s -w "%{http_code}" -o /dev/null -X PUT \
      "${KEYCLOAK_URL}/admin/realms/ansible-realm/users/${USER_ID}/groups/${GROUP_ID}" \
      -H "Authorization: Bearer ${TOKEN}")

    if [ "$RESPONSE" == "204" ] || [ "$RESPONSE" == "200" ]; then
        echo "    ✅ ${USERNAME} → developer 그룹 추가 완료"
    else
        echo "    ⚠️  ${USERNAME} 추가 실패 (HTTP ${RESPONSE})"
    fi
done

echo ""
echo "5. developer 그룹 멤버 확인..."
MEMBERS=$(curl -s -X GET "${KEYCLOAK_URL}/admin/realms/ansible-realm/groups/${GROUP_ID}/members" \
  -H "Authorization: Bearer ${TOKEN}")

echo "developer 그룹 멤버:"
echo "$MEMBERS" | jq -r '.[] | "  - " + .username + " (" + .email + ")"'

echo ""
echo "=========================================="
echo "✅ 작업 완료!"
echo "=========================================="
echo ""
echo "이제 OIDC로 AWX에 로그인하면:"
echo "  - Default 조직의 관리자로 자동 추가됩니다"
echo "  - developer 팀에 자동 추가됩니다"
echo "  - ansible-builder에서 생성한 리소스를 볼 수 있습니다"
echo ""
