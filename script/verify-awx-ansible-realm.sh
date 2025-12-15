#!/bin/bash

echo "=========================================="
echo "AWX ansible-realm 설정 확인"
echo "=========================================="
echo ""

KEYCLOAK_URL="http://192.168.64.26:30002"

# Get admin token
echo "1. Keycloak ansible-realm 확인..."
ADMIN_TOKEN=$(curl -s -X POST "${KEYCLOAK_URL}/realms/master/protocol/openid-connect/token" \
  -d "client_id=admin-cli" \
  -d "username=admin" \
  -d "password=admin123" \
  -d "grant_type=password" | jq -r '.access_token')

if [ -z "$ADMIN_TOKEN" ] || [ "$ADMIN_TOKEN" == "null" ]; then
    echo "❌ Keycloak 토큰 획득 실패"
    exit 1
fi

# Check ansible-realm client
CLIENTS=$(curl -s -X GET "${KEYCLOAK_URL}/admin/realms/ansible-realm/clients" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}")

AWX_CLIENT=$(echo "$CLIENTS" | jq '.[] | select(.clientId == "awx-oidc")')

if [ -z "$AWX_CLIENT" ] || [ "$AWX_CLIENT" == "null" ]; then
    echo "❌ ansible-realm에 awx-oidc 클라이언트가 없습니다"
    exit 1
fi

echo "✅ ansible-realm의 awx-oidc 클라이언트 확인됨"
echo ""
echo "Redirect URIs:"
echo "$AWX_CLIENT" | jq -r '.redirectUris[]' | sed 's/^/  - /'

echo ""
echo "2. AWX Pod 상태 확인..."
kubectl get pods -n awx -l app.kubernetes.io/name=awx-web

echo ""
echo "3. AWX OIDC 설정 확인..."
AWX_WEB_POD=$(kubectl get pods -n awx -l app.kubernetes.io/name=awx-web -o jsonpath='{.items[0].metadata.name}')

if [ -z "$AWX_WEB_POD" ]; then
    echo "❌ AWX web pod를 찾을 수 없습니다"
    exit 1
fi

kubectl exec -n awx ${AWX_WEB_POD} -c awx-web -- awx-manage shell << 'EOF'
from awx.conf.models import Setting

try:
    endpoint = Setting.objects.get(key='SOCIAL_AUTH_OIDC_OIDC_ENDPOINT')
    key = Setting.objects.get(key='SOCIAL_AUTH_OIDC_KEY')

    print(f"OIDC Endpoint: {endpoint.value}")
    print(f"OIDC Client ID: {key.value}")

    if "ansible-realm" in endpoint.value:
        print("\n✅ AWX가 ansible-realm을 사용하도록 설정되었습니다!")
    else:
        print("\n⚠️  AWX가 ansible-realm을 사용하지 않습니다")

except Exception as e:
    print(f"❌ 설정 확인 실패: {e}")
EOF

echo ""
echo "=========================================="
echo "✅ 설정 확인 완료"
echo "=========================================="
echo ""
echo "테스트 방법:"
echo "  1. AWX 접속: http://192.168.64.26:30000"
echo "  2. 'Sign in with OIDC' 버튼 클릭"
echo "  3. Keycloak ansible-realm 로그인 화면 확인"
echo "  4. 사용자 인증: admin / admin123"
echo ""
