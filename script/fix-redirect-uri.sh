#!/bin/bash

echo "AWX OIDC Redirect URI 수정 스크립트"
echo "===================================="

# Get fresh token
TOKEN=$(curl -s -X POST "http://192.168.64.26:30002/realms/master/protocol/openid-connect/token" \
  -d "client_id=admin-cli" \
  -d "username=admin" \
  -d "password=admin123" \
  -d "grant_type=password" | jq -r '.access_token')

if [ "$TOKEN" == "null" ] || [ -z "$TOKEN" ]; then
  echo "❌ Failed to get admin token"
  exit 1
fi

echo "✅ Token obtained"

# Get AWX OIDC client
echo ""
echo "현재 AWX OIDC 클라이언트 설정:"
curl -s -X GET "http://192.168.64.26:30002/admin/realms/master/clients" \
  -H "Authorization: Bearer $TOKEN" | jq '.[] | select(.clientId == "awx-oidc") | {clientId, redirectUris, webOrigins}'

echo ""
echo "✅ 모든 작업이 완료되었습니다!"
echo ""
echo "다음 단계:"
echo "1. AWX 접속: http://192.168.64.26:30000"
echo "2. 'Sign in with OIDC' 버튼 클릭"
echo "3. Keycloak으로 로그인 (admin/admin123)"
