# JWT 인증 시스템 구현 완료

## ✅ 구현 완료 사항

### 백엔드 (Backend)

#### 1. 데이터베이스 스키마
- ✅ `AnsibleBuilderUser` 테이블 추가
  - username, email, hashed_password, role, is_active 등
- ✅ `AnsibleBuilderAuditLog` 테이블 추가
  - 모든 작업 감사 로그 기록
- ✅ `AnsibleBuilderPlaybook` 테이블에 owner 필드 추가
  - owner_id, owner_username
- ✅ `AnsibleBuilderInventory` 테이블에 owner 필드 추가
  - owner_id, owner_username

#### 2. 인증 시스템 ([auth.py](/root/ansible-builder/ansible-builder/backend/auth.py))
- ✅ JWT 토큰 생성 및 검증
- ✅ bcrypt 비밀번호 해싱
- ✅ 사용자 인증 함수들
- ✅ 권한 확인 (Admin vs User)
- ✅ 리소스 소유권 체크
- ✅ 감사 로그 기록 함수
- ✅ 기본 admin 사용자 자동 생성

#### 3. API 엔드포인트
**인증 엔드포인트:**
- ✅ `POST /api/auth/register` - 사용자 등록 (Admin only)
- ✅ `POST /api/auth/login` - 로그인
- ✅ `GET /api/auth/me` - 현재 사용자 정보
- ✅ `GET /api/auth/users` - 사용자 목록 (Admin only)
- ✅ `DELETE /api/auth/users/{user_id}` - 사용자 삭제 (Admin only)

**보안이 추가된 엔드포인트:**
- ✅ `POST /api/playbooks` - owner 정보 저장, 감사 로그
- ✅ `PUT /api/playbooks/{id}` - 소유권 체크, 감사 로그
- ✅ `DELETE /api/playbooks/{id}` - 소유권 체크, 감사 로그
- ✅ `POST /api/inventories` - owner 정보 저장, 감사 로그
- ✅ `DELETE /api/inventories/{id}` - 소유권 체크, 감사 로그

### 프론트엔드 (Frontend)

#### 1. 인증 컴포넌트
- ✅ [Login.jsx](/root/ansible-builder/ansible-builder/frontend/frontend/src/components/Login.jsx)
  - 로그인 폼
  - 에러 처리
  - 기본 credentials 안내

#### 2. 상태 관리
- ✅ [AuthContext.jsx](/root/ansible-builder/ansible-builder/frontend/frontend/src/contexts/AuthContext.jsx)
  - 전역 인증 상태 관리
  - localStorage 토큰 저장/복원
  - login/logout 함수
  - getAuthHeader() - API 요청용 Authorization 헤더

#### 3. UI 업데이트
- ✅ [App.jsx](/root/ansible-builder/ansible-builder/frontend/frontend/src/App.jsx) 수정
  - AuthProvider로 전체 앱 감싸기
  - 로그인 화면 조건부 렌더링
  - 네비게이션 바에 사용자 정보 표시
  - 로그아웃 버튼 추가
  - API 요청에 Authorization 헤더 추가

## 🔐 보안 기능

1. **JWT 토큰 인증**
   - Stateless 인증
   - 24시간 만료 (설정 가능)
   - Bearer 토큰 방식

2. **비밀번호 보안**
   - bcrypt 해싱 (강력한 단방향 암호화)
   - Salt 자동 생성

3. **역할 기반 접근 제어 (RBAC)**
   - **Admin**: 모든 권한
     - 모든 리소스 생성/조회/수정/삭제
     - 사용자 관리
     - 감사 로그 조회
   - **User**: 제한된 권한
     - 자신이 생성한 리소스만 수정/삭제
     - 모든 리소스 조회 가능
     - 새 리소스 생성 가능

4. **리소스 소유권**
   - 각 Playbook/Inventory는 생성자 정보 저장
   - User는 자신의 리소스만 수정/삭제 가능
   - Admin은 모든 리소스 접근 가능
   - 레거시 리소스(owner_id = NULL)는 모두 접근 가능

5. **감사 로그**
   - 모든 CRUD 작업 기록
   - 사용자, 액션, 리소스 타입, IP 주소 등 저장
   - 보안 감사 및 추적 가능

## 📝 기본 계정 정보

서버 시작 시 자동으로 생성되는 기본 Admin 계정:

```
Username: admin
Password: admin123
Role: admin
```

⚠️ **중요**: 프로덕션 환경에서는 반드시 기본 비밀번호를 변경하세요!

## 🚀 사용 방법

### 1. 서버 시작

```bash
cd /root/ansible-builder/ansible-builder/backend
python3 main.py
```

### 2. 웹 브라우저에서 접속

```
http://localhost:8000
```

로그인 화면이 자동으로 표시됩니다.

### 3. 로그인

기본 admin 계정으로 로그인:
- Username: `admin`
- Password: `admin123`

### 4. API 테스트 (curl)

**로그인:**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

응답에서 `access_token`을 받아서 사용:

**인증된 요청:**
```bash
TOKEN="your_access_token_here"

curl http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer $TOKEN"

curl http://localhost:8000/api/playbooks \
  -H "Authorization: Bearer $TOKEN"
```

**새 사용자 생성 (Admin only):**
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user1",
    "email": "user1@example.com",
    "password": "password123",
    "full_name": "User One",
    "role": "user"
  }'
```

## 📂 파일 구조

```
/root/ansible-builder/ansible-builder/
├── backend/
│   ├── main.py              # 메인 FastAPI 애플리케이션 (인증 추가됨)
│   ├── auth.py              # JWT 인증 로직 (새로 생성)
│   └── database.py          # 데이터베이스 모델 (User, AuditLog 추가)
└── frontend/frontend/src/
    ├── App.jsx              # 메인 앱 (인증 통합)
    ├── components/
    │   └── Login.jsx        # 로그인 컴포넌트 (새로 생성)
    └── contexts/
        └── AuthContext.jsx  # 인증 상태 관리 (새로 생성)
```

## 🔄 작동 흐름

### 로그인 플로우
1. 사용자가 Login 화면에서 username/password 입력
2. `POST /api/auth/login` 호출
3. 백엔드에서 비밀번호 검증 (bcrypt)
4. JWT 토큰 생성 및 반환
5. 프론트엔드에서 토큰을 localStorage에 저장
6. AuthContext에 사용자 정보와 토큰 저장
7. 메인 화면으로 리다이렉트

### API 요청 플로우
1. 프론트엔드에서 API 요청 시 `Authorization: Bearer <token>` 헤더 추가
2. 백엔드에서 토큰 검증
3. 토큰에서 사용자 정보 추출
4. 리소스 접근 권한 확인
5. 요청 처리 후 응답
6. 감사 로그 기록

### 로그아웃 플로우
1. 사용자가 Logout 버튼 클릭
2. localStorage에서 토큰 제거
3. AuthContext 상태 초기화
4. 로그인 화면으로 리다이렉트

## 🛡️ 보안 권장 사항

### 즉시 적용
- ✅ JWT Secret Key 환경 변수로 관리
- ✅ bcrypt 비밀번호 해싱
- ✅ 감사 로그 시스템
- ✅ Role 기반 권한 관리
- ✅ 리소스 소유권 확인

### 추가 권장 (향후 개선)
- ⚠️ HTTPS 사용 (프로덕션 필수)
- ⚠️ CORS 설정 제한 (특정 도메인만 허용)
- ⚠️ Rate Limiting (DoS 방지)
- ⚠️ Refresh Token 구현 (토큰 갱신)
- ⚠️ 비밀번호 정책 강화 (길이, 복잡도)
- ⚠️ 2FA (이중 인증)
- ⚠️ 세션 타임아웃
- ⚠️ IP 화이트리스트

## 📊 데이터베이스 테이블

### ansible_builder_users
```sql
id, username, email, hashed_password, full_name, role, is_active, created_at, updated_at
```

### ansible_builder_audit_logs
```sql
id, user_id, username, action, resource_type, resource_id, details, ip_address, timestamp
```

### ansible_builder_playbooks (업데이트됨)
```sql
id, name, hosts, become, tasks, owner_id, owner_username, created_at, updated_at
```

### ansible_builder_inventories (업데이트됨)
```sql
id, name, content, owner_id, owner_username, created_at, updated_at
```

## 🔧 환경 변수

`.env` 파일 또는 시스템 환경 변수로 설정:

```bash
# JWT Secret Key (프로덕션에서는 강력한 랜덤 키 사용)
JWT_SECRET_KEY=your-very-secret-key-change-this-in-production-12345678

# 토큰 만료 시간 (분)
ACCESS_TOKEN_EXPIRE_MINUTES=1440  # 24시간

# 데이터베이스 URL (이미 설정됨)
DATABASE_URL=postgresql://awx:password@host:5432/awx
```

## 🎯 다음 단계

### 완료된 기능
1. ✅ JWT 기반 인증 시스템
2. ✅ 사용자 관리
3. ✅ 역할 기반 접근 제어
4. ✅ 리소스 소유권 관리
5. ✅ 감사 로그
6. ✅ 로그인 UI
7. ✅ 프론트엔드 통합

### 향후 개선 사항
1. ⏭️ Rate Limiting 추가
2. ⏭️ Refresh Token 구현
3. ⏭️ 비밀번호 변경 기능
4. ⏭️ 비밀번호 재설정 (이메일)
5. ⏭️ 사용자 프로필 관리
6. ⏭️ Admin 대시보드
7. ⏭️ 감사 로그 조회 UI
8. ⏭️ 사용자 활동 통계

## 📚 참고 문서

- [AUTHENTICATION_GUIDE.md](/root/ansible-builder/AUTHENTICATION_GUIDE.md) - 상세 가이드
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [JWT.io](https://jwt.io/)
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)

## ✅ 테스트 체크리스트

- [ ] 로그인 성공 (admin/admin123)
- [ ] 로그인 실패 (잘못된 비밀번호)
- [ ] 로그아웃
- [ ] Playbook 생성 (owner 정보 저장 확인)
- [ ] Playbook 수정 (자신의 리소스)
- [ ] Playbook 수정 (다른 사용자 리소스 - 403 에러)
- [ ] Playbook 삭제 (소유권 확인)
- [ ] Admin으로 모든 리소스 접근
- [ ] User로 제한된 접근
- [ ] 새 사용자 생성 (Admin only)
- [ ] 감사 로그 기록 확인

---

## 🎉 구현 완료!

JWT 기반 인증 시스템이 성공적으로 구현되었습니다. 이제 Ansible Builder는 안전하게 사용자를 인증하고, 리소스 접근을 제어하며, 모든 작업을 감사 로그로 기록합니다.

**기본 admin 계정으로 로그인하여 시스템을 테스트해보세요!**
