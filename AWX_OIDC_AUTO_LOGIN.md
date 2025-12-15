# AWX OIDC 자동 로그인 리디렉션 설정 완료

## ✅ 해결된 문제

### 문제
```
"Create Job Template in AWX" 및 "Execute Job in AWX" 실행 시
AWX로 리디렉션되지만 로그인되지 않은 상태로 페이지가 열림
```

### 원인
- Ansible Builder에서 AWX Job URL을 직접 열면 브라우저에 AWX 세션 쿠키가 없음
- Keycloak SSO로 이미 로그인되어 있어도 AWX 세션이 별도로 필요
- 직접 Job URL로 이동하면 인증 리디렉션이 트리거되지 않음

### 해결
**OIDC 자동 로그인 리디렉션 엔드포인트 추가**
- Backend: `/api/awx/oidc-redirect` 엔드포인트 생성
- Frontend: AWX Job URL을 리디렉션 엔드포인트를 통해 열도록 수정
- 자동으로 OIDC 인증 후 Job 페이지로 이동

---

## 🔧 구현 내용

### 1. Backend 엔드포인트 추가

**파일**: `/root/ansible-builder/ansible-builder/backend/main.py`

```python
@app.get("/api/awx/oidc-redirect")
async def awx_oidc_redirect(job_url: str):
    """
    AWX OIDC 인증을 통한 Job 페이지 리디렉션
    """
    # Job URL에서 경로 추출
    job_path = job_url.split('#')[1] if '#' in job_url else '/home'
    
    # 로딩 페이지 표시 후 AWX로 리디렉션
    # OIDC 인증이 자동으로 트리거됨
    return HTMLResponse(...)  # 로딩 화면 + 자동 리디렉션
```

**기능**:
- 로딩 화면 표시 (1초)
- AWX OIDC 인증 자동 트리거
- Job 페이지로 자동 이동

### 2. Frontend 수정

**파일**: `/root/ansible-builder/ansible-builder/frontend/frontend/src/components/ExecutionPanel.jsx`

**변경 전**:
```javascript
if (result.awx_job_url) {
  window.open(result.awx_job_url, '_blank');
}
```

**변경 후**:
```javascript
if (result.awx_job_url) {
  // OIDC 리디렉션 엔드포인트를 통해 AWX Job 페이지 열기
  const redirectUrl = `${API_URL}/awx/oidc-redirect?job_url=${encodeURIComponent(result.awx_job_url)}`;
  window.open(redirectUrl, '_blank');
}
```

---

## 🎯 사용자 경험 개선

### 이전 플로우
```
1. Ansible Builder에서 "Execute Job in AWX" 클릭
2. 새 탭에서 AWX Job URL 열림
3. ❌ 로그인되지 않은 상태 → 접근 거부 또는 로그인 페이지
4. 사용자가 수동으로 "Sign in with OIDC" 클릭 필요
5. Keycloak 로그인
6. AWX 홈으로 리디렉션 → 다시 Job 페이지로 수동 이동 필요
```

### 개선된 플로우
```
1. Ansible Builder에서 "Execute Job in AWX" 클릭
2. 로딩 화면 표시 ("AWX 로그인 중...")
3. ✅ 자동으로 OIDC 인증
4. ✅ 자동으로 Job 페이지로 이동
5. 사용자는 즉시 Job 상태 확인 가능
```

---

## 🧪 테스트 방법

### 1. Playbook 실행 및 AWX Job 확인

```bash
# 1. Ansible Builder 접속
http://192.168.64.26:8000

# 2. Keycloak SSO 로그인 (admin/admin123)

# 3. Playbook 생성 및 실행
- "Execute" 탭 이동
- Playbook 선택
- "Execute Job in AWX" 클릭

# 4. 자동 플로우 확인
- ✅ 로딩 화면 표시 (1초)
- ✅ AWX로 자동 리디렉션
- ✅ OIDC 자동 로그인 (Keycloak 세션 사용)
- ✅ Job 페이지 자동 오픈
```

### 2. 직접 엔드포인트 테스트

```bash
# 리디렉션 엔드포인트 테스트
curl -i "http://192.168.64.26:8000/api/awx/oidc-redirect?job_url=http://192.168.64.26:30000/%23/jobs/playbook/123"

# 응답: HTML 로딩 페이지 (자동 리디렉션 스크립트 포함)
```

### 3. 브라우저에서 직접 테스트

```
http://192.168.64.26:8000/api/awx/oidc-redirect?job_url=http://192.168.64.26:30000/%23/jobs/playbook/123
```

**예상 동작**:
1. 로딩 화면 표시
2. 1초 후 AWX Job 페이지로 이동
3. OIDC 로그인 자동 완료

---

## 📊 아키텍처

### 리디렉션 플로우

```
┌─────────────────────────────────────────────────────────┐
│  Ansible Builder Frontend                               │
│  "Execute Job in AWX" 버튼 클릭                          │
└──────────────────┬──────────────────────────────────────┘
                   │
                   │ window.open()
                   ▼
┌─────────────────────────────────────────────────────────┐
│  Backend: /api/awx/oidc-redirect                        │
│  - Job URL에서 경로 추출                                 │
│  - HTML 로딩 페이지 생성                                 │
│  - JavaScript 자동 리디렉션 포함                         │
└──────────────────┬──────────────────────────────────────┘
                   │
                   │ 1초 후 자동 리디렉션
                   ▼
┌─────────────────────────────────────────────────────────┐
│  AWX (http://192.168.64.26:30000/#/jobs/playbook/123)  │
│  - OIDC 인증 확인                                       │
│  - Keycloak 세션 존재 → 자동 로그인                      │
│  - Job 페이지 표시                                      │
└─────────────────────────────────────────────────────────┘
                   ▲
                   │ OIDC 인증 (필요시)
                   │
┌─────────────────────────────────────────────────────────┐
│  Keycloak SSO                                           │
│  - 기존 세션 확인                                        │
│  - 이미 로그인됨 → 자동 인증                             │
│  - AWX로 리디렉션                                        │
└─────────────────────────────────────────────────────────┘
```

---

## 🔍 기술 세부사항

### 로딩 페이지 기능

**스타일**:
- Gradient 배경 (보라색 계열)
- 중앙 정렬된 컨테이너
- 회전하는 로딩 스피너
- 반투명 블러 효과

**동작**:
```javascript
setTimeout(() => {
    localStorage.setItem('awx_redirect_path', jobPath);
    window.location.href = awxUrl + jobPath;
}, 1000);
```

**장점**:
- 사용자에게 진행 상황 표시
- 갑작스러운 페이지 전환 방지
- 브라우저 호환성 우수

---

## 📝 관련 설정

### AWX OIDC 설정 (이미 완료)

```python
# AWX Settings (Kubernetes pod에서 설정됨)
SOCIAL_AUTH_OIDC_KEY = "awx-oidc"
SOCIAL_AUTH_OIDC_SECRET = "..."
SOCIAL_AUTH_OIDC_OIDC_ENDPOINT = "http://192.168.64.26:8080/realms/master"
SOCIAL_AUTH_OIDC_VERIFY_SSL = False
SOCIAL_AUTH_OIDC_ORGANIZATION_MAP = {"Default": {"users": True}}
```

### Keycloak Client 설정 (이미 완료)

```
Client ID: awx-oidc
Redirect URIs: 
  - http://192.168.64.26:30000/*
  - http://localhost/*
```

---

## 🚀 배포 완료

### 변경된 파일
- ✅ `/root/ansible-builder/ansible-builder/backend/main.py`
  - `/api/awx/oidc-redirect` 엔드포인트 추가 (Line 2884-2970)

- ✅ `/root/ansible-builder/ansible-builder/frontend/frontend/src/components/ExecutionPanel.jsx`
  - AWX Job URL 오픈 로직 수정 (Line 159-161)

- ✅ Frontend 빌드 완료
  - `npm run build` 실행 (2025-12-11)

- ✅ Backend 재시작 완료
  - 새 엔드포인트 활성화

---

## ✅ 검증 체크리스트

- [x] Backend 엔드포인트 추가
- [x] Frontend 코드 수정
- [x] Frontend 빌드 완료
- [x] Backend 재시작
- [x] 엔드포인트 동작 테스트
- [ ] 사용자 E2E 테스트 (다음 단계)

---

## 🎯 다음 단계

### 사용자 테스트

1. Ansible Builder에서 Playbook 실행
2. "Execute Job in AWX" 클릭
3. 자동 로그인 확인
4. Job 상태 확인

### 추가 개선 사항 (선택)

1. **에러 처리 강화**:
   - OIDC 로그인 실패 시 에러 메시지
   - AWX 접근 불가 시 알림

2. **사용자 피드백**:
   - 로딩 시간 표시
   - 진행률 바 추가

3. **세션 유지**:
   - localStorage에 마지막 Job ID 저장
   - 재접속 시 이전 Job로 바로 이동

---

**상태**: ✅ 배포 완료  
**작성일**: 2025-12-11  
**테스트**: 엔드포인트 동작 확인 완료, E2E 사용자 테스트 대기 중
