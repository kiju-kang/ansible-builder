#!/bin/bash

# Keycloak 자동 설정 스크립트
# Realm, Client, Roles, Users 자동 생성

set -e

echo "=== Keycloak 자동 설정 시작 ==="

# 설정 변수
KEYCLOAK_URL="http://192.168.64.26:8080"
ADMIN_USER="admin"
ADMIN_PASS="admin123"
REALM_NAME="ansible-realm"

# Keycloak이 완전히 시작될 때까지 대기
echo "1. Keycloak 서버 시작 대기 중..."
timeout 180 bash -c 'until curl -sf http://192.168.64.26:8080/health/ready > /dev/null 2>&1; do sleep 5; done' || {
    echo "Error: Keycloak 서버가 시작되지 않았습니다."
    exit 1
}
echo "✓ Keycloak 서버 준비 완료"

# kcadm.sh 경로
KCADM="docker exec -i keycloak /opt/keycloak/bin/kcadm.sh"

# 관리자 로그인
echo ""
echo "2. 관리자 로그인..."
$KCADM config credentials --server $KEYCLOAK_URL --realm master --user $ADMIN_USER --password $ADMIN_PASS

# Realm 생성
echo ""
echo "3. Realm 생성: $REALM_NAME"
$KCADM create realms -s realm=$REALM_NAME -s enabled=true || echo "Realm이 이미 존재합니다."

# AWX Client 생성
echo ""
echo "4. AWX Client 생성..."
AWX_CLIENT_EXISTS=$($KCADM get clients -r $REALM_NAME --fields clientId | grep -c "awx-client" || true)
if [ "$AWX_CLIENT_EXISTS" -eq 0 ]; then
    $KCADM create clients -r $REALM_NAME \
        -s clientId=awx-client \
        -s enabled=true \
        -s clientAuthenticatorType=client-secret \
        -s secret=awx-secret-key \
        -s redirectUris='["http://192.168.64.26:8000/*","http://localhost:8000/*"]' \
        -s webOrigins='["http://192.168.64.26:8000","http://localhost:8000"]' \
        -s standardFlowEnabled=true \
        -s directAccessGrantsEnabled=true
    echo "✓ AWX Client 생성 완료"
else
    echo "✓ AWX Client가 이미 존재합니다."
fi

# Ansible Builder Client 생성
echo ""
echo "5. Ansible Builder Client 생성..."
BUILDER_CLIENT_EXISTS=$($KCADM get clients -r $REALM_NAME --fields clientId | grep -c "ansible-builder-client" || true)
if [ "$BUILDER_CLIENT_EXISTS" -eq 0 ]; then
    $KCADM create clients -r $REALM_NAME \
        -s clientId=ansible-builder-client \
        -s enabled=true \
        -s publicClient=true \
        -s redirectUris='["http://192.168.64.26:3000/*","http://192.168.64.26:8000/*","http://localhost:3000/*","http://localhost:8000/*"]' \
        -s webOrigins='["+"]' \
        -s standardFlowEnabled=true \
        -s directAccessGrantsEnabled=true
    echo "✓ Ansible Builder Client 생성 완료"
else
    echo "✓ Ansible Builder Client가 이미 존재합니다."
fi

# Roles 생성
echo ""
echo "6. Realm Roles 생성..."
for ROLE in admin user awx-admin awx-user; do
    ROLE_EXISTS=$($KCADM get roles -r $REALM_NAME --fields name | grep -c "\"$ROLE\"" || true)
    if [ "$ROLE_EXISTS" -eq 0 ]; then
        $KCADM create roles -r $REALM_NAME -s name=$ROLE
        echo "  ✓ Role '$ROLE' 생성됨"
    else
        echo "  ✓ Role '$ROLE'가 이미 존재합니다."
    fi
done

# Admin 사용자 생성
echo ""
echo "7. Admin 사용자 생성..."
ADMIN_USER_EXISTS=$($KCADM get users -r $REALM_NAME --fields username | grep -c "\"admin\"" || true)
if [ "$ADMIN_USER_EXISTS" -eq 0 ]; then
    $KCADM create users -r $REALM_NAME \
        -s username=admin \
        -s email=admin@example.com \
        -s firstName=Admin \
        -s lastName=User \
        -s enabled=true \
        -s emailVerified=true

    # 비밀번호 설정
    ADMIN_USER_ID=$($KCADM get users -r $REALM_NAME -q username=admin --fields id | grep -oP '(?<="id" : ")[^"]+')
    $KCADM set-password -r $REALM_NAME --username admin --new-password admin123

    # Role 할당
    $KCADM add-roles -r $REALM_NAME --uusername admin --rolename admin
    $KCADM add-roles -r $REALM_NAME --uusername admin --rolename awx-admin

    echo "✓ Admin 사용자 생성 완료"
else
    echo "✓ Admin 사용자가 이미 존재합니다."
fi

# Test 사용자 생성
echo ""
echo "8. Test 사용자 생성..."
TEST_USER_EXISTS=$($KCADM get users -r $REALM_NAME --fields username | grep -c "\"testuser\"" || true)
if [ "$TEST_USER_EXISTS" -eq 0 ]; then
    $KCADM create users -r $REALM_NAME \
        -s username=testuser \
        -s email=testuser@example.com \
        -s firstName=Test \
        -s lastName=User \
        -s enabled=true \
        -s emailVerified=true

    # 비밀번호 설정
    $KCADM set-password -r $REALM_NAME --username testuser --new-password test123

    # Role 할당
    $KCADM add-roles -r $REALM_NAME --uusername testuser --rolename user
    $KCADM add-roles -r $REALM_NAME --uusername testuser --rolename awx-user

    echo "✓ Test 사용자 생성 완료"
else
    echo "✓ Test 사용자가 이미 존재합니다."
fi

# AWX Client Secret 출력
echo ""
echo "9. AWX Client Secret 확인..."
AWX_CLIENT_ID=$($KCADM get clients -r $REALM_NAME -q clientId=awx-client --fields id | grep -oP '(?<="id" : ")[^"]+' | head -1)
if [ -n "$AWX_CLIENT_ID" ]; then
    AWX_SECRET=$($KCADM get clients/$AWX_CLIENT_ID/client-secret -r $REALM_NAME | grep -oP '(?<="value" : ")[^"]+')
    echo "AWX Client Secret: $AWX_SECRET"
    echo "이 값을 AWX 설정에 사용하세요."
fi

echo ""
echo "=== Keycloak 설정 완료 ==="
echo ""
echo "접속 정보:"
echo "  URL: http://192.168.64.26:8080"
echo "  Realm: $REALM_NAME"
echo "  Admin Console: http://192.168.64.26:8080/admin"
echo ""
echo "테스트 계정:"
echo "  Admin - username: admin, password: admin123"
echo "  User  - username: testuser, password: test123"
echo ""
