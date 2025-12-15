#!/bin/bash
BACKUP_DIR="/root/backups/ansible-builder"
DATE=$(date +%Y%m%d_%H%M%S)
KEEP_DAYS=7

# 백업 디렉토리 생성
mkdir -p $BACKUP_DIR

echo "====================================="
echo "Ansible Builder 백업 시작"
echo "====================================="
echo "시간: $(date)"
echo ""

# 1. 데이터베이스 백업
echo "1. 데이터베이스 백업 중..."
pg_dump -U ansible_builder -d ansible_builder -F c -f $BACKUP_DIR/backup_$DATE.dump
if [ $? -eq 0 ]; then
    echo "  ✅ 데이터베이스 백업 완료: $BACKUP_DIR/backup_$DATE.dump"
    ls -lh $BACKUP_DIR/backup_$DATE.dump
else
    echo "  ❌ 데이터베이스 백업 실패"
    exit 1
fi
echo ""

# 2. Backend 코드 백업
echo "2. Backend 코드 백업 중..."
tar -czf $BACKUP_DIR/backend_$DATE.tar.gz -C /root/ansible-builder/ansible-builder backend/
if [ $? -eq 0 ]; then
    echo "  ✅ Backend 백업 완료: $BACKUP_DIR/backend_$DATE.tar.gz"
    ls -lh $BACKUP_DIR/backend_$DATE.tar.gz
else
    echo "  ❌ Backend 백업 실패"
fi
echo ""

# 3. Frontend 코드 백업
echo "3. Frontend 코드 백업 중..."
tar -czf $BACKUP_DIR/frontend_$DATE.tar.gz -C /root/ansible-builder/ansible-builder frontend/
if [ $? -eq 0 ]; then
    echo "  ✅ Frontend 백업 완료: $BACKUP_DIR/frontend_$DATE.tar.gz"
    ls -lh $BACKUP_DIR/frontend_$DATE.tar.gz
else
    echo "  ❌ Frontend 백업 실패"
fi
echo ""

# 4. 오래된 백업 삭제
echo "4. 오래된 백업 정리 중 (${KEEP_DAYS}일 이상)..."
DELETED_COUNT=$(find $BACKUP_DIR -name "backup_*.dump" -mtime +$KEEP_DAYS -delete -print | wc -l)
DELETED_COUNT=$((DELETED_COUNT + $(find $BACKUP_DIR -name "backend_*.tar.gz" -mtime +$KEEP_DAYS -delete -print | wc -l)))
DELETED_COUNT=$((DELETED_COUNT + $(find $BACKUP_DIR -name "frontend_*.tar.gz" -mtime +$KEEP_DAYS -delete -print | wc -l)))
echo "  ✅ 삭제된 백업 파일 수: $DELETED_COUNT"
echo ""

# 5. 백업 요약
echo "====================================="
echo "백업 완료!"
echo "====================================="
echo "백업 위치: $BACKUP_DIR"
echo ""
echo "백업 파일 목록:"
ls -lh $BACKUP_DIR/*$DATE*
echo ""
echo "전체 백업 크기:"
du -sh $BACKUP_DIR
echo ""
