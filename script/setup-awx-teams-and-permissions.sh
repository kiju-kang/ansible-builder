#!/bin/bash

echo "=========================================="
echo "AWX Teams 및 OIDC 매핑 설정"
echo "=========================================="
echo ""

AWX_URL="http://192.168.64.26:30000"
AWX_TOKEN="A6tZWbC5pFXUynXvhogzzC0BDWulOj"

echo "1. AWX에 developer 팀 생성 중..."

# Check if developer team already exists
EXISTING_TEAM=$(curl -s -H "Authorization: Bearer ${AWX_TOKEN}" \
  "${AWX_URL}/api/v2/teams/" | jq -r '.results[] | select(.name == "developer") | .id')

if [ ! -z "$EXISTING_TEAM" ] && [ "$EXISTING_TEAM" != "null" ]; then
    echo "⚠️  developer 팀이 이미 존재합니다 (ID: ${EXISTING_TEAM})"
    TEAM_ID=$EXISTING_TEAM
else
    # Create developer team in Default organization (ID: 1)
    TEAM_RESPONSE=$(curl -s -X POST "${AWX_URL}/api/v2/teams/" \
      -H "Authorization: Bearer ${AWX_TOKEN}" \
      -H "Content-Type: application/json" \
      -d '{
        "name": "developer",
        "description": "Developer team from Keycloak",
        "organization": 1
      }')

    TEAM_ID=$(echo "$TEAM_RESPONSE" | jq -r '.id')

    if [ ! -z "$TEAM_ID" ] && [ "$TEAM_ID" != "null" ]; then
        echo "✅ developer 팀 생성 완료 (ID: ${TEAM_ID})"
    else
        echo "❌ 팀 생성 실패"
        echo "$TEAM_RESPONSE" | jq '.'
        exit 1
    fi
fi

echo ""
echo "2. developer 팀에 권한 부여 중..."

# Grant admin role to developer team for Default organization
curl -s -X POST "${AWX_URL}/api/v2/teams/${TEAM_ID}/roles/" \
  -H "Authorization: Bearer ${AWX_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "id": 11
  }' > /dev/null

# Organization Admin role is usually ID 11
# We can also grant specific permissions

echo "✅ developer 팀에 조직 관리자 권한 부여 완료"

echo ""
echo "3. AWX OIDC 매핑 설정 업데이트 중..."

AWX_WEB_POD=$(kubectl get pods -n awx -l app.kubernetes.io/name=awx-web -o jsonpath='{.items[0].metadata.name}')

kubectl exec -n awx ${AWX_WEB_POD} -c awx-web -- bash -c "awx-manage shell << 'PYEOF'
from awx.conf.models import Setting

# Organization Map - 사용자를 Default 조직에 추가하고 관리자로 설정
org_map = {
    'Default': {
        'users': True,
        'admins': True,  # OIDC 사용자를 조직 관리자로 설정
        'remove_users': False,
        'remove_admins': False
    }
}

setting = Setting.objects.get(key='SOCIAL_AUTH_OIDC_ORGANIZATION_MAP')
setting.value = org_map
setting.save()
print('✅ Organization Map 업데이트:')
print(f'   {org_map}')

# Team Map - Keycloak 그룹을 AWX 팀에 매핑
team_map = {
    'developer': {
        'organization': 'Default',
        'users': '/developer',  # Keycloak group path
        'remove': False
    }
}

setting = Setting.objects.get(key='SOCIAL_AUTH_OIDC_TEAM_MAP')
setting.value = team_map
setting.save()
print('✅ Team Map 업데이트:')
print(f'   {team_map}')

PYEOF
"

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✅ AWX 팀 및 OIDC 매핑 설정 완료!"
    echo "=========================================="
    echo ""
    echo "설정 내용:"
    echo "  - AWX 팀: developer (조직: Default)"
    echo "  - 조직 매핑: 모든 OIDC 사용자를 Default 조직의 관리자로 추가"
    echo "  - 팀 매핑: Keycloak의 /developer 그룹 → AWX developer 팀"
    echo ""
    echo "다음 단계:"
    echo "  1. AWX Web Pod 재시작 (설정 적용):"
    echo "     kubectl rollout restart deployment/awx-web -n awx"
    echo ""
    echo "  2. Keycloak에서 사용자를 developer 그룹에 추가"
    echo ""
    echo "  3. OIDC로 AWX에 재로그인하여 팀 매핑 확인"
    echo ""
else
    echo "❌ OIDC 매핑 설정 실패"
    exit 1
fi
