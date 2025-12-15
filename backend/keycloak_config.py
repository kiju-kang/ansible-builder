"""
Keycloak 설정 파일
AWX와 Ansible Builder의 통합 인증을 위한 Keycloak 설정
"""
import os

# Keycloak 서버 설정
KEYCLOAK_SERVER_URL = os.getenv("KEYCLOAK_SERVER_URL", "http://192.168.64.26:30002")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "ansible-realm")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "ansible-builder-client")
KEYCLOAK_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", "")  # Public client는 비어있음

# OIDC 엔드포인트
KEYCLOAK_WELL_KNOWN_URL = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/.well-known/openid-configuration"
KEYCLOAK_TOKEN_URL = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
KEYCLOAK_USERINFO_URL = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/userinfo"
KEYCLOAK_JWKS_URL = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
KEYCLOAK_AUTHORIZATION_URL = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/auth"
KEYCLOAK_LOGOUT_URL = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/logout"
KEYCLOAK_INTROSPECTION_URL = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token/introspect"

# JWT 검증 설정
KEYCLOAK_ALGORITHMS = ["RS256"]
KEYCLOAK_AUDIENCE = KEYCLOAK_CLIENT_ID
KEYCLOAK_ISSUER = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}"

# Keycloak 역할 매핑
KEYCLOAK_ADMIN_ROLES = ["admin", "awx-admin"]
KEYCLOAK_USER_ROLES = ["user", "awx-user"]

# 캐시 설정
JWKS_CACHE_TTL = 3600  # 1시간
USER_CACHE_TTL = 300   # 5분
