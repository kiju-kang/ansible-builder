#!/bin/bash

echo "=========================================="
echo "AWX OIDC 설정 적용"
echo "=========================================="
echo ""

# 설정 변수
AWX_URL="http://192.168.64.26:30000"
AWX_ADMIN="admin"
AWX_PASSWORD="password"
KEYCLOAK_URL="http://192.168.64.26:30002"
KEYCLOAK_REALM="master"
CLIENT_SECRET=$(cat /root/awx-oidc-client-secret.txt)
COOKIE_FILE="/tmp/awx-cookies.txt"

echo "1. AWX API 연결 확인..."
AWX_VERSION=$(curl -s "${AWX_URL}/api/v2/ping/" | jq -r '.version')
if [ -z "$AWX_VERSION" ] || [ "$AWX_VERSION" == "null" ]; then
    echo "❌ AWX API 연결 실패"
    exit 1
fi
echo "✅ AWX API 연결 성공 (버전: ${AWX_VERSION})"

echo ""
echo "2. AWX OIDC 설정 적용 (kubectl 사용)..."

# kubectl exec로 AWX pod에서 직접 설정
AWX_WEB_POD=$(kubectl get pods -n awx -l app.kubernetes.io/component=awx-web -o jsonpath='{.items[0].metadata.name}')

if [ -z "$AWX_WEB_POD" ]; then
    echo "❌ AWX web pod를 찾을 수 없습니다"
    exit 1
fi

echo "  AWX Web Pod: ${AWX_WEB_POD}"

# AWX 설정 적용
echo ""
echo "3. awx-manage를 사용하여 OIDC 설정 적용..."

kubectl exec -it ${AWX_WEB_POD} -n awx -- bash -c "awx-manage shell << 'PYTHON_EOF'
from django.conf import settings
from awx.conf.models import Setting

# OIDC Key
Setting.objects.update_or_create(
    key='SOCIAL_AUTH_OIDC_KEY',
    defaults={'value': 'awx-oidc'}
)
print('✅ SOCIAL_AUTH_OIDC_KEY 설정 완료')

# OIDC Secret
Setting.objects.update_or_create(
    key='SOCIAL_AUTH_OIDC_SECRET',
    defaults={'value': '${CLIENT_SECRET}'}
)
print('✅ SOCIAL_AUTH_OIDC_SECRET 설정 완료')

# OIDC Endpoint
Setting.objects.update_or_create(
    key='SOCIAL_AUTH_OIDC_OIDC_ENDPOINT',
    defaults={'value': '${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}'}
)
print('✅ SOCIAL_AUTH_OIDC_OIDC_ENDPOINT 설정 완료')

# OIDC Verify SSL
Setting.objects.update_or_create(
    key='SOCIAL_AUTH_OIDC_VERIFY_SSL',
    defaults={'value': False}
)
print('✅ SOCIAL_AUTH_OIDC_VERIFY_SSL 설정 완료')

# Organization Map
Setting.objects.update_or_create(
    key='SOCIAL_AUTH_OIDC_ORGANIZATION_MAP',
    defaults={'value': {'Default': {'users': True}}}
)
print('✅ SOCIAL_AUTH_OIDC_ORGANIZATION_MAP 설정 완료')

# Team Map
Setting.objects.update_or_create(
    key='SOCIAL_AUTH_OIDC_TEAM_MAP',
    defaults={'value': {}}
)
print('✅ SOCIAL_AUTH_OIDC_TEAM_MAP 설정 완료')

# 설정 확인
print('\n현재 OIDC 설정:')
print(f'  Key: {Setting.objects.get(key=\"SOCIAL_AUTH_OIDC_KEY\").value}')
print(f'  Endpoint: {Setting.objects.get(key=\"SOCIAL_AUTH_OIDC_OIDC_ENDPOINT\").value}')
print(f'  Verify SSL: {Setting.objects.get(key=\"SOCIAL_AUTH_OIDC_VERIFY_SSL\").value}')
PYTHON_EOF
"

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✅ AWX OIDC 설정 완료!"
    echo "=========================================="
    echo ""
    echo "설정 내용:"
    echo "  - AWX URL: ${AWX_URL}"
    echo "  - OIDC Client: awx-oidc"
    echo "  - OIDC Endpoint: ${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}"
    echo "  - 조직: Default (자동 사용자 추가)"
    echo ""
    echo "다음 단계:"
    echo "  1. AWX Web Pod 재시작 (설정 적용):"
    echo "     kubectl rollout restart deployment/awx-web -n awx"
    echo ""
    echo "  2. AWX 접속: ${AWX_URL}"
    echo "  3. 'Sign in with OIDC' 버튼 클릭"
    echo "  4. Keycloak으로 로그인 (admin/admin123)"
    echo ""
else
    echo "❌ AWX OIDC 설정 실패"
    exit 1
fi
