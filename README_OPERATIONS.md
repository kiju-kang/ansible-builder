# Ansible Playbook Builder - 운영 문서 완성

## 📁 생성된 문서 및 스크립트

### 📚 문서
1. **[OPERATIONS_MANUAL.md](/root/ansible-builder/ansible-builder/OPERATIONS_MANUAL.md)**
   - 전체 운영 매뉴얼 (한글)
   - 시스템 아키텍처 설명
   - 모든 서비스의 상세 시작/정지 절차
   - 모니터링 및 로그 관리
   - 문제 해결 가이드
   - 백업 및 복구 절차
   - 설정 관리

2. **[QUICK_START.md](/root/QUICK_START.md)**
   - 빠른 시작 가이드
   - 자주 사용하는 명령어 모음
   - 접속 URL 및 계정 정보
   - 긴급 복구 절차

### 🔧 운영 스크립트

3. **[/root/start-all-services.sh](/root/start-all-services.sh)**
   - 전체 서비스 자동 시작 스크립트
   - PostgreSQL → Keycloak → AWX → Backend 순서로 시작
   - 각 서비스 시작 후 상태 확인
   - 사용법: `/root/start-all-services.sh`

4. **[/root/stop-all-services.sh](/root/stop-all-services.sh)**
   - 전체 서비스 자동 정지 스크립트
   - Backend → AWX → Keycloak 순서로 정지
   - PostgreSQL은 기본적으로 유지 (주석 해제 가능)
   - 사용법: `/root/stop-all-services.sh`

5. **[/root/check-services.sh](/root/check-services.sh)**
   - 전체 서비스 상태 확인 스크립트
   - 각 서비스의 실행 상태, 포트, API 응답 확인
   - 디스크 사용량 및 최근 에러 확인
   - 사용법: `/root/check-services.sh`

6. **[/root/backup-ansible-builder.sh](/root/backup-ansible-builder.sh)**
   - 자동 백업 스크립트
   - 데이터베이스, Backend, Frontend 코드 백업
   - 7일 이상 오래된 백업 자동 삭제
   - 백업 위치: `/root/backups/ansible-builder/`
   - 사용법: `/root/backup-ansible-builder.sh`

---

## 🚀 빠른 사용 방법

### 서비스 관리

```bash
# 전체 시작
/root/start-all-services.sh

# 전체 정지
/root/stop-all-services.sh

# 상태 확인
/root/check-services.sh

# 백업 실행
/root/backup-ansible-builder.sh
```

### 접속 정보

| 서비스 | URL | 계정 |
|--------|-----|------|
| Ansible Builder | http://192.168.64.26:8000 | Keycloak SSO |
| Keycloak Admin | http://192.168.64.26:8080 | admin / admin |
| AWX | http://192.168.64.26 | admin / password |
| Backend API Docs | http://192.168.64.26:8000/docs | - |

---

## 📊 시스템 현황

### 서비스 구성
```
┌─────────────────────────────────────────────────────────┐
│             Frontend (React + Vite)                     │
│           http://192.168.64.26:8000                     │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│          Backend (FastAPI + Uvicorn)                    │
│                  Port 8000                              │
└─────────┬──────────────────────┬────────────────────────┘
          │                      │
┌─────────▼──────────┐  ┌───────▼─────────────────────────┐
│   PostgreSQL       │  │     Keycloak SSO                │
│   (Backend DB)     │  │  http://192.168.64.26:8080      │
│   Port 5432        │  │   (Docker Container)            │
└────────────────────┘  └──────────┬──────────────────────┘
                                   │
                      ┌────────────▼──────────┐
                      │ Keycloak PostgreSQL   │
                      │  (Docker Container)   │
                      └───────────────────────┘

┌─────────────────────────────────────────────────────────┐
│              AWX (Kubernetes)                           │
│          http://192.168.64.26                           │
│  - awx-web: Frontend & API                              │
│  - awx-task: Job executor                               │
│  - awx-postgres: Database                               │
└─────────────────────────────────────────────────────────┘
```

### 현재 상태 (2025-12-11 15:43)
- ✅ Backend: Running (Port 8000)
- ✅ Keycloak: Running (Port 8080, Docker)
- ✅ AWX: Running (Kubernetes)
- ✅ PostgreSQL: Running (multiple instances)

---

## 🔧 개별 서비스 관리

### Backend
```bash
# 시작
cd /root/ansible-builder/ansible-builder/backend
nohup uvicorn main:app --host 0.0.0.0 --port 8000 --reload > backend.log 2>&1 &

# 정지
pkill -f "uvicorn main:app"

# 로그
tail -f /root/ansible-builder/ansible-builder/backend/backend.log
```

### Keycloak (Docker)
```bash
# 시작
docker start keycloak-postgres keycloak

# 정지
docker stop keycloak keycloak-postgres

# 로그
docker logs -f keycloak
```

### AWX (Kubernetes)
```bash
# 상태 확인
kubectl get pods -n awx

# 로그
kubectl logs -f deployment/awx-web -n awx

# 재시작
kubectl rollout restart deployment -n awx
```

---

## 💾 백업 관리

### 수동 백업
```bash
/root/backup-ansible-builder.sh
```

### 자동 백업 설정 (Cron)
```bash
# 매일 새벽 2시 자동 백업
(crontab -l 2>/dev/null; echo "0 2 * * * /root/backup-ansible-builder.sh >> /var/log/ansible-builder-backup.log 2>&1") | crontab -

# Cron 확인
crontab -l
```

### 백업 위치
```
/root/backups/ansible-builder/
├── backup_YYYYMMDD_HHMMSS.dump      (데이터베이스)
├── backend_YYYYMMDD_HHMMSS.tar.gz   (Backend 코드)
└── frontend_YYYYMMDD_HHMMSS.tar.gz  (Frontend 코드)
```

### 복구
```bash
# 데이터베이스 복구
pg_restore -U ansible_builder -d ansible_builder /root/backups/ansible-builder/backup_20251211_020000.dump

# 코드 복구
tar -xzf /root/backups/ansible-builder/backend_20251211_020000.tar.gz -C /root/ansible-builder/ansible-builder/
```

---

## 🐛 문제 해결

### Backend 응답 없음
```bash
# 로그 확인
tail -f /root/ansible-builder/ansible-builder/backend/backend.log

# 재시작
pkill -f "uvicorn main:app"
sleep 2
cd /root/ansible-builder/ansible-builder/backend
nohup uvicorn main:app --host 0.0.0.0 --port 8000 --reload > backend.log 2>&1 &
```

### Frontend 변경사항 미반영
```bash
# 재빌드
cd /root/ansible-builder/ansible-builder/frontend/frontend
npm run build

# 브라우저 캐시 클리어: Ctrl+Shift+R
```

### 전체 서비스 재시작
```bash
/root/stop-all-services.sh
sleep 2
/root/start-all-services.sh
```

---

## 📈 모니터링

### 로그 모니터링
```bash
# Backend 실시간 로그
tail -f /root/ansible-builder/ansible-builder/backend/backend.log

# Keycloak 실시간 로그
docker logs -f keycloak

# AWX 실시간 로그
kubectl logs -f deployment/awx-web -n awx
```

### 리소스 모니터링
```bash
# CPU/메모리
top

# 디스크
df -h

# Backend 프로세스
ps aux | grep uvicorn | grep -v grep

# Docker 컨테이너
docker stats --no-stream

# Kubernetes Pods
kubectl top pods -n awx
```

---

## 📚 추가 리소스

### 문서
- **전체 운영 매뉴얼**: `/root/ansible-builder/ansible-builder/OPERATIONS_MANUAL.md`
- **빠른 시작 가이드**: `/root/QUICK_START.md`
- **Backend API 문서**: http://192.168.64.26:8000/docs

### 주요 디렉토리
```
/root/ansible-builder/ansible-builder/
├── backend/
│   ├── main.py (FastAPI 애플리케이션)
│   ├── backend.log (로그 파일)
│   └── playbooks/ (생성된 playbook 파일들)
└── frontend/
    └── frontend/
        ├── src/ (소스 코드)
        ├── dist/ (빌드 결과)
        └── package.json
```

### 로그 파일 위치
- Backend: `/root/ansible-builder/ansible-builder/backend/backend.log`
- Keycloak: `docker logs keycloak`
- AWX: `kubectl logs -n awx <pod-name>`
- PostgreSQL: `/var/lib/pgsql/data/log/`

---

## ✅ 완료 항목

### 문서 작성 완료
- ✅ 전체 운영 매뉴얼 작성 (한글)
- ✅ 빠른 시작 가이드 작성
- ✅ 시스템 아키텍처 문서화
- ✅ 서비스 시작/정지 절차 문서화
- ✅ 모니터링 방법 문서화
- ✅ 문제 해결 가이드 작성
- ✅ 백업/복구 절차 문서화

### 스크립트 작성 완료
- ✅ 전체 서비스 시작 스크립트
- ✅ 전체 서비스 정지 스크립트
- ✅ 서비스 상태 확인 스크립트
- ✅ 자동 백업 스크립트

### 테스트 완료
- ✅ 상태 확인 스크립트 동작 검증
- ✅ 모든 서비스 정상 작동 확인
- ✅ Backend API 응답 확인
- ✅ Keycloak API 응답 확인

---

## 🎯 다음 단계 (권장)

### 1. 자동 백업 설정
```bash
# Cron에 백업 작업 등록
(crontab -l 2>/dev/null; echo "0 2 * * * /root/backup-ansible-builder.sh >> /var/log/ansible-builder-backup.log 2>&1") | crontab -
```

### 2. 로그 로테이션 설정
```bash
# logrotate 설정 생성
cat > /etc/logrotate.d/ansible-builder << 'LOGROTATE'
/root/ansible-builder/ansible-builder/backend/backend.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 root root
}
LOGROTATE
```

### 3. 시스템 모니터링 도구 설치 (선택사항)
```bash
# Prometheus, Grafana 등의 모니터링 도구 고려
```

---

**작성일**: 2025-12-11  
**작성자**: Claude  
**버전**: 1.0

**문의 및 지원**: 
- Backend API 문서: http://192.168.64.26:8000/docs
- 운영 매뉴얼: `/root/ansible-builder/ansible-builder/OPERATIONS_MANUAL.md`
