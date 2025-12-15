#!/bin/bash

echo "=========================================="
echo "AWX ansible-realm OIDC 설정 적용"
echo "=========================================="
echo ""

KEYCLOAK_URL="http://192.168.64.26:30002"
KEYCLOAK_REALM="ansible-realm"
CLIENT_SECRET=$(cat /root/awx-ansible-realm-client-secret.txt)

if [ -z "$CLIENT_SECRET" ]; then
    echo "❌ Client secret 파일을 찾을 수 없습니다"
    echo "   먼저 ./configure-awx-ansible-realm.sh를 실행하세요"
    exit 1
fi

echo "Client Secret: ${CLIENT_SECRET:0:20}..."
echo ""

# Get AWX web pod
AWX_WEB_POD=$(kubectl get pods -n awx -l app.kubernetes.io/name=awx-web -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

if [ -z "$AWX_WEB_POD" ]; then
    echo "❌ AWX web pod를 찾을 수 없습니다"
    exit 1
fi

echo "1. AWX Web Pod: ${AWX_WEB_POD}"
echo ""

echo "2. AWX OIDC 설정 업데이트 중..."

# Update AWX OIDC settings
kubectl exec -n awx ${AWX_WEB_POD} -c awx-web -- awx-manage shell << PYTHON_EOF
from awx.conf.models import Setting

# OIDC Key
Setting.objects.update_or_create(
    key='SOCIAL_AUTH_OIDC_KEY',
    defaults={'value': 'awx-oidc'}
)
print('✅ SOCIAL_AUTH_OIDC_KEY: awx-oidc')

# OIDC Secret
Setting.objects.update_or_create(
    key='SOCIAL_AUTH_OIDC_SECRET',
    defaults={'value': '${CLIENT_SECRET}'}
)
print('✅ SOCIAL_AUTH_OIDC_SECRET: ${CLIENT_SECRET:0:20}...')

# OIDC Endpoint - ansible-realm
Setting.objects.update_or_create(
    key='SOCIAL_AUTH_OIDC_OIDC_ENDPOINT',
    defaults={'value': '${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}'}
)
print('✅ SOCIAL_AUTH_OIDC_OIDC_ENDPOINT: ${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}')

# OIDC Verify SSL
Setting.objects.update_or_create(
    key='SOCIAL_AUTH_OIDC_VERIFY_SSL',
    defaults={'value': False}
)
print('✅ SOCIAL_AUTH_OIDC_VERIFY_SSL: False')

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

print('')
print('현재 OIDC 설정:')
print('=' * 60)
for key in ['SOCIAL_AUTH_OIDC_KEY', 'SOCIAL_AUTH_OIDC_OIDC_ENDPOINT', 'SOCIAL_AUTH_OIDC_VERIFY_SSL']:
    try:
        setting = Setting.objects.get(key=key)
        print(f'{key}: {setting.value}')
    except Setting.DoesNotExist:
        print(f'{key}: Not set')
PYTHON_EOF

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✅ AWX OIDC 설정 완료!"
    echo "=========================================="
    echo ""
    echo "설정 내용:"
    echo "  - Realm: ${KEYCLOAK_REALM}"
    echo "  - OIDC Client: awx-oidc"
    echo "  - OIDC Endpoint: ${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}"
    echo "  - 조직: Default (자동 사용자 추가)"
    echo ""
    echo "다음 단계:"
    echo "  1. AWX Web Pod 재시작 (설정 적용):"
    echo "     kubectl rollout restart deployment/awx-web -n awx"
    echo ""
    echo "  2. 재시작 완료 대기:"
    echo "     kubectl rollout status deployment/awx-web -n awx"
    echo ""
    echo "  3. AWX 접속: http://192.168.64.26:30000"
    echo "  4. 'Sign in with OIDC' 버튼 클릭"
    echo "  5. Keycloak ansible-realm으로 로그인 (admin/admin123)"
    echo ""
else
    echo "❌ AWX OIDC 설정 실패"
    exit 1
fi
