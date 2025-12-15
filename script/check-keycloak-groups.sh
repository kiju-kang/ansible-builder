#!/bin/bash

echo "Checking Keycloak ansible-realm groups..."

# Get admin token
TOKEN=$(curl -s -X POST "http://192.168.64.26:30002/realms/master/protocol/openid-connect/token" \
  -d "client_id=admin-cli" \
  -d "username=admin" \
  -d "password=admin123" \
  -d "grant_type=password" | jq -r '.access_token')

if [ -z "$TOKEN" ] || [ "$TOKEN" == "null" ]; then
    echo "Failed to get admin token"
    exit 1
fi

echo "Keycloak ansible-realm Groups:"
echo "================================"
curl -s -X GET "http://192.168.64.26:30002/admin/realms/ansible-realm/groups" \
  -H "Authorization: Bearer $TOKEN" | jq -r '.[] | "  - " + .name + " (path: " + .path + ")"'

echo ""
echo "Keycloak ansible-realm Users:"
echo "================================"
curl -s -X GET "http://192.168.64.26:30002/admin/realms/ansible-realm/users" \
  -H "Authorization: Bearer $TOKEN" | jq -r '.[] | "  - " + .username + " (email: " + (.email // "none") + ")"'
