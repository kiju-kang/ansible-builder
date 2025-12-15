#!/bin/bash

echo "=========================================="
echo "Instance Group 할당"
echo "=========================================="
echo ""

AWX_WEB_POD=$(kubectl get pods -n awx -l app.kubernetes.io/name=awx-web -o jsonpath='{.items[0].metadata.name}')

echo "AWX Pod: $AWX_WEB_POD"
echo ""

kubectl exec -n awx ${AWX_WEB_POD} -c awx-web -- awx-manage shell << 'EOF'
from awx.main.models import Organization, InstanceGroup

# Get Default organization
org = Organization.objects.get(name='Default')
print(f"Organization: {org.name} (ID: {org.id})")

# Get controlplane instance group
ig = InstanceGroup.objects.get(name='controlplane')
print(f"Instance Group: {ig.name} (ID: {ig.id}, Capacity: {ig.capacity})")

# Assign instance group to organization
org.instance_groups.add(ig)
print(f"\n✅ Instance group '{ig.name}' assigned to organization '{org.name}'")

# Verify
print(f"\nOrganization instance groups:")
for group in org.instance_groups.all():
    print(f"  - {group.name} (Capacity: {group.capacity})")
EOF

echo ""
echo "=========================================="
echo "✅ 완료!"
echo "=========================================="
