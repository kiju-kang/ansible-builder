# AWX Projects PV 마이그레이션 가이드 (2Gi → 8Gi)

## 문제 상황

AWX Web 및 Task Pod에서 `init-projects` 컨테이너가 실패하며 CrashLoopBackOff 발생:

```
Back-off restarting failed container init-projects
```

**원인**: PV 추가 또는 변경 시 권한 문제 또는 디렉토리 접근 실패

---

## init-projects 컨테이너 역할

```bash
chmod 775 /var/lib/awx/projects
chgrp 1000 /var/lib/awx/projects
```

- AWX Projects 디렉토리의 권한을 775로 설정
- 그룹을 GID 1000 (AWX 사용자)으로 변경
- ReadWriteMany 볼륨에 대한 다중 Pod 접근 허용

---

## 현재 상태 확인

### 1. PV/PVC 상태 확인

```bash
kubectl get pv,pvc -n awx | grep projects
```

**정상 출력**:
```
persistentvolume/awx-projects-pv   2Gi   RWX   Retain   Bound   awx/awx-projects-claim
persistentvolumeclaim/awx-projects-claim   Bound   awx-projects-pv   2Gi   RWX
```

### 2. Pod 상태 확인

```bash
kubectl get pods -n awx | grep -E "awx-web|awx-task"
```

**문제 발생 시**:
```
awx-web-xxx    0/3     Init:CrashLoopBackOff   5          5m
awx-task-xxx   0/4     Init:CrashLoopBackOff   5          5m
```

### 3. init-projects 로그 확인

```bash
# AWX Web Pod
kubectl logs -n awx -l app.kubernetes.io/name=awx-web -c init-projects

# AWX Task Pod
kubectl logs -n awx -l app.kubernetes.io/name=awx-task -c init-projects
```

**에러 예시**:
```
chmod: cannot access '/var/lib/awx/projects': No such file or directory
chgrp: cannot access '/var/lib/awx/projects': No such file or directory
```

---

## 원인 분석

### 원인 1: 호스트 디렉토리 미존재

**증상**: init-projects에서 "No such file or directory" 에러

**확인**:
```bash
ls -la /data/awx-projects-8gi/
```

**해결**:
```bash
sudo mkdir -p /data/awx-projects-8gi
sudo chmod 775 /data/awx-projects-8gi
sudo chown 26:1000 /data/awx-projects-8gi
```

---

### 원인 2: 잘못된 권한

**증상**: init-projects에서 "Permission denied" 에러

**확인**:
```bash
ls -la /data/ | grep awx-projects
```

**문제**:
```
drwxr-xr-x.  3 root root  30 Dec 15 16:02 awx-projects-8gi  # ← root:root, 755
```

**해결**:
```bash
sudo chown 26:1000 /data/awx-projects-8gi
sudo chmod 775 /data/awx-projects-8gi
```

**올바른 권한**:
```
drwxrwxr-x.  3   26 gaia_bot   30 Dec 15 16:02 awx-projects-8gi
```

- UID 26: AWX 컨테이너 사용자
- GID 1000: AWX 그룹
- 권한 775: rwxrwxr-x (소유자/그룹 읽기/쓰기/실행, 기타 읽기/실행)

---

### 원인 3: PV hostPath 경로 불일치

**증상**: PVC가 Bound되지 않거나 Pod가 마운트 실패

**확인**:
```bash
kubectl get pv awx-projects-pv-8gi -o jsonpath='{.spec.hostPath.path}'
```

**문제**: PV YAML의 `hostPath.path`와 실제 디렉토리 경로가 다름

**해결**: PV YAML 수정 후 재생성

---

### 원인 4: PVC가 기존 PV에 바인딩됨

**증상**: 새 8Gi PV 생성했지만 PVC가 여전히 2Gi PV 사용

**확인**:
```bash
kubectl describe pvc awx-projects-claim -n awx | grep Volume
```

**해결**: 기존 PVC 삭제 후 재생성 (아래 마이그레이션 절차 참조)

---

## 2Gi → 8Gi PV 마이그레이션 절차

### 사전 준비

#### 1. 기존 데이터 백업

```bash
# 백업 디렉토리 생성
sudo mkdir -p /backup/awx-projects

# 기존 데이터 복사
sudo rsync -av /data/awx-projects/ /backup/awx-projects/

# 백업 확인
ls -la /backup/awx-projects/
```

#### 2. 새 디렉토리 생성 및 권한 설정

```bash
# 새 8Gi 디렉토리 생성
sudo mkdir -p /data/awx-projects-8gi

# 올바른 권한 설정
sudo chown 26:1000 /data/awx-projects-8gi
sudo chmod 775 /data/awx-projects-8gi

# 확인
ls -la /data/ | grep awx-projects-8gi
# 출력: drwxrwxr-x.  2   26 gaia_bot   6 Dec 16 17:45 awx-projects-8gi
```

#### 3. 기존 데이터 복사 (선택)

```bash
# 기존 데이터를 새 디렉토리로 복사
sudo rsync -av /data/awx-projects/ /data/awx-projects-8gi/

# 권한 재설정
sudo chown -R 26:1000 /data/awx-projects-8gi
sudo find /data/awx-projects-8gi -type d -exec chmod 775 {} \;
sudo find /data/awx-projects-8gi -type f -exec chmod 664 {} \;
```

---

### 마이그레이션 실행

#### Step 1: AWX Operator 중지 (선택)

```bash
# AWX 리소스가 자동으로 재생성되지 않도록 Operator 스케일 다운
kubectl scale deployment awx-operator-controller-manager -n awx --replicas=0

# 확인
kubectl get deployment awx-operator-controller-manager -n awx
```

#### Step 2: 기존 AWX Pod 삭제

```bash
# AWX Web 및 Task Pod 삭제
kubectl delete deployment awx-web -n awx
kubectl delete deployment awx-task -n awx

# 확인
kubectl get pods -n awx | grep awx
```

#### Step 3: 기존 PVC 삭제

```bash
# PVC 삭제 (PV는 Retain 정책이므로 데이터 유지됨)
kubectl delete pvc awx-projects-claim -n awx

# 확인
kubectl get pvc -n awx | grep projects
```

#### Step 4: 기존 PV Unbind (선택)

```bash
# PV의 claimRef 제거하여 Released 상태로 변경
kubectl patch pv awx-projects-pv -p '{"spec":{"claimRef": null}}'

# 확인
kubectl get pv awx-projects-pv
# Status: Available 또는 Released
```

#### Step 5: 새 8Gi PV 생성

```bash
# PV 생성
kubectl apply -f /root/ansible-builder/k8s/awx-projects-pv-8gi.yaml

# 확인
kubectl get pv | grep projects
```

**예상 출력**:
```
awx-projects-pv      2Gi   RWX   Retain   Released   manual
awx-projects-pv-8gi  8Gi   RWX   Retain   Available  manual
```

#### Step 6: 새 PVC 생성

```bash
# PVC 생성
kubectl apply -f /root/ansible-builder/k8s/awx-projects-pvc-8gi.yaml

# 바인딩 확인
kubectl get pvc -n awx awx-projects-claim
```

**예상 출력**:
```
NAME                  STATUS   VOLUME                CAPACITY   ACCESS MODES
awx-projects-claim    Bound    awx-projects-pv-8gi   8Gi        RWX
```

#### Step 7: AWX 재배포

**방법 A: Operator로 재배포 (권장)**

```bash
# Operator 다시 활성화
kubectl scale deployment awx-operator-controller-manager -n awx --replicas=1

# AWX CR 수정하여 재배포 트리거
kubectl patch awx awx -n awx -p '{"spec":{"projects_storage_size":"8Gi"}}' --type=merge

# Pod 생성 확인
kubectl get pods -n awx -w
```

**방법 B: Deployment 재생성 (수동)**

```bash
# AWX Deployment YAML을 백업에서 재적용
kubectl apply -f /backup/awx-deployment.yaml
```

#### Step 8: init-projects 성공 확인

```bash
# init-projects 로그 확인
kubectl logs -n awx -l app.kubernetes.io/name=awx-web -c init-projects

# 성공 시 출력: (로그 없음 - 명령 성공)
```

```bash
# Pod 상태 확인
kubectl get pods -n awx | grep awx
```

**정상 출력**:
```
awx-web-xxx    3/3   Running   0   2m
awx-task-xxx   4/4   Running   0   2m
```

---

## 트러블슈팅

### 에러 1: "No such file or directory"

```bash
# init-projects 로그
chmod: cannot access '/var/lib/awx/projects': No such file or directory
```

**원인**: 호스트 디렉토리 미존재

**해결**:
```bash
# 디렉토리 생성 및 권한 설정
sudo mkdir -p /data/awx-projects-8gi
sudo chown 26:1000 /data/awx-projects-8gi
sudo chmod 775 /data/awx-projects-8gi

# Pod 재시작
kubectl rollout restart deployment/awx-web -n awx
kubectl rollout restart deployment/awx-task -n awx
```

---

### 에러 2: "Permission denied"

```bash
# init-projects 로그
chmod: changing permissions of '/var/lib/awx/projects': Operation not permitted
```

**원인**: 호스트 디렉토리 권한 문제

**해결**:
```bash
# 권한 재설정
sudo chown -R 26:1000 /data/awx-projects-8gi
sudo chmod 775 /data/awx-projects-8gi

# SELinux 컨텍스트 설정 (필요 시)
sudo chcon -Rt svirt_sandbox_file_t /data/awx-projects-8gi
```

---

### 에러 3: PVC Pending 상태

```bash
kubectl get pvc -n awx awx-projects-claim
# STATUS: Pending
```

**원인**: PV가 Available 상태가 아니거나 스펙 불일치

**해결**:
```bash
# PV 상태 확인
kubectl get pv | grep projects

# PV Released 상태면 claimRef 제거
kubectl patch pv awx-projects-pv-8gi -p '{"spec":{"claimRef": null}}'

# PVC 재생성
kubectl delete pvc awx-projects-claim -n awx
kubectl apply -f /root/ansible-builder/k8s/awx-projects-pvc-8gi.yaml
```

---

### 에러 4: init-projects 반복 실패 (CrashLoopBackOff)

**원인**: 볼륨 마운트 실패 또는 권한 문제

**진단**:
```bash
# Pod Describe에서 상세 에러 확인
kubectl describe pod -n awx -l app.kubernetes.io/name=awx-web | grep -A 20 Events

# 볼륨 마운트 확인
kubectl describe pod -n awx -l app.kubernetes.io/name=awx-web | grep -A 10 "Volumes:"
```

**해결**:
```bash
# 1. 호스트 디렉토리 권한 재확인
ls -la /data/awx-projects-8gi/

# 2. PV hostPath 확인
kubectl get pv awx-projects-pv-8gi -o yaml | grep -A 2 hostPath

# 3. 필요시 PV 재생성
kubectl delete pv awx-projects-pv-8gi
kubectl apply -f /root/ansible-builder/k8s/awx-projects-pv-8gi.yaml

# 4. Pod 재시작
kubectl delete pod -n awx -l app.kubernetes.io/name=awx-web
kubectl delete pod -n awx -l app.kubernetes.io/name=awx-task
```

---

## 롤백 절차

마이그레이션 실패 시 기존 2Gi PV로 복구:

```bash
# 1. 새 PVC 삭제
kubectl delete pvc awx-projects-claim -n awx

# 2. 기존 PV의 claimRef 제거
kubectl patch pv awx-projects-pv -p '{"spec":{"claimRef": null}}'

# 3. 기존 PVC 재생성 (2Gi)
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: awx-projects-claim
  namespace: awx
spec:
  storageClassName: manual
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 2Gi
EOF

# 4. AWX Pod 재시작
kubectl rollout restart deployment/awx-web -n awx
kubectl rollout restart deployment/awx-task -n awx

# 5. 확인
kubectl get pvc -n awx awx-projects-claim
kubectl get pods -n awx | grep awx
```

---

## 빠른 체크리스트

### ✅ 마이그레이션 전

- [ ] 기존 데이터 백업 완료
- [ ] 새 디렉토리 생성: `/data/awx-projects-8gi`
- [ ] 디렉토리 권한: `chown 26:1000`, `chmod 775`
- [ ] 기존 데이터 복사 (선택)
- [ ] AWX Operator 스케일 다운 (선택)

### ✅ 마이그레이션 중

- [ ] 기존 PVC 삭제
- [ ] 기존 PV Unbind (claimRef 제거)
- [ ] 새 8Gi PV 생성 및 Available 확인
- [ ] 새 PVC 생성 및 Bound 확인
- [ ] AWX 재배포

### ✅ 마이그레이션 후

- [ ] init-projects 성공 (로그 확인)
- [ ] AWX Web Pod Running (3/3)
- [ ] AWX Task Pod Running (4/4)
- [ ] PVC 8Gi Bound 확인
- [ ] AWX UI 접속 가능
- [ ] Demo Project 정상 동기화

---

## 참고 명령어

### 현재 상태 한눈에 보기

```bash
echo "=== PV/PVC 상태 ==="
kubectl get pv,pvc -n awx | grep projects

echo -e "\n=== 호스트 디렉토리 권한 ==="
ls -la /data/ | grep awx-projects

echo -e "\n=== AWX Pod 상태 ==="
kubectl get pods -n awx | grep -E "awx-web|awx-task"

echo -e "\n=== init-projects 로그 (최근) ==="
kubectl logs -n awx -l app.kubernetes.io/name=awx-web -c init-projects --tail=10 2>&1
```

### 완전 초기화 (주의!)

```bash
# 모든 AWX 리소스 삭제 및 재생성
kubectl delete awx awx -n awx
kubectl delete pvc awx-projects-claim -n awx
kubectl delete pv awx-projects-pv awx-projects-pv-8gi

# 호스트 디렉토리 초기화
sudo rm -rf /data/awx-projects-8gi
sudo mkdir -p /data/awx-projects-8gi
sudo chown 26:1000 /data/awx-projects-8gi
sudo chmod 775 /data/awx-projects-8gi

# 새 PV/PVC 생성
kubectl apply -f /root/ansible-builder/k8s/awx-projects-pv-8gi.yaml
kubectl apply -f /root/ansible-builder/k8s/awx-projects-pvc-8gi.yaml

# AWX 재생성
kubectl apply -f /backup/awx.yaml
```

---

## 요약

### 문제
init-projects 컨테이너 실패로 AWX Pod CrashLoopBackOff

### 원인
1. 호스트 디렉토리 미존재
2. 잘못된 디렉토리 권한
3. PV/PVC 바인딩 문제

### 해결
1. 호스트 디렉토리 생성: `mkdir -p /data/awx-projects-8gi`
2. 권한 설정: `chown 26:1000`, `chmod 775`
3. PV/PVC 재생성
4. AWX Pod 재시작

### 확인
```bash
# init-projects 성공 확인
kubectl logs -n awx -l app.kubernetes.io/name=awx-web -c init-projects

# Pod Running 확인
kubectl get pods -n awx | grep awx
```

---

**작성일**: 2025-12-16
**대상 서버**: 192.168.64.26, 10.2.14.160
**AWX 버전**: 24.6.1
