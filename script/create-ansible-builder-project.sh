#!/bin/bash

echo "=========================================="
echo "Ansible Builder 전용 프로젝트 생성"
echo "=========================================="
echo ""

AWX_URL="http://192.168.64.26:30000"
AWX_TOKEN="A6tZWbC5pFXUynXvhogzzC0BDWulOj"

echo "1. AWX 프로젝트 디렉토리 생성..."

# Create project directory on AWX task pod
kubectl exec -n awx deployment/awx-task -c awx-task -- bash -c "
mkdir -p /var/lib/awx/projects/builder_project
chown awx:awx /var/lib/awx/projects/builder_project
chmod 755 /var/lib/awx/projects/builder_project
echo '✅ Directory created: /var/lib/awx/projects/builder_project'
"

echo ""
echo "2. executor playbook 복사..."

# Copy executor playbook
cat /root/ansible-builder/ansible-builder/backend/ansible_builder_executor_sent_to_awx.yml | \
kubectl exec -i -n awx deployment/awx-task -c awx-task -- \
tee /var/lib/awx/projects/builder_project/ansible_builder_executor.yml > /dev/null

kubectl exec -n awx deployment/awx-task -c awx-task -- \
chown awx:awx /var/lib/awx/projects/builder_project/ansible_builder_executor.yml

echo "✅ Executor playbook copied"

echo ""
echo "3. AWX에 Manual 프로젝트 생성..."

# Create manual project
PROJECT_RESPONSE=$(curl -s -X POST "${AWX_URL}/api/v2/projects/" \
  -H "Authorization: Bearer ${AWX_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Builder Project",
    "description": "Manual project for ansible-builder (no Git sync required)",
    "organization": 1,
    "scm_type": "",
    "local_path": "builder_project",
    "scm_update_on_launch": false,
    "scm_delete_on_update": false,
    "scm_clean": false
  }')

PROJECT_ID=$(echo "$PROJECT_RESPONSE" | jq -r '.id')

if [ ! -z "$PROJECT_ID" ] && [ "$PROJECT_ID" != "null" ]; then
    echo "✅ Manual 프로젝트 생성 완료 (ID: ${PROJECT_ID})"
    echo "   이름: Builder Project"
    echo "   경로: /var/lib/awx/projects/builder_project"
else
    echo "⚠️  프로젝트 생성 실패 또는 이미 존재"
    echo "$PROJECT_RESPONSE" | jq '.'

    # Try to get existing project
    PROJECT_ID=$(curl -s -H "Authorization: Bearer ${AWX_TOKEN}" \
      "${AWX_URL}/api/v2/projects/" | \
      jq -r '.results[] | select(.local_path == "builder_project") | .id')

    if [ ! -z "$PROJECT_ID" ] && [ "$PROJECT_ID" != "null" ]; then
        echo "✅ 기존 프로젝트 사용 (ID: ${PROJECT_ID})"
    fi
fi

echo ""
echo "4. ansible-builder backend 설정 업데이트..."

# Update backend configuration to use new project
if [ ! -z "$PROJECT_ID" ] && [ "$PROJECT_ID" != "null" ]; then
    echo "PROJECT_ID=${PROJECT_ID}" > /root/ansible-builder-project-id.txt
    echo "✅ 프로젝트 ID 저장: /root/ansible-builder-project-id.txt"
fi

echo ""
echo "=========================================="
echo "✅ 설정 완료!"
echo "=========================================="
echo ""
echo "생성된 리소스:"
echo "  - AWX 프로젝트: Builder Project (ID: ${PROJECT_ID})"
echo "  - 로컬 경로: /var/lib/awx/projects/builder_project"
echo "  - Playbook: ansible_builder_executor.yml"
echo ""
echo "다음 단계:"
echo "  ansible-builder가 프로젝트 ID ${PROJECT_ID}를 사용하도록 설정"
echo "  또는 기존 job template을 새 프로젝트로 변경"
echo ""
