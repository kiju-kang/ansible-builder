# Ansible Playbook Builder - 운영 매뉴얼 (Operations Manual)

## 목차 (Table of Contents)

1. [시스템 개요 (System Overview)](#시스템-개요)
2. [서비스 구성 (Service Architecture)](#서비스-구성)
3. [서비스 시작/정지 (Service Start/Stop)](#서비스-시작정지)
4. [서비스 모니터링 (Service Monitoring)](#서비스-모니터링)
5. [로그 확인 (Log Management)](#로그-확인)
6. [문제 해결 (Troubleshooting)](#문제-해결)
7. [백업 및 복구 (Backup & Recovery)](#백업-및-복구)
8. [설정 관리 (Configuration Management)](#설정-관리)

---

## 시스템 개요

### 전체 아키텍처
```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (React + Vite)                   │
│                  http://192.168.64.26:8000                   │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│               Backend (FastAPI + Uvicorn)                    │
│                     Port 8000                                │
└─────────┬────────────────────────────┬──────────────────────┘
          │                            │
┌─────────▼──────────┐    ┌───────────▼──────────────────────┐
│    PostgreSQL      │    │        Keycloak SSO              │
│   (Backend DB)     │    │  http://192.168.64.26:8080       │
│    Port 5432       │    │    (Docker Container)            │
└────────────────────┘    └───────────┬──────────────────────┘
                                      │
                         ┌────────────▼─────────────┐
                         │  Keycloak PostgreSQL     │
                         │   (Docker Container)     │
                         └──────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                    AWX (Kubernetes)                          │
│               http://192.168.64.26                           │
│  - awx-web: Frontend & API                                   │
│  - awx-task: Job executor                                    │
│  - awx-postgres: Database                                    │
└──────────────────────────────────────────────────────────────┘
```

### 주요 컴포넌트
- **Backend**: FastAPI/Uvicorn (Python 3.6)
- **Frontend**: React + Vite (정적 파일로 Backend에서 서빙)
- **Database**: PostgreSQL (Backend 데이터 저장)
- **SSO**: Keycloak (Docker로 실행)
- **Automation**: AWX (Kubernetes로 실행)

---

## 서비스 구성

### 1. Backend Service
- **위치**: `/root/ansible-builder/ansible-builder/backend/`
- **실행 방식**: Uvicorn (nohup으로 백그라운드 실행)
- **포트**: 8000
- **로그**: `/root/ansible-builder/ansible-builder/backend/backend.log`
- **PID 확인**: `ps aux | grep uvicorn`

### 2. Frontend
- **소스 위치**: `/root/ansible-builder/ansible-builder/frontend/frontend/`
- **빌드 산출물**: `/root/ansible-builder/ansible-builder/frontend/frontend/dist/`
- **서빙 방식**: Backend의 정적 파일 서빙 기능 사용

### 3. Keycloak (Docker)
- **컨테이너 이름**: `keycloak`, `keycloak-postgres`
- **포트**: 8080 (HTTP)
- **Admin Console**: http://192.168.64.26:8080
- **Realm**: master
- **Client ID**: ansible-builder

### 4. AWX (Kubernetes)
- **Namespace**: `awx`
- **Pods**:
  - `awx-web`: Web UI 및 API
  - `awx-task`: Job 실행
  - `awx-postgres`: 데이터베이스
- **URL**: http://192.168.64.26

### 5. PostgreSQL (Backend)
- **서비스**: systemd로 관리
- **포트**: 5432
- **데이터베이스**: `ansible_builder`
- **사용자**: `ansible_builder`

---

## 서비스 시작/정지

### 1. Backend 서비스

#### 시작 (Start)
```bash
# 방법 1: 백그라운드로 실행
cd /root/ansible-builder/ansible-builder/backend
nohup uvicorn main:app --host 0.0.0.0 --port 8000 --reload > backend.log 2>&1 &

# 방법 2: 로그 확인하며 실행
cd /root/ansible-builder/ansible-builder/backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 시작 확인
sleep 3
curl http://localhost:8000/docs
```

#### 정지 (Stop)
```bash
# 방법 1: 프로세스 이름으로 종료
pkill -f "uvicorn main:app"

# 방법 2: 포트로 프로세스 찾아서 종료
lsof -ti:8000 | xargs kill -9

# 종료 확인
ps aux | grep uvicorn | grep -v grep
```

#### 재시작 (Restart)
```bash
# 정지 후 시작
pkill -f "uvicorn main:app"
sleep 2
cd /root/ansible-builder/ansible-builder/backend
nohup uvicorn main:app --host 0.0.0.0 --port 8000 --reload > backend.log 2>&1 &
sleep 3
tail -f backend.log
```

#### 상태 확인 (Status)
```bash
# 프로세스 확인
ps aux | grep uvicorn | grep -v grep

# 포트 리스닝 확인
netstat -tlnp | grep 8000
# 또는
lsof -i:8000

# API 응답 확인
curl http://localhost:8000/health
curl http://localhost:8000/docs
```

---

### 2. Frontend 빌드 및 배포

#### 개발 모드 실행
```bash
cd /root/ansible-builder/ansible-builder/frontend/frontend
npm run dev
# 개발 서버: http://localhost:5173
```

#### 프로덕션 빌드
```bash
cd /root/ansible-builder/ansible-builder/frontend/frontend

# 빌드 실행
npm run build

# 빌드 결과 확인
ls -lh dist/

# 빌드 완료 후 Backend가 자동으로 dist/ 폴더를 서빙
```

#### 빌드 후 적용
```bash
# 1. Frontend 빌드
cd /root/ansible-builder/ansible-builder/frontend/frontend
npm run build

# 2. Backend 재시작 (선택사항 - 정적 파일은 자동 반영됨)
# Backend는 dist 폴더를 직접 읽으므로 재시작 불필요
# 단, 브라우저 캐시 클리어 필요: Ctrl+Shift+R (hard refresh)

# 3. 브라우저에서 확인
# http://192.168.64.26:8000
```

---

### 3. Keycloak (Docker)

#### 시작 (Start)
```bash
# 단일 컨테이너 시작
docker start keycloak
docker start keycloak-postgres

# 또는 docker-compose 사용 (compose 파일이 있는 경우)
cd /path/to/docker-compose
docker-compose up -d
```

#### 정지 (Stop)
```bash
# 컨테이너 정지
docker stop keycloak
docker stop keycloak-postgres

# 또는 docker-compose 사용
docker-compose down
```

#### 재시작 (Restart)
```bash
docker restart keycloak
docker restart keycloak-postgres
```

#### 상태 확인 (Status)
```bash
# 컨테이너 상태 확인
docker ps | grep keycloak

# 로그 확인
docker logs keycloak -f
docker logs keycloak-postgres -f

# Health 확인
curl http://192.168.64.26:8080/health
```

#### 로그인 정보
```
URL: http://192.168.64.26:8080
Username: admin
Password: admin
Realm: master
```

---

### 4. AWX (Kubernetes)

#### 시작 (Start)
```bash
# AWX pods 스케일 업
kubectl scale deployment awx-web --replicas=1 -n awx
kubectl scale deployment awx-task --replicas=1 -n awx

# 또는 전체 namespace 재시작
kubectl rollout restart deployment -n awx
```

#### 정지 (Stop)
```bash
# AWX pods 스케일 다운
kubectl scale deployment awx-web --replicas=0 -n awx
kubectl scale deployment awx-task --replicas=0 -n awx

# 주의: PostgreSQL StatefulSet은 유지하는 것을 권장
```

#### 재시작 (Restart)
```bash
# 전체 deployment 재시작
kubectl rollout restart deployment awx-web -n awx
kubectl rollout restart deployment awx-task -n awx

# Pod 강제 재시작
kubectl delete pod -l app.kubernetes.io/component=awx -n awx
```

#### 상태 확인 (Status)
```bash
# Pod 상태 확인
kubectl get pods -n awx

# 상세 상태
kubectl get pods -n awx -o wide

# Pod 로그 확인
kubectl logs -f deployment/awx-web -n awx
kubectl logs -f deployment/awx-task -n awx

# Service 확인
kubectl get svc -n awx

# Health 확인
curl http://192.168.64.26/api/v2/ping/
```

---

### 5. PostgreSQL (Backend Database)

#### 시작/정지/재시작 (Start/Stop/Restart)
```bash
# 시작
systemctl start postgresql

# 정지
systemctl stop postgresql

# 재시작
systemctl restart postgresql

# 상태 확인
systemctl status postgresql
```

#### 데이터베이스 접속
```bash
# Backend 데이터베이스 접속
psql -U ansible_builder -d ansible_builder

# 또는 postgres 사용자로 접속
sudo -u postgres psql

# 데이터베이스 목록
\l

# 테이블 목록
\dt

# 종료
\q
```

---

## 서비스 모니터링

### 1. 전체 서비스 상태 확인 스크립트

```bash
#!/bin/bash
echo "==================================="
echo "Ansible Builder 서비스 상태 확인"
echo "==================================="
echo ""

echo "1. Backend Service (Port 8000)"
if ps aux | grep -v grep | grep "uvicorn main:app" > /dev/null; then
    echo "   ✅ Running"
    ps aux | grep -v grep | grep "uvicorn main:app" | awk '{print "   PID: "$2", CPU: "$3"%, MEM: "$4"%"}'
else
    echo "   ❌ Not Running"
fi
echo ""

echo "2. Keycloak (Docker)"
docker ps --filter name=keycloak --format "   {{.Names}}: {{.Status}}"
echo ""

echo "3. AWX (Kubernetes)"
kubectl get pods -n awx --no-headers | awk '{print "   "$1": "$3}'
echo ""

echo "4. PostgreSQL"
if systemctl is-active postgresql > /dev/null 2>&1; then
    echo "   ✅ Running"
else
    echo "   ❌ Not Running"
fi
echo ""

echo "5. Port Status"
echo "   Port 8000 (Backend): $(netstat -tln | grep :8000 > /dev/null && echo '✅ Listening' || echo '❌ Not Listening')"
echo "   Port 8080 (Keycloak): $(netstat -tln | grep :8080 > /dev/null && echo '✅ Listening' || echo '❌ Not Listening')"
echo "   Port 5432 (PostgreSQL): $(netstat -tln | grep :5432 > /dev/null && echo '✅ Listening' || echo '❌ Not Listening')"
echo ""
```

이 스크립트를 `/root/check-services.sh`로 저장하고 실행:
```bash
chmod +x /root/check-services.sh
/root/check-services.sh
```

### 2. 리소스 모니터링

#### CPU 및 메모리 사용량
```bash
# 전체 시스템 리소스
top -b -n 1 | head -20

# Backend 프로세스
ps aux | grep uvicorn | grep -v grep

# Docker 컨테이너
docker stats --no-stream keycloak keycloak-postgres

# Kubernetes Pods
kubectl top pods -n awx
```

#### 디스크 사용량
```bash
# 전체 디스크
df -h

# Backend 디렉토리
du -sh /root/ansible-builder/ansible-builder/backend/

# Frontend 빌드
du -sh /root/ansible-builder/ansible-builder/frontend/frontend/dist/

# 데이터베이스
du -sh /var/lib/pgsql/
```

#### 네트워크 연결
```bash
# 포트 리스닝 상태
netstat -tlnp | grep -E "8000|8080|5432"

# Backend 활성 연결
netstat -an | grep :8000 | grep ESTABLISHED | wc -l

# Keycloak 활성 연결
netstat -an | grep :8080 | grep ESTABLISHED | wc -l
```

---

## 로그 확인

### 1. Backend 로그

#### 실시간 로그
```bash
# 전체 로그
tail -f /root/ansible-builder/ansible-builder/backend/backend.log

# 에러만 필터링
tail -f /root/ansible-builder/ansible-builder/backend/backend.log | grep ERROR

# 특정 패턴 검색
tail -f /root/ansible-builder/ansible-builder/backend/backend.log | grep -E "ERROR|WARNING"
```

#### 로그 분석
```bash
# 최근 100줄
tail -100 /root/ansible-builder/ansible-builder/backend/backend.log

# 에러 카운트
grep ERROR /root/ansible-builder/ansible-builder/backend/backend.log | wc -l

# 특정 날짜 로그
grep "2025-12-11" /root/ansible-builder/ansible-builder/backend/backend.log

# 로그 크기 확인
ls -lh /root/ansible-builder/ansible-builder/backend/backend.log
```

#### 로그 로테이션
```bash
# 로그 백업 및 새 파일로 교체
cd /root/ansible-builder/ansible-builder/backend
mv backend.log backend.log.$(date +%Y%m%d_%H%M%S)
touch backend.log

# Backend 재시작 (새 로그 파일 사용)
pkill -f "uvicorn main:app"
sleep 2
nohup uvicorn main:app --host 0.0.0.0 --port 8000 --reload > backend.log 2>&1 &
```

### 2. Keycloak 로그

```bash
# Docker 로그
docker logs keycloak -f

# 최근 100줄
docker logs keycloak --tail 100

# 특정 시간 이후
docker logs keycloak --since 1h

# 로그 저장
docker logs keycloak > keycloak.log 2>&1
```

### 3. AWX 로그

```bash
# Web pod 로그
kubectl logs -f deployment/awx-web -n awx

# Task pod 로그
kubectl logs -f deployment/awx-task -n awx

# 특정 pod 로그
kubectl logs -f awx-web-788c895fbf-g98fz -n awx

# 이전 컨테이너 로그 (crash 시)
kubectl logs awx-web-788c895fbf-g98fz -n awx --previous

# 모든 pod 로그
kubectl logs -l app.kubernetes.io/name=awx -n awx
```

### 4. PostgreSQL 로그

```bash
# PostgreSQL 로그 위치 확인
psql -U postgres -c "SHOW log_directory;"
psql -U postgres -c "SHOW log_filename;"

# 일반적인 로그 위치
tail -f /var/lib/pgsql/data/log/postgresql-*.log

# 또는 systemd 로그
journalctl -u postgresql -f
```

---

## 문제 해결

### 1. Backend 문제

#### 문제: Backend가 시작되지 않음
```bash
# 원인 1: 포트 이미 사용 중
lsof -i:8000
# 해결: 기존 프로세스 종료
lsof -ti:8000 | xargs kill -9

# 원인 2: Python 모듈 누락
cd /root/ansible-builder/ansible-builder/backend
python3 -c "import fastapi, uvicorn, sqlalchemy, jwt"
# 해결: 모듈 설치
pip3 install fastapi uvicorn sqlalchemy python-jose[cryptography] passlib[bcrypt]

# 원인 3: 데이터베이스 연결 실패
psql -U ansible_builder -d ansible_builder
# 해결: 데이터베이스 및 사용자 생성
sudo -u postgres psql
CREATE DATABASE ansible_builder;
CREATE USER ansible_builder WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE ansible_builder TO ansible_builder;
```

#### 문제: API 응답 느림
```bash
# DB 연결 확인
psql -U ansible_builder -d ansible_builder -c "SELECT count(*) FROM playbooks;"

# 실행 중인 쿼리 확인
psql -U ansible_builder -d ansible_builder -c "SELECT pid, query, state FROM pg_stat_activity WHERE state = 'active';"

# 로그에서 느린 쿼리 확인
grep "slow" /root/ansible-builder/ansible-builder/backend/backend.log
```

#### 문제: 인증 실패
```bash
# Keycloak 연결 확인
curl http://192.168.64.26:8080/health

# 토큰 발급 테스트
curl -X POST http://192.168.64.26:8080/realms/master/protocol/openid-connect/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin" \
  -d "password=admin" \
  -d "grant_type=password" \
  -d "client_id=ansible-builder"

# Backend 환경변수 확인
grep -E "KEYCLOAK|CLIENT" /root/ansible-builder/ansible-builder/backend/main.py | head -20
```

### 2. Frontend 문제

#### 문제: 변경사항이 반영되지 않음
```bash
# 해결 1: Frontend 재빌드
cd /root/ansible-builder/ansible-builder/frontend/frontend
npm run build

# 해결 2: 브라우저 캐시 클리어
# Chrome/Edge: Ctrl+Shift+R
# Firefox: Ctrl+F5

# 해결 3: dist 폴더 확인
ls -lh /root/ansible-builder/ansible-builder/frontend/frontend/dist/
```

#### 문제: 빌드 실패
```bash
# Node modules 재설치
cd /root/ansible-builder/ansible-builder/frontend/frontend
rm -rf node_modules package-lock.json
npm install

# 빌드 재시도
npm run build

# 빌드 로그 확인
npm run build > build.log 2>&1
cat build.log
```

### 3. Keycloak 문제

#### 문제: Keycloak 접속 불가
```bash
# 컨테이너 상태 확인
docker ps -a | grep keycloak

# 컨테이너 재시작
docker restart keycloak

# 포트 확인
netstat -tlnp | grep 8080

# 로그 확인
docker logs keycloak --tail 50
```

#### 문제: 인증 리디렉션 에러
```bash
# Valid Redirect URIs 확인 및 수정
# 1. Keycloak Admin Console 접속
# 2. Clients > ansible-builder > Valid Redirect URIs
# 3. 추가: http://192.168.64.26:8000/*

# 또는 스크립트로 수정 (setup-keycloak.sh 재실행)
cd /root/ansible-builder/ansible-builder/backend
./setup-keycloak.sh
```

### 4. AWX 문제

#### 문제: AWX Pod가 시작되지 않음
```bash
# Pod 상태 확인
kubectl get pods -n awx

# Pod 상세 정보
kubectl describe pod <pod-name> -n awx

# 이벤트 확인
kubectl get events -n awx --sort-by='.lastTimestamp'

# Pod 재생성
kubectl delete pod <pod-name> -n awx
```

#### 문제: AWX Job 실행 실패
```bash
# Task pod 로그 확인
kubectl logs -f deployment/awx-task -n awx

# Job 상태 확인 (AWX UI)
# http://192.168.64.26/#/jobs

# Database 확인
kubectl exec -it awx-postgres-15-0 -n awx -- psql -U awx -c "SELECT id, name, status FROM main_job ORDER BY id DESC LIMIT 10;"
```

### 5. Database 문제

#### 문제: 연결 실패
```bash
# PostgreSQL 상태 확인
systemctl status postgresql

# 연결 테스트
psql -U ansible_builder -d ansible_builder -c "SELECT 1;"

# pg_hba.conf 확인 (인증 설정)
cat /var/lib/pgsql/data/pg_hba.conf

# postgresql.conf 확인 (listen_addresses)
grep listen_addresses /var/lib/pgsql/data/postgresql.conf
```

#### 문제: 디스크 공간 부족
```bash
# 데이터베이스 크기 확인
psql -U postgres -c "SELECT pg_size_pretty(pg_database_size('ansible_builder'));"

# 오래된 데이터 정리
psql -U ansible_builder -d ansible_builder
DELETE FROM playbooks WHERE created_at < NOW() - INTERVAL '30 days';
VACUUM FULL;

# WAL 로그 정리
psql -U postgres -c "SELECT pg_ls_waldir();"
```

---

## 백업 및 복구

### 1. Backend Database 백업

#### 전체 백업
```bash
# 백업 디렉토리 생성
mkdir -p /root/backups/ansible-builder

# 데이터베이스 덤프
pg_dump -U ansible_builder -d ansible_builder -F c -f /root/backups/ansible-builder/backup_$(date +%Y%m%d_%H%M%S).dump

# 또는 SQL 형식
pg_dump -U ansible_builder -d ansible_builder > /root/backups/ansible-builder/backup_$(date +%Y%m%d_%H%M%S).sql
```

#### 특정 테이블만 백업
```bash
# playbooks 테이블만 백업
pg_dump -U ansible_builder -d ansible_builder -t playbooks > /root/backups/ansible-builder/playbooks_$(date +%Y%m%d_%H%M%S).sql
```

#### 자동 백업 스크립트
```bash
cat > /root/backup-ansible-builder.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/root/backups/ansible-builder"
DATE=$(date +%Y%m%d_%H%M%S)
KEEP_DAYS=7

# 백업 디렉토리 생성
mkdir -p $BACKUP_DIR

# 데이터베이스 백업
pg_dump -U ansible_builder -d ansible_builder -F c -f $BACKUP_DIR/backup_$DATE.dump

# 오래된 백업 삭제 (7일 이상)
find $BACKUP_DIR -name "backup_*.dump" -mtime +$KEEP_DAYS -delete

echo "Backup completed: $BACKUP_DIR/backup_$DATE.dump"
EOF

chmod +x /root/backup-ansible-builder.sh
```

#### Cron 등록 (매일 새벽 2시)
```bash
(crontab -l 2>/dev/null; echo "0 2 * * * /root/backup-ansible-builder.sh >> /var/log/ansible-builder-backup.log 2>&1") | crontab -
```

### 2. Database 복구

#### 전체 복구
```bash
# 복구 전 기존 데이터베이스 삭제 (주의!)
sudo -u postgres psql << EOF
DROP DATABASE IF EXISTS ansible_builder;
CREATE DATABASE ansible_builder OWNER ansible_builder;
EOF

# Custom 형식 복구
pg_restore -U ansible_builder -d ansible_builder /root/backups/ansible-builder/backup_20251211_020000.dump

# SQL 형식 복구
psql -U ansible_builder -d ansible_builder < /root/backups/ansible-builder/backup_20251211_020000.sql
```

#### 특정 테이블만 복구
```bash
# playbooks 테이블만 복구
psql -U ansible_builder -d ansible_builder < /root/backups/ansible-builder/playbooks_20251211_020000.sql
```

### 3. Backend 코드 백업

```bash
# 전체 백업
tar -czf /root/backups/ansible-builder-code_$(date +%Y%m%d_%H%M%S).tar.gz \
  /root/ansible-builder/ansible-builder/backend/ \
  /root/ansible-builder/ansible-builder/frontend/

# 복구
tar -xzf /root/backups/ansible-builder-code_20251211_020000.tar.gz -C /
```

### 4. Keycloak 백업

```bash
# Keycloak 설정 export
docker exec keycloak /opt/keycloak/bin/kc.sh export \
  --dir /tmp/keycloak-export \
  --realm master

# 파일 복사
docker cp keycloak:/tmp/keycloak-export /root/backups/keycloak-export_$(date +%Y%m%d_%H%M%S)

# Keycloak 데이터베이스 백업
docker exec keycloak-postgres pg_dump -U keycloak keycloak > /root/backups/keycloak-db_$(date +%Y%m%d_%H%M%S).sql
```

### 5. AWX 백업

```bash
# AWX 설정 백업 (Kubernetes manifests)
kubectl get all -n awx -o yaml > /root/backups/awx-manifests_$(date +%Y%m%d_%H%M%S).yaml

# AWX 데이터베이스 백업
kubectl exec -it awx-postgres-15-0 -n awx -- pg_dump -U awx awx > /root/backups/awx-db_$(date +%Y%m%d_%H%M%S).sql
```

---

## 설정 관리

### 1. Backend 설정

#### 주요 설정 파일
- **main.py**: `/root/ansible-builder/ansible-builder/backend/main.py`
- **데이터베이스 URL**: `DATABASE_URL = "postgresql://ansible_builder:password@localhost/ansible_builder"`
- **Keycloak 설정**:
  ```python
  KEYCLOAK_URL = "http://192.168.64.26:8080"
  KEYCLOAK_REALM = "master"
  KEYCLOAK_CLIENT_ID = "ansible-builder"
  ```
- **AWX 설정**:
  ```python
  AWX_URL = "http://192.168.64.26"
  ```

#### 환경변수 설정
```bash
# .env 파일 생성 (선택사항)
cat > /root/ansible-builder/ansible-builder/backend/.env << EOF
DATABASE_URL=postgresql://ansible_builder:password@localhost/ansible_builder
KEYCLOAK_URL=http://192.168.64.26:8080
KEYCLOAK_REALM=master
KEYCLOAK_CLIENT_ID=ansible-builder
AWX_URL=http://192.168.64.26
SECRET_KEY=your-secret-key-here
EOF
```

### 2. Frontend 설정

#### Vite 설정
- **파일**: `/root/ansible-builder/ansible-builder/frontend/frontend/vite.config.js`
- **빌드 출력**: `dist/`
- **개발 서버**: Port 5173

#### API Endpoint 설정
- **파일**: `/root/ansible-builder/ansible-builder/frontend/frontend/src/config.js` (있는 경우)
- Frontend는 Backend와 동일한 origin을 사용하므로 별도 설정 불필요

### 3. Keycloak 설정

#### Client 설정
```bash
# Admin Console: http://192.168.64.26:8080
# Realm: master
# Client: ansible-builder

# Valid Redirect URIs
http://192.168.64.26:8000/*
http://localhost:8000/*

# Web Origins
http://192.168.64.26:8000
http://localhost:8000
```

#### Realm 설정 Export
```bash
docker exec keycloak /opt/keycloak/bin/kc.sh export \
  --dir /tmp/keycloak-config \
  --realm master

docker cp keycloak:/tmp/keycloak-config /root/keycloak-config
```

### 4. AWX 설정

#### OAuth2 Application 설정
```python
# AWX Admin > Applications > ansible-builder-oauth
Name: ansible-builder-oauth
Organization: Default
Authorization Grant Type: Resource owner password-based
Client Type: Public
Redirect URIs: http://192.168.64.26:8000/callback (필요시)
```

#### AWX 환경변수
```bash
# AWX pod 환경변수 확인
kubectl exec -it awx-web-<pod-id> -n awx -- env | grep AWX
```

### 5. PostgreSQL 설정

#### postgresql.conf 주요 설정
```bash
# 파일 위치: /var/lib/pgsql/data/postgresql.conf

# 연결 설정
listen_addresses = 'localhost'  # 또는 '*'
port = 5432
max_connections = 100

# 메모리 설정
shared_buffers = 128MB
work_mem = 4MB

# 로그 설정
log_destination = 'stderr'
logging_collector = on
log_directory = 'log'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '
```

#### pg_hba.conf 설정
```bash
# 파일 위치: /var/lib/pgsql/data/pg_hba.conf

# Local connections
local   all             all                                     peer

# IPv4 local connections
host    all             all             127.0.0.1/32            md5
host    ansible_builder ansible_builder 127.0.0.1/32            md5

# IPv6 local connections
host    all             all             ::1/128                 md5
```

---

## 전체 서비스 시작/정지 스크립트

### 전체 시작 스크립트

```bash
cat > /root/start-all-services.sh << 'EOF'
#!/bin/bash
set -e

echo "====================================="
echo "모든 서비스 시작 중..."
echo "====================================="
echo ""

# 1. PostgreSQL 시작
echo "1. PostgreSQL 시작 중..."
systemctl start postgresql
sleep 2
systemctl status postgresql --no-pager | head -5
echo ""

# 2. Keycloak 시작
echo "2. Keycloak 시작 중..."
docker start keycloak-postgres
sleep 5
docker start keycloak
sleep 10
docker ps | grep keycloak
echo ""

# 3. AWX 시작
echo "3. AWX 시작 중..."
kubectl scale deployment awx-web --replicas=1 -n awx
kubectl scale deployment awx-task --replicas=1 -n awx
echo "AWX pods 시작 대기 중..."
kubectl wait --for=condition=ready pod -l app.kubernetes.io/component=awx -n awx --timeout=120s
kubectl get pods -n awx
echo ""

# 4. Backend 시작
echo "4. Backend 시작 중..."
cd /root/ansible-builder/ansible-builder/backend
# 기존 프로세스 종료
pkill -f "uvicorn main:app" || true
sleep 2
# 새로 시작
nohup uvicorn main:app --host 0.0.0.0 --port 8000 --reload > backend.log 2>&1 &
sleep 5
echo ""

# 5. 상태 확인
echo "====================================="
echo "서비스 상태 확인"
echo "====================================="
echo ""

echo "Backend (Port 8000):"
if curl -s http://localhost:8000/docs > /dev/null; then
    echo "  ✅ Running"
else
    echo "  ❌ Not responding"
fi
echo ""

echo "Keycloak (Port 8080):"
if curl -s http://localhost:8080/health > /dev/null; then
    echo "  ✅ Running"
else
    echo "  ⚠️  Starting... (may take a minute)"
fi
echo ""

echo "AWX Pods:"
kubectl get pods -n awx --no-headers | awk '{print "  "$1": "$3}'
echo ""

echo "====================================="
echo "모든 서비스 시작 완료!"
echo "====================================="
echo ""
echo "접속 URL:"
echo "  - Ansible Builder: http://192.168.64.26:8000"
echo "  - Keycloak Admin: http://192.168.64.26:8080"
echo "  - AWX: http://192.168.64.26"
echo ""
EOF

chmod +x /root/start-all-services.sh
```

### 전체 정지 스크립트

```bash
cat > /root/stop-all-services.sh << 'EOF'
#!/bin/bash

echo "====================================="
echo "모든 서비스 정지 중..."
echo "====================================="
echo ""

# 1. Backend 정지
echo "1. Backend 정지 중..."
pkill -f "uvicorn main:app" || true
sleep 2
echo "  ✅ Backend 정지 완료"
echo ""

# 2. AWX 정지
echo "2. AWX 정지 중..."
kubectl scale deployment awx-web --replicas=0 -n awx
kubectl scale deployment awx-task --replicas=0 -n awx
sleep 5
echo "  ✅ AWX 정지 완료"
kubectl get pods -n awx
echo ""

# 3. Keycloak 정지
echo "3. Keycloak 정지 중..."
docker stop keycloak
docker stop keycloak-postgres
echo "  ✅ Keycloak 정지 완료"
echo ""

# 4. PostgreSQL 정지 (선택사항 - 주석 처리됨)
# echo "4. PostgreSQL 정지 중..."
# systemctl stop postgresql
# echo "  ✅ PostgreSQL 정지 완료"
# echo ""

echo "====================================="
echo "모든 서비스 정지 완료!"
echo "====================================="
echo ""
echo "참고: PostgreSQL은 계속 실행 중입니다."
echo "PostgreSQL도 정지하려면 스크립트의 주석을 해제하세요."
echo ""
EOF

chmod +x /root/stop-all-services.sh
```

### 상태 확인 스크립트

```bash
cat > /root/check-services.sh << 'EOF'
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

# 4. PostgreSQL
echo "4. PostgreSQL"
if systemctl is-active postgresql > /dev/null 2>&1; then
    echo "   ✅ Running"
    psql -U ansible_builder -d ansible_builder -c "SELECT count(*) as playbook_count FROM playbooks;" 2>/dev/null | grep -A 1 playbook_count | tail -1 | awk '{print "   Playbooks in DB: "$1}'
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
EOF

chmod +x /root/check-services.sh
```

---

## 빠른 명령어 참조 (Quick Reference)

### Backend
```bash
# 시작
cd /root/ansible-builder/ansible-builder/backend && nohup uvicorn main:app --host 0.0.0.0 --port 8000 --reload > backend.log 2>&1 &

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
cd /root/ansible-builder/ansible-builder/frontend/frontend && npm run build

# 개발 모드
npm run dev
```

### Keycloak
```bash
# 시작
docker start keycloak-postgres && docker start keycloak

# 정지
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

### PostgreSQL
```bash
# 시작/정지/재시작
systemctl start/stop/restart postgresql

# 접속
psql -U ansible_builder -d ansible_builder

# 백업
pg_dump -U ansible_builder -d ansible_builder > backup.sql
```

---

## 연락처 및 지원

### 로그 위치 요약
- Backend: `/root/ansible-builder/ansible-builder/backend/backend.log`
- Keycloak: `docker logs keycloak`
- AWX: `kubectl logs -n awx <pod-name>`
- PostgreSQL: `/var/lib/pgsql/data/log/`

### 주요 URL
- **Ansible Builder**: http://192.168.64.26:8000
- **Keycloak Admin**: http://192.168.64.26:8080
- **AWX**: http://192.168.64.26
- **Backend API Docs**: http://192.168.64.26:8000/docs

### 문서 버전
- 작성일: 2025-12-11
- 버전: 1.0
- 마지막 업데이트: 2025-12-11

---

## 부록

### A. 시스템 요구사항
- OS: RHEL/CentOS 8+
- Python: 3.6+
- Node.js: 14+
- Docker: 20.10+
- Kubernetes: 1.20+
- PostgreSQL: 12+

### B. 포트 목록
- 8000: Backend (FastAPI)
- 8080: Keycloak
- 5432: PostgreSQL
- 5173: Frontend Dev Server (개발 시에만)

### C. 디렉토리 구조
```
/root/ansible-builder/
└── ansible-builder/
    ├── backend/
    │   ├── main.py
    │   ├── backend.log
    │   ├── ansible_builder.db (SQLite 사용 시)
    │   └── playbooks/ (생성된 playbook 파일들)
    └── frontend/
        └── frontend/
            ├── src/
            ├── dist/ (빌드 결과)
            └── package.json
```

### D. 추가 리소스
- FastAPI 문서: https://fastapi.tiangolo.com/
- React 문서: https://react.dev/
- Keycloak 문서: https://www.keycloak.org/documentation
- AWX 문서: https://github.com/ansible/awx
- Ansible 문서: https://docs.ansible.com/

---

**끝 (End of Document)**
