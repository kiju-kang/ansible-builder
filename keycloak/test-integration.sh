#!/bin/bash

# Keycloak 통합 테스트 스크립트
# AWX + Ansible Builder + Keycloak SSO 통합 테스트

set -e

echo "========================================"
echo "  Keycloak 통합 테스트"
echo "========================================"
echo ""

# 설정
KEYCLOAK_URL="http://localhost:8080"
REALM="ansible-realm"
CLIENT_ID="ansible-builder-client"
USERNAME="admin"
PASSWORD="admin123"
BACKEND_URL="http://localhost:8000"

# 색상 코드
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 테스트 결과 카운터
PASSED=0
FAILED=0

# 테스트 함수
test_step() {
    echo -e "${YELLOW}TEST:${NC} $1"
}

test_pass() {
    echo -e "${GREEN}✓ PASS${NC}: $1"
    ((PASSED++))
}

test_fail() {
    echo -e "${RED}✗ FAIL${NC}: $1"
    ((FAILED++))
}

# 1. Keycloak 서버 접속 확인
test_step "Keycloak 서버 접속 확인"
if curl -sf "$KEYCLOAK_URL/health/ready" > /dev/null 2>&1; then
    test_pass "Keycloak 서버가 정상 작동 중입니다."
else
    test_fail "Keycloak 서버에 접속할 수 없습니다."
    exit 1
fi

# 2. OpenID Configuration 확인
test_step "OpenID Configuration 확인"
OIDC_CONFIG=$(curl -s "$KEYCLOAK_URL/realms/$REALM/.well-known/openid-configuration")
if echo "$OIDC_CONFIG" | jq -e '.token_endpoint' > /dev/null 2>&1; then
    test_pass "OpenID Configuration이 정상입니다."
    TOKEN_ENDPOINT=$(echo "$OIDC_CONFIG" | jq -r '.token_endpoint')
    echo "  Token Endpoint: $TOKEN_ENDPOINT"
else
    test_fail "OpenID Configuration을 가져올 수 없습니다."
fi

# 3. Keycloak 토큰 발급 테스트
test_step "Keycloak 토큰 발급 테스트"
TOKEN_RESPONSE=$(curl -s -X POST "$KEYCLOAK_URL/realms/$REALM/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id=$CLIENT_ID" \
  -d "username=$USERNAME" \
  -d "password=$PASSWORD")

ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.access_token')
if [ "$ACCESS_TOKEN" != "null" ] && [ -n "$ACCESS_TOKEN" ]; then
    test_pass "Keycloak 토큰 발급 성공"
    echo "  Access Token: ${ACCESS_TOKEN:0:50}..."
else
    test_fail "Keycloak 토큰 발급 실패"
    echo "  Response: $TOKEN_RESPONSE"
    exit 1
fi

# 4. JWT 토큰 디코딩 (페이로드 확인)
test_step "JWT 토큰 페이로드 확인"
PAYLOAD=$(echo "$ACCESS_TOKEN" | cut -d. -f2 | base64 -d 2>/dev/null || echo "{}")
if echo "$PAYLOAD" | jq -e '.preferred_username' > /dev/null 2>&1; then
    test_pass "JWT 토큰 페이로드가 유효합니다."
    echo "  Username: $(echo $PAYLOAD | jq -r '.preferred_username')"
    echo "  Email: $(echo $PAYLOAD | jq -r '.email')"
    echo "  Roles: $(echo $PAYLOAD | jq -r '.realm_access.roles')"
else
    test_fail "JWT 토큰 페이로드 디코딩 실패"
fi

# 5. Ansible Builder 백엔드 접속 확인
test_step "Ansible Builder 백엔드 접속 확인"
if curl -sf "$BACKEND_URL/docs" > /dev/null 2>&1; then
    test_pass "Ansible Builder 백엔드가 정상 작동 중입니다."
else
    test_fail "Ansible Builder 백엔드에 접속할 수 없습니다."
    echo "  백엔드가 실행 중인지 확인하세요: cd /root/ansible-builder/ansible-builder/backend && python3 main.py"
fi

# 6. Keycloak Config 엔드포인트 확인
test_step "Keycloak Config 엔드포인트 확인"
CONFIG_RESPONSE=$(curl -s "$BACKEND_URL/api/auth/keycloak-config")
if echo "$CONFIG_RESPONSE" | jq -e '.realm' > /dev/null 2>&1; then
    test_pass "Keycloak Config 엔드포인트가 정상입니다."
    echo "  Realm: $(echo $CONFIG_RESPONSE | jq -r '.realm')"
    echo "  Client ID: $(echo $CONFIG_RESPONSE | jq -r '.client_id')"
else
    test_fail "Keycloak Config 엔드포인트 응답 실패"
    echo "  Response: $CONFIG_RESPONSE"
fi

# 7. Keycloak 토큰으로 /api/auth/me 호출
test_step "Keycloak 토큰으로 사용자 정보 조회"
ME_RESPONSE=$(curl -s "$BACKEND_URL/api/auth/me" \
  -H "Authorization: Bearer $ACCESS_TOKEN")
if echo "$ME_RESPONSE" | jq -e '.username' > /dev/null 2>&1; then
    test_pass "Keycloak 토큰으로 사용자 정보 조회 성공"
    echo "  Username: $(echo $ME_RESPONSE | jq -r '.username')"
    echo "  Role: $(echo $ME_RESPONSE | jq -r '.role')"
else
    test_fail "Keycloak 토큰으로 사용자 정보 조회 실패"
    echo "  Response: $ME_RESPONSE"
fi

# 8. Keycloak 토큰으로 Playbooks 조회
test_step "Keycloak 토큰으로 Playbooks 조회"
PLAYBOOKS_RESPONSE=$(curl -s "$BACKEND_URL/api/playbooks" \
  -H "Authorization: Bearer $ACCESS_TOKEN")
if echo "$PLAYBOOKS_RESPONSE" | jq -e '. | type == "array"' > /dev/null 2>&1; then
    test_pass "Keycloak 토큰으로 Playbooks 조회 성공"
    PLAYBOOK_COUNT=$(echo "$PLAYBOOKS_RESPONSE" | jq '. | length')
    echo "  Playbook 개수: $PLAYBOOK_COUNT"
else
    test_fail "Keycloak 토큰으로 Playbooks 조회 실패"
    echo "  Response: $PLAYBOOKS_RESPONSE"
fi

# 9. JWKS 엔드포인트 확인
test_step "JWKS 엔드포인트 확인"
JWKS_RESPONSE=$(curl -s "$KEYCLOAK_URL/realms/$REALM/protocol/openid-connect/certs")
if echo "$JWKS_RESPONSE" | jq -e '.keys[0]' > /dev/null 2>&1; then
    test_pass "JWKS 엔드포인트가 정상입니다."
    KEY_COUNT=$(echo "$JWKS_RESPONSE" | jq '.keys | length')
    echo "  공개키 개수: $KEY_COUNT"
else
    test_fail "JWKS 엔드포인트 응답 실패"
fi

# 10. UserInfo 엔드포인트 확인
test_step "UserInfo 엔드포인트 확인"
USERINFO_RESPONSE=$(curl -s "$KEYCLOAK_URL/realms/$REALM/protocol/openid-connect/userinfo" \
  -H "Authorization: Bearer $ACCESS_TOKEN")
if echo "$USERINFO_RESPONSE" | jq -e '.preferred_username' > /dev/null 2>&1; then
    test_pass "UserInfo 엔드포인트가 정상입니다."
    echo "  Username: $(echo $USERINFO_RESPONSE | jq -r '.preferred_username')"
else
    test_fail "UserInfo 엔드포인트 응답 실패"
fi

# 테스트 결과 요약
echo ""
echo "========================================"
echo "  테스트 결과"
echo "========================================"
echo -e "${GREEN}통과:${NC} $PASSED"
echo -e "${RED}실패:${NC} $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ 모든 테스트를 통과했습니다!${NC}"
    echo ""
    echo "다음 단계:"
    echo "  1. 웹 브라우저에서 http://localhost:8000 접속"
    echo "  2. 'Sign in with Keycloak SSO' 버튼 클릭"
    echo "  3. Username: admin, Password: admin123 입력"
    echo "  4. Ansible Builder로 자동 로그인 확인"
    exit 0
else
    echo -e "${RED}✗ 일부 테스트가 실패했습니다.${NC}"
    echo ""
    echo "문제 해결:"
    echo "  1. Keycloak이 실행 중인지 확인: docker ps | grep keycloak"
    echo "  2. Ansible Builder 백엔드가 실행 중인지 확인"
    echo "  3. 설정 파일 확인: /root/ansible-builder/ansible-builder/backend/.env"
    exit 1
fi
