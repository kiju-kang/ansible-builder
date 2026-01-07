/**
 * Keycloak 클라이언트 설정
 * Backend /api/config에서 동적으로 설정을 로드
 * Kubernetes ConfigMap으로 관리되어 빌드 없이 IP 변경 가능
 */
import Keycloak from 'keycloak-js';

// 기본값 (API 실패 시 또는 Vite 환경변수 사용)
const DEFAULT_KEYCLOAK_URL = import.meta.env.VITE_KEYCLOAK_URL || `http://${window.location.hostname}:30002`;
const DEFAULT_KEYCLOAK_REALM = import.meta.env.VITE_KEYCLOAK_REALM || 'ansible-realm';
const DEFAULT_KEYCLOAK_CLIENT_ID = import.meta.env.VITE_KEYCLOAK_CLIENT_ID || 'ansible-builder-client';

// Keycloak 인스턴스 (초기화 전 null)
let keycloakInstance = null;
let configLoaded = false;

/**
 * Backend에서 설정을 로드하고 Keycloak 인스턴스 생성
 * @returns {Promise<Keycloak>} Keycloak 인스턴스
 */
export async function initKeycloak() {
  if (keycloakInstance && configLoaded) {
    return keycloakInstance;
  }

  let config = {
    url: DEFAULT_KEYCLOAK_URL,
    realm: DEFAULT_KEYCLOAK_REALM,
    clientId: DEFAULT_KEYCLOAK_CLIENT_ID,
  };

  try {
    const res = await fetch('/api/config');
    if (res.ok) {
      const data = await res.json();
      if (data.keycloak_url) {
        config = {
          url: data.keycloak_url,
          realm: data.keycloak_realm || DEFAULT_KEYCLOAK_REALM,
          clientId: data.keycloak_client_id || DEFAULT_KEYCLOAK_CLIENT_ID,
        };
        console.log('✅ Keycloak config loaded from backend:', config.url);
      }
    }
  } catch (err) {
    console.warn('⚠️ Using default Keycloak config:', err.message);
  }

  keycloakInstance = new Keycloak(config);
  configLoaded = true;

  return keycloakInstance;
}

/**
 * 현재 Keycloak 인스턴스 반환 (동기)
 * initKeycloak()이 먼저 호출되어야 함
 */
export function getKeycloak() {
  if (!keycloakInstance) {
    // 초기화되지 않은 경우 기본값으로 생성
    keycloakInstance = new Keycloak({
      url: DEFAULT_KEYCLOAK_URL,
      realm: DEFAULT_KEYCLOAK_REALM,
      clientId: DEFAULT_KEYCLOAK_CLIENT_ID,
    });
  }
  return keycloakInstance;
}

// 하위 호환성을 위한 기본 export
export default getKeycloak();

