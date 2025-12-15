# AWX - Keycloak SSO 통합 가이드

## 1. Keycloak에 AWX Client 생성

### 1.1 Keycloak Admin Console 접속
- URL: http://192.168.64.26:8080/admin
- Realm: ansible-realm

### 1.2 새 Client 생성
```
Client ID: awx-client
Client Protocol: openid-connect
Access Type: confidential
Valid Redirect URIs:
  - http://AWX_HOST/sso/complete/oidc/
  - http://AWX_HOST/*
Web Origins: http://AWX_HOST
```

### 1.3 Client Secret 확인
Credentials 탭에서 Client Secret 복사

## 2. AWX 환경변수 설정

AWX 컨테이너 또는 docker-compose.yml에 추가:

```yaml
environment:
  # Keycloak OIDC 설정
  SOCIAL_AUTH_OIDC_KEY: awx-client
  SOCIAL_AUTH_OIDC_SECRET: <keycloak-client-secret>
  SOCIAL_AUTH_OIDC_OIDC_ENDPOINT: http://192.168.64.26:8080/realms/ansible-realm

  # 추가 OIDC 설정
  SOCIAL_AUTH_OIDC_VERIFY_SSL: "false"
  SOCIAL_AUTH_OIDC_USERNAME_KEY: preferred_username

  # 자동 사용자 생성
  SOCIAL_AUTH_CREATE_USERS: "true"
  SOCIAL_AUTH_REMOVE_DISABLED_USERS: "false"
```

## 3. AWX Settings 설정 (UI)

AWX Admin UI → Settings → Authentication → SAML/OIDC:

```json
{
  "SOCIAL_AUTH_OIDC_KEY": "awx-client",
  "SOCIAL_AUTH_OIDC_SECRET": "<client-secret>",
  "SOCIAL_AUTH_OIDC_OIDC_ENDPOINT": "http://192.168.64.26:8080/realms/ansible-realm"
}
```

## 4. 사용자 매핑 설정

Keycloak Client Scopes → awx-client → Mappers:

### Username Mapper
```
Name: username
Mapper Type: User Property
Property: username
Token Claim Name: preferred_username
Claim JSON Type: String
```

### Email Mapper
```
Name: email
Mapper Type: User Property
Property: email
Token Claim Name: email
Claim JSON Type: String
```

### Groups Mapper (Optional - Role 기반 접근 제어)
```
Name: groups
Mapper Type: Group Membership
Token Claim Name: groups
Full group path: OFF
```

## 5. SSO 흐름

1. 사용자가 Ansible Builder에서 Keycloak SSO 로그인
2. Keycloak 세션 생성 (Cookie 저장)
3. 사용자가 AWX URL 접속
4. AWX가 Keycloak 세션 확인
5. **자동 로그인!** (재인증 불필요)

## 6. 테스트 절차

1. Ansible Builder 로그아웃
2. Ansible Builder 로그인 (Keycloak SSO)
3. 새 탭에서 AWX 접속
4. 자동으로 로그인되는지 확인

## 주의사항

- 같은 브라우저 사용 (Cookie 공유)
- 같은 Keycloak Realm 사용 (ansible-realm)
- AWX와 Keycloak이 서로 통신 가능한 네트워크
- HTTPS 사용 권장 (Production 환경)
