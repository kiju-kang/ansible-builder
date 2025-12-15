"""
Keycloak 인증 모듈
JWT 토큰 검증 및 사용자 프로비저닝
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.orm import Session
import requests
from typing import Optional
from datetime import datetime, timedelta
from database import get_db, AnsibleBuilderUser
from keycloak_config import (
    KEYCLOAK_JWKS_URL, KEYCLOAK_ALGORITHMS,
    KEYCLOAK_AUDIENCE, KEYCLOAK_ISSUER, KEYCLOAK_USERINFO_URL,
    KEYCLOAK_ADMIN_ROLES, JWKS_CACHE_TTL
)

security = HTTPBearer(auto_error=False)

# JWKS 캐시 (성능 향상을 위한 전역 캐시)
_jwks_cache = None
_jwks_cache_time = None

def get_jwks():
    """
    Keycloak의 JWKS(JSON Web Key Set) 가져오기
    캐시를 사용하여 매번 요청하지 않음
    """
    global _jwks_cache, _jwks_cache_time

    # 캐시가 있고 유효한 경우
    if _jwks_cache and _jwks_cache_time:
        if datetime.utcnow() - _jwks_cache_time < timedelta(seconds=JWKS_CACHE_TTL):
            return _jwks_cache

    try:
        # Keycloak에서 JWKS 가져오기
        response = requests.get(KEYCLOAK_JWKS_URL, timeout=5)
        response.raise_for_status()
        _jwks_cache = response.json()
        _jwks_cache_time = datetime.utcnow()
        return _jwks_cache
    except Exception as e:
        # Keycloak 서버 접속 실패
        if _jwks_cache:
            # 이전 캐시가 있으면 그것 사용
            return _jwks_cache
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to connect to Keycloak server: {str(e)}"
        )

def verify_keycloak_token(token: str) -> dict:
    """
    Keycloak JWT 토큰 검증

    Args:
        token: JWT 토큰 문자열

    Returns:
        dict: 토큰 페이로드 (사용자 정보 포함)

    Raises:
        HTTPException: 토큰 검증 실패 시
    """
    try:
        # JWKS에서 공개 키 가져오기
        jwks = get_jwks()

        # JWT 헤더에서 kid (key id) 추출
        unverified_header = jwt.get_unverified_header(token)

        # JWKS에서 해당 kid의 키 찾기
        rsa_key = {}
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"]
                }
                break

        if not rsa_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to find appropriate key in JWKS"
            )

        # JWT 검증 및 디코딩
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=KEYCLOAK_ALGORITHMS,
            audience=KEYCLOAK_AUDIENCE,
            issuer=KEYCLOAK_ISSUER
        )

        return payload

    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token verification failed: {str(e)}"
        )

def extract_role_from_payload(payload: dict) -> str:
    """
    Keycloak 토큰 페이로드에서 역할 추출

    Args:
        payload: JWT 토큰 페이로드

    Returns:
        str: 'admin' 또는 'user'
    """
    # realm_access에서 roles 추출
    realm_roles = payload.get("realm_access", {}).get("roles", [])

    # resource_access에서 client roles 추출
    client_roles = []
    resource_access = payload.get("resource_access", {})
    for client, client_data in resource_access.items():
        client_roles.extend(client_data.get("roles", []))

    # 모든 역할 합치기
    all_roles = realm_roles + client_roles

    # admin 역할 확인
    for role in all_roles:
        if role in KEYCLOAK_ADMIN_ROLES:
            return "admin"

    return "user"

def get_or_create_user_from_keycloak(payload: dict, db: Session) -> AnsibleBuilderUser:
    """
    Keycloak 토큰에서 사용자 정보 추출 및 DB에 생성/업데이트
    JIT (Just-In-Time) 프로비저닝

    Args:
        payload: JWT 토큰 페이로드
        db: 데이터베이스 세션

    Returns:
        AnsibleBuilderUser: 사용자 객체
    """
    # 사용자 정보 추출
    username = payload.get("preferred_username")
    email = payload.get("email", f"{username}@example.com")
    full_name = payload.get("name", username)

    # Role 추출
    role = extract_role_from_payload(payload)

    # DB에서 사용자 조회
    user = db.query(AnsibleBuilderUser).filter(
        AnsibleBuilderUser.username == username
    ).first()

    if user:
        # 기존 사용자 업데이트
        user.email = email
        user.full_name = full_name
        user.role = role
        user.is_active = True
        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
    else:
        # 새 사용자 생성 (JIT Provisioning)
        user = AnsibleBuilderUser(
            username=username,
            email=email,
            hashed_password="",  # Keycloak에서 관리하므로 비어있음
            full_name=full_name,
            role=role,
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return user

async def get_current_user_keycloak(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[AnsibleBuilderUser]:
    """
    Keycloak 토큰으로 현재 사용자 가져오기

    Args:
        credentials: HTTP Bearer 토큰
        db: 데이터베이스 세션

    Returns:
        AnsibleBuilderUser 또는 None
    """
    if not credentials:
        return None

    token = credentials.credentials

    try:
        # 토큰 검증
        payload = verify_keycloak_token(token)

        # 사용자 정보 가져오기 또는 생성
        user = get_or_create_user_from_keycloak(payload, db)

        return user
    except HTTPException:
        # 토큰 검증 실패 - None 반환
        return None
    except Exception as e:
        # 예상치 못한 오류
        print(f"Keycloak auth error: {str(e)}")
        return None

async def get_optional_user_keycloak(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[AnsibleBuilderUser]:
    """
    선택적 Keycloak 인증 (토큰이 없어도 OK)

    Args:
        credentials: HTTP Bearer 토큰 (선택적)
        db: 데이터베이스 세션

    Returns:
        AnsibleBuilderUser 또는 None
    """
    if not credentials:
        return None

    return await get_current_user_keycloak(credentials, db)

async def require_keycloak_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> AnsibleBuilderUser:
    """
    필수 Keycloak 인증 (토큰이 없으면 401 에러)

    Args:
        credentials: HTTP Bearer 토큰
        db: 데이터베이스 세션

    Returns:
        AnsibleBuilderUser

    Raises:
        HTTPException: 인증 실패 시
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    token = credentials.credentials

    # 토큰 검증
    payload = verify_keycloak_token(token)

    # 사용자 정보 가져오기 또는 생성
    user = get_or_create_user_from_keycloak(payload, db)

    return user
