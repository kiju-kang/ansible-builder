# Ansible Playbook Builder - 빠른 시작 가이드

## 📋 바로 사용할 수 있는 명령어

### 🚀 서비스 시작
```bash
/root/start-all-services.sh
```

### 🛑 서비스 정지
```bash
/root/stop-all-services.sh
```

### 🔍 상태 확인
```bash
/root/check-services.sh
```

### 💾 백업
```bash
/root/backup-ansible-builder.sh
```

---

## 🌐 접속 URL

| 서비스 | URL | 계정 |
|--------|-----|------|
| **Ansible Builder** | http://192.168.64.26:8000 | Keycloak SSO |
| **Keycloak Admin** | http://192.168.64.26:8080 | admin / admin |
| **AWX** | http://192.168.64.26 | admin / password |
| **Backend API Docs** | http://192.168.64.26:8000/docs | - |

---

## 🔧 개별 서비스 명령어

### Backend
```bash
# 시작
cd /root/ansible-builder/ansible-builder/backend
nohup uvicorn main:app --host 0.0.0.0 --port 8000 --reload > backend.log 2>&1 &

# 정지
pkill -f "uvicorn main:app"

# 로그
tail -f /root/ansible-builder/ansible-builder/backend/backend.log

# 상태
curl http://localhost:8000/docs
```

### Frontend
```bash
# 빌드
cd /root/ansible-builder/ansible-builder/frontend/frontend
npm run build

# 브라우저 캐시 클리어: Ctrl+Shift+R
```

### Keycloak
```bash
# 시작/정지
docker start keycloak keycloak-postgres
docker stop keycloak keycloak-postgres

# 로그
docker logs -f keycloak
```

### AWX
```bash
# 상태
kubectl get pods -n awx

# 로그
kubectl logs -f deployment/awx-web -n awx

# 재시작
kubectl rollout restart deployment -n awx
```

---

## 🐛 빠른 문제 해결

### Backend가 응답하지 않을 때
```bash
# 1. 로그 확인
tail -f /root/ansible-builder/ansible-builder/backend/backend.log

# 2. 재시작
pkill -f "uvicorn main:app"
sleep 2
cd /root/ansible-builder/ansible-builder/backend
nohup uvicorn main:app --host 0.0.0.0 --port 8000 --reload > backend.log 2>&1 &
```

### Frontend 변경사항이 반영되지 않을 때
```bash
# 1. 재빌드
cd /root/ansible-builder/ansible-builder/frontend/frontend
npm run build

# 2. 브라우저에서 Ctrl+Shift+R (Hard Refresh)
```

### 포트 충돌 시
```bash
# 8000 포트 사용 중인 프로세스 종료
lsof -ti:8000 | xargs kill -9

# 8080 포트 확인
lsof -i:8080
```

---

## 📊 모니터링

### 실시간 로그
```bash
# Backend
tail -f /root/ansible-builder/ansible-builder/backend/backend.log

# Keycloak
docker logs -f keycloak

# AWX
kubectl logs -f deployment/awx-web -n awx
```

### 리소스 사용량
```bash
# CPU/메모리
top

# 디스크
df -h

# Backend 프로세스
ps aux | grep uvicorn | grep -v grep
```

---

## 💾 백업 및 복구

### 백업
```bash
# 전체 백업 (자동 스크립트)
/root/backup-ansible-builder.sh

# 수동 데이터베이스 백업
pg_dump -U ansible_builder -d ansible_builder > backup_$(date +%Y%m%d).sql
```

### 복구
```bash
# 데이터베이스 복구
psql -U ansible_builder -d ansible_builder < backup_20251211.sql
```

---

## 📝 자동 백업 설정

```bash
# Cron에 등록 (매일 새벽 2시)
(crontab -l 2>/dev/null; echo "0 2 * * * /root/backup-ansible-builder.sh >> /var/log/ansible-builder-backup.log 2>&1") | crontab -

# Cron 확인
crontab -l
```

---

## 📚 상세 문서

더 자세한 내용은 다음 문서를 참조하세요:
- **전체 운영 매뉴얼**: `/root/ansible-builder/ansible-builder/OPERATIONS_MANUAL.md`
- **Backend API 문서**: http://192.168.64.26:8000/docs

---

## 🆘 긴급 복구

모든 서비스가 작동하지 않을 때:

```bash
# 1. 전체 정지
/root/stop-all-services.sh

# 2. 2초 대기
sleep 2

# 3. 전체 시작
/root/start-all-services.sh

# 4. 상태 확인
/root/check-services.sh
```

---

**작성일**: 2025-12-11  
**버전**: 1.0
