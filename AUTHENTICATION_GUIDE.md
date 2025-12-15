# JWT 인증 구현 가이드

## 구현 완료 사항

### 1. 데이터베이스 스키마 업데이트
- ✅ `AnsibleBuilderUser` 테이블 추가
- ✅ `AnsibleBuilderAuditLog` 테이블 추가
- ✅ `AnsibleBuilderPlaybook`에 `owner_id`, `owner_username` 필드 추가
- ✅ `AnsibleBuilderInventory`에 `owner_id`, `owner_username` 필드 추가

### 2. 인증 시스템 구현
- ✅ JWT 토큰 기반 인증
- ✅ 비밀번호 해싱 (bcrypt)
- ✅ 사용자 등록/로그인 엔드포인트
- ✅ 감사 로그 시스템

### 3. API 엔드포인트
- ✅ `POST /api/auth/register` - 사용자 등록 (Admin only)
- ✅ `POST /api/auth/login` - 로그인
- ✅ `GET /api/auth/me` - 현재 사용자 정보
- ✅ `GET /api/auth/users` - 사용자 목록 (Admin only)
- ✅ `DELETE /api/auth/users/{user_id}` - 사용자 삭제 (Admin only)

## 다음 단계: 기존 엔드포인트에 인증 추가

### Playbook 엔드포인트 수정이 필요한 부분

파일: `/root/ansible-builder/ansible-builder/backend/main.py`

#### 1. Playbook 생성 (line ~140)
```python
# 수정 전
@app.post("/api/playbooks", response_model=Playbook)
async def create_playbook(playbook: Playbook, db: Session = Depends(get_db)):
    db_playbook = AnsibleBuilderPlaybook(
        name=playbook.name,
        hosts=playbook.hosts,
        become=playbook.become,
        tasks=json.dumps(playbook.tasks)
    )

# 수정 후
@app.post("/api/playbooks", response_model=Playbook)
async def create_playbook(
    playbook: Playbook,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[AnsibleBuilderUser] = Depends(get_optional_user)
):
    db_playbook = AnsibleBuilderPlaybook(
        name=playbook.name,
        hosts=playbook.hosts,
        become=playbook.become,
        tasks=json.dumps(playbook.tasks),
        owner_id=current_user.id if current_user else None,
        owner_username=current_user.username if current_user else None
    )
    db.add(db_playbook)
    db.commit()
    db.refresh(db_playbook)

    # 감사 로그
    log_action(db, current_user, "CREATE", "playbook", db_playbook.id,
               f"Created playbook: {playbook.name}", request.client.host)

    return Playbook(
        id=db_playbook.id,
        name=db_playbook.name,
        hosts=db_playbook.hosts,
        become=db_playbook.become,
        tasks=json.loads(db_playbook.tasks)
    )
```

#### 2. Playbook 업데이트 (line ~179)
```python
# 수정 후
@app.put("/api/playbooks/{playbook_id}", response_model=Playbook)
async def update_playbook(
    playbook_id: int,
    playbook: Playbook,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[AnsibleBuilderUser] = Depends(get_optional_user)
):
    db_playbook = db.query(AnsibleBuilderPlaybook).filter(
        AnsibleBuilderPlaybook.id == playbook_id
    ).first()

    if not db_playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")

    # 권한 체크
    if current_user and not check_resource_access(current_user, db_playbook.owner_id):
        raise HTTPException(status_code=403, detail="Not authorized to update this playbook")

    db_playbook.name = playbook.name
    db_playbook.hosts = playbook.hosts
    db_playbook.become = playbook.become
    db_playbook.tasks = json.dumps(playbook.tasks)
    db.commit()

    # 감사 로그
    log_action(db, current_user, "UPDATE", "playbook", playbook_id,
               f"Updated playbook: {playbook.name}", request.client.host)
```

#### 3. Playbook 삭제 (line ~203)
```python
# 수정 후
@app.delete("/api/playbooks/{playbook_id}")
async def delete_playbook(
    playbook_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[AnsibleBuilderUser] = Depends(get_optional_user)
):
    db_playbook = db.query(AnsibleBuilderPlaybook).filter(
        AnsibleBuilderPlaybook.id == playbook_id
    ).first()

    if not db_playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")

    # 권한 체크
    if current_user and not check_resource_access(current_user, db_playbook.owner_id):
        raise HTTPException(status_code=403, detail="Not authorized to delete this playbook")

    playbook_name = db_playbook.name
    db.delete(db_playbook)
    db.commit()

    # 감사 로그
    log_action(db, current_user, "DELETE", "playbook", playbook_id,
               f"Deleted playbook: {playbook_name}", request.client.host)
```

### Inventory 엔드포인트도 동일한 패턴으로 수정

#### Inventory 생성, 업데이트, 삭제에도 같은 패턴 적용:
- `current_user: Optional[AnsibleBuilderUser] = Depends(get_optional_user)` 추가
- `owner_id`, `owner_username` 저장
- 권한 체크 로직 추가
- 감사 로그 기록

### Execute 엔드포인트 수정 (line ~960)
```python
@app.post("/api/execute")
async def execute_playbook(
    exec_request: ExecuteRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Optional[AnsibleBuilderUser] = Depends(get_optional_user)
):
    # Playbook 권한 체크
    playbook = db.query(AnsibleBuilderPlaybook).filter(
        AnsibleBuilderPlaybook.id == exec_request.playbook_id
    ).first()

    if current_user and playbook and not check_resource_access(current_user, playbook.owner_id):
        raise HTTPException(status_code=403, detail="Not authorized to execute this playbook")

    # ... 기존 로직 ...

    # 감사 로그
    log_action(db, current_user, "EXECUTE", "playbook", exec_request.playbook_id,
               f"Executed playbook", request.client.host)
```

## 기본 사용자 정보

시스템 시작 시 자동으로 생성되는 기본 Admin 계정:
- **Username**: `admin`
- **Password**: `admin123`
- **Role**: `admin`

⚠️ **중요**: 프로덕션 환경에서는 반드시 기본 비밀번호를 변경하세요!

## 환경 변수

`.env` 파일 또는 환경 변수로 설정:

```bash
# JWT Secret Key (프로덕션에서는 강력한 랜덤 키 사용)
JWT_SECRET_KEY=your-very-secret-key-change-this-in-production

# 토큰 만료 시간 (분)
ACCESS_TOKEN_EXPIRE_MINUTES=1440  # 24시간
```

## API 사용 예시

### 1. 로그인
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123"
  }'
```

응답:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com",
    "full_name": "Administrator",
    "role": "admin"
  }
}
```

### 2. 인증된 요청
```bash
curl -X GET http://localhost:8000/api/playbooks \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

### 3. 새 사용자 등록 (Admin only)
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user1",
    "email": "user1@example.com",
    "password": "password123",
    "full_name": "User One",
    "role": "user"
  }'
```

## 권한 체계

### Roles:
- **admin**: 모든 권한
  - 모든 Playbook/Inventory 생성, 조회, 수정, 삭제
  - 사용자 관리
  - 감사 로그 조회
- **user**: 제한된 권한
  - 자신이 생성한 Playbook/Inventory만 수정/삭제 가능
  - 모든 리소스 조회 가능
  - 새 리소스 생성 가능

### 리소스 접근 규칙:
1. Admin은 모든 리소스에 접근 가능
2. User는 자신이 생성한 리소스만 수정/삭제 가능
3. `owner_id`가 NULL인 레거시 리소스는 누구나 접근 가능

## 마이그레이션 전략

기존 데이터베이스에 컬럼을 추가하는 방법:

```sql
-- Playbook 테이블에 owner 필드 추가
ALTER TABLE ansible_builder_playbooks
ADD COLUMN owner_id INTEGER NULL,
ADD COLUMN owner_username VARCHAR(255) NULL;

-- Inventory 테이블에 owner 필드 추가
ALTER TABLE ansible_builder_inventories
ADD COLUMN owner_id INTEGER NULL,
ADD COLUMN owner_username VARCHAR(255) NULL;
```

## 테스트

서버를 재시작하고 테스트:
```bash
cd /root/ansible-builder/ansible-builder/backend
python main.py
```

엔드포인트 테스트:
```bash
# Health check
curl http://localhost:8000/health

# 로그인
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# 현재 사용자 정보
curl http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 보안 권장 사항

1. ✅ JWT Secret Key를 환경 변수로 관리
2. ✅ HTTPS 사용 (프로덕션)
3. ✅ CORS 설정 제한
4. ⚠️ Rate Limiting 추가 (TODO)
5. ✅ 비밀번호 해싱 (bcrypt)
6. ✅ 감사 로그
7. ⚠️ 토큰 갱신 메커니즘 (TODO)
8. ⚠️ 비밀번호 정책 강화 (TODO)

## 다음 할 일

1. 프론트엔드 로그인 UI 구현
2. 프론트엔드에서 JWT 토큰 저장 및 사용
3. Rate Limiting 추가
4. 비밀번호 변경 기능
5. 토큰 갱신 (Refresh Token)
