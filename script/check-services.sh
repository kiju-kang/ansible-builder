#!/bin/bash

echo "====================================="
echo "Ansible Builder 서비스 상태 확인"
echo "====================================="
echo "실행 시간: $(date)"
echo ""

# 1. Backend
echo "1. Backend Service (Port 8000)"
if ps aux | grep -v grep | grep "uvicorn main:app" > /dev/null; then
    echo "   ✅ Running"
    ps aux | grep -v grep | grep "uvicorn main:app" | awk '{print "   PID: "$2", CPU: "$3"%, MEM: "$4"%"}'
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "   ✅ API responding"
    else
        echo "   ⚠️  API not responding"
    fi
else
    echo "   ❌ Not Running"
fi
echo ""

# 2. Keycloak
echo "2. Keycloak (Docker)"
if docker ps --format "{{.Names}}" | grep -q keycloak; then
    docker ps --filter name=keycloak --format "   {{.Names}}: {{.Status}}"
    if curl -s http://localhost:8080/health > /dev/null 2>&1; then
        echo "   ✅ API responding"
    else
        echo "   ⚠️  API not responding"
    fi
else
    echo "   ❌ Not Running"
fi
echo ""

# 3. AWX
echo "3. AWX (Kubernetes)"
if kubectl get pods -n awx --no-headers 2>/dev/null | grep -q Running; then
    kubectl get pods -n awx --no-headers | awk '{print "   "$1": "$3}'
    if curl -s http://192.168.64.26/api/v2/ping/ > /dev/null 2>&1; then
        echo "   ✅ API responding"
    else
        echo "   ⚠️  API not responding"
    fi
else
    echo "   ❌ No pods running"
fi
echo ""

# 4. PostgreSQL (Kubernetes AWX)
echo "4. PostgreSQL (AWX Kubernetes)"
if kubectl get pod awx-postgres-15-0 -n awx 2>/dev/null | grep -q Running; then
    echo "   ✅ Running (awx-postgres-15-0)"
    # Check playbook count via AWX PostgreSQL
    PLAYBOOK_COUNT=$(kubectl exec -it awx-postgres-15-0 -n awx -- psql -U awx -d awx -c "SELECT count(*) FROM ansible_builder_playbooks;" 2>/dev/null | grep -E "^\s+[0-9]+" | tr -d ' \r')
    if [ ! -z "$PLAYBOOK_COUNT" ]; then
        echo "   Playbooks in DB: $PLAYBOOK_COUNT"
    fi
else
    echo "   ❌ Not Running"
fi
echo ""

# 5. 포트 상태
echo "5. Port Status"
echo "   Port 8000 (Backend): $(netstat -tln 2>/dev/null | grep :8000 > /dev/null && echo '✅ Listening' || echo '❌ Not Listening')"
echo "   Port 8080 (Keycloak): $(netstat -tln 2>/dev/null | grep :8080 > /dev/null && echo '✅ Listening' || echo '❌ Not Listening')"
echo "   Port 5432 (PostgreSQL): $(netstat -tln 2>/dev/null | grep :5432 > /dev/null && echo '✅ Listening' || echo '❌ Not Listening')"
echo ""

# 6. 디스크 사용량
echo "6. Disk Usage"
df -h / | tail -1 | awk '{print "   Root: "$3" / "$2" ("$5")"}'
du -sh /root/ansible-builder/ansible-builder/backend/ 2>/dev/null | awk '{print "   Backend: "$1}'
du -sh /root/ansible-builder/ansible-builder/frontend/frontend/dist/ 2>/dev/null | awk '{print "   Frontend: "$1}'
echo ""

# 7. 최근 에러 (Backend)
echo "7. Recent Errors (Backend - Last 10 minutes)"
if [ -f /root/ansible-builder/ansible-builder/backend/backend.log ]; then
    ERROR_COUNT=$(grep ERROR /root/ansible-builder/ansible-builder/backend/backend.log | tail -100 | wc -l)
    echo "   Error count in last 100 lines: $ERROR_COUNT"
    if [ $ERROR_COUNT -gt 0 ]; then
        echo "   Last error:"
        grep ERROR /root/ansible-builder/ansible-builder/backend/backend.log | tail -1 | cut -c 1-100
    fi
else
    echo "   No log file found"
fi
echo ""

echo "====================================="
