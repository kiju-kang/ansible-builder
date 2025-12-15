# AWX 설정 완료 상태 요약

## ✅ 완료된 작업

### 1. Keycloak ansible-realm 설정
- ✅ ansible-realm에 AWX OIDC 클라이언트 생성
- ✅ Keycloak 사용자를 developer 그룹에 추가
- ✅ AWX OIDC 매핑 설정 (ansible-realm 사용)

### 2. AWX 팀 및 권한 설정
- ✅ developer 팀 생성 (ID: 1)
- ✅ OIDC 사용자를 Default 조직 관리자로 추가
- ✅ OIDC 사용자를 developer 팀에 추가
- ✅ 팀 멤버: kiju.kang@kt.com

### 3. 프로젝트 설정
- ✅ Demo Project를 Git에서 Manual 타입으로 변경
- ✅ ansible_builder_executor.yml playbook 복사 완료
- ✅ 프로젝트 디렉토리: /var/lib/awx/projects/_6__demo_project

### 4. 인스턴스 그룹 설정
- ✅ controlplane 인스턴스 그룹 확인 (Capacity: 315)
- ✅ Default 조직에 controlplane 인스턴스 그룹 할당

### 5. ansible-builder 설정
- ✅ Job URL에 /output 경로 추가 (직접 output 페이지로 리디렉션)
- ✅ Backend 재시작 및 정상 작동

## ⚠️  현재 이슈

### Job 실행 대기 중 (Pending 상태)
- 증상: Job이 생성되지만 "pending" 상태에서 실행되지 않음
- 원인: AWX logs에 "needs capacity" 메시지
- Job ID: 210 (현재 pending)

### 가능한 원인
1. Instance group과 job template 간 매핑 문제
2. AWX dispatcher 재시작 필요
3. Inventory 또는 credential 설정 문제

## 📋 현재 구성

| 항목 | 값 |
|------|-----|
| Organization | Default (ID: 1) |
| Team | developer (ID: 1) |
| Instance Group | controlplane (Capacity: 315) |
| Project | Demo Project (ID: 6, Manual) |
| Playbook | ansible_builder_executor.yml |
| Job Template | ID: 68 |
| Inventory | ansible_builder_60 (ID: 22, 1 host) |

## 🔧 생성된 스크립트

1. `/root/configure-awx-ansible-realm.sh` - Keycloak ansible-realm 설정
2. `/root/apply-awx-ansible-realm-settings.sh` - AWX OIDC 설정 적용
3. `/root/add-users-to-keycloak-group.sh` - 사용자 그룹 추가
4. `/root/setup-awx-teams-and-permissions.sh` - AWX 팀 및 권한 설정
5. `/root/fix-awx-user-permissions.sh` - OIDC 사용자 권한 수정
6. `/root/assign-instance-group.sh` - Instance group 할당
7. `/root/create-ansible-builder-project.sh` - Manual 프로젝트 생성

## 🎯 다음 단계

현재 Job이 pending 상태에 있으므로, 다음 중 하나를 시도:

1. **AWX 전체 재시작**
   ```bash
   kubectl rollout restart deployment/awx-web deployment/awx-task -n awx
   ```

2. **Job Template 재생성**
   - ansible-builder가 새로운 job template을 생성하도록 함

3. **수동으로 Job 실행 테스트**
   - AWX UI에서 직접 job template 실행

