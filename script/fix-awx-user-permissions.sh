#!/bin/bash

echo "=========================================="
echo "AWX OIDC 사용자 권한 수정"
echo "=========================================="
echo ""

AWX_URL="http://192.168.64.26:30000"
AWX_TOKEN="A6tZWbC5pFXUynXvhogzzC0BDWulOj"

echo "1. OIDC 사용자 목록 조회 중..."
OIDC_USERS=$(curl -s -H "Authorization: Bearer ${AWX_TOKEN}" \
  "${AWX_URL}/api/v2/users/" | jq -r '.results[] | select(.auth != null and .auth != [] and (.auth[] | .provider == "oidc")) | "\(.id) \(.username)"')

if [ -z "$OIDC_USERS" ]; then
    echo "⚠️  OIDC 사용자가 없습니다"
    echo "   AWX에 OIDC로 로그인하여 사용자를 생성하세요"
    exit 0
fi

echo "OIDC 사용자:"
echo "$OIDC_USERS" | while read USER_ID USERNAME; do
    echo "  - ${USERNAME} (ID: ${USER_ID})"
done

echo ""
echo "2. Default 조직에 관리자로 추가 중..."

echo "$OIDC_USERS" | while read USER_ID USERNAME; do
    echo "  - ${USERNAME} 추가 중..."

    # Remove user first (in case they're already a member)
    curl -s -X POST "${AWX_URL}/api/v2/organizations/1/users/" \
      -H "Authorization: Bearer ${AWX_TOKEN}" \
      -H "Content-Type: application/json" \
      -d "{\"id\": ${USER_ID}, \"disassociate\": true}" > /dev/null 2>&1

    # Add user as admin
    RESULT=$(curl -s -X POST "${AWX_URL}/api/v2/organizations/1/users/" \
      -H "Authorization: Bearer ${AWX_TOKEN}" \
      -H "Content-Type: application/json" \
      -d "{\"id\": ${USER_ID}}")

    # Make user an admin of the organization
    curl -s -X POST "${AWX_URL}/api/v2/organizations/1/admins/" \
      -H "Authorization: Bearer ${AWX_TOKEN}" \
      -H "Content-Type: application/json" \
      -d "{\"id\": ${USER_ID}}" > /dev/null

    echo "    ✅ ${USERNAME} → Default 조직 관리자"
done

echo ""
echo "3. developer 팀에 추가 중..."

echo "$OIDC_USERS" | while read USER_ID USERNAME; do
    echo "  - ${USERNAME} 추가 중..."

    RESULT=$(curl -s -X POST "${AWX_URL}/api/v2/teams/1/users/" \
      -H "Authorization: Bearer ${AWX_TOKEN}" \
      -H "Content-Type: application/json" \
      -d "{\"id\": ${USER_ID}}")

    echo "    ✅ ${USERNAME} → developer 팀"
done

echo ""
echo "4. 권한 확인..."

ORG_INFO=$(curl -s -H "Authorization: Bearer ${AWX_TOKEN}" \
  "${AWX_URL}/api/v2/organizations/1/" | jq -r '. | "조직: " + .name + "\n  관리자: " + (.summary_fields.related_field_counts.admins | tostring) + "명\n  사용자: " + (.summary_fields.related_field_counts.users | tostring) + "명"')

TEAM_INFO=$(curl -s -H "Authorization: Bearer ${AWX_TOKEN}" \
  "${AWX_URL}/api/v2/teams/1/" | jq -r '. | "팀: " + .name + "\n  멤버: " + (.summary_fields.member_count | tostring) + "명"')

echo "$ORG_INFO"
echo ""
echo "$TEAM_INFO"

echo ""
echo "=========================================="
echo "✅ 권한 수정 완료!"
echo "=========================================="
echo ""
echo "이제 AWX UI에서:"
echo "  - 팀 목록에 'developer' 팀이 표시됩니다"
echo "  - ansible-builder에서 생성한 리소스를 볼 수 있습니다"
echo ""
echo "참고: AWX UI를 새로고침(F5)하세요"
echo ""
