/**
 * Keycloak 클라이언트 설정
 * AWX와 통합 인증을 위한 Keycloak 초기화
 */
import Keycloak from 'keycloak-js';

// Keycloak 인스턴스 생성
const keycloak = new Keycloak({
  url: 'http://192.168.64.26:30002',
  realm: 'ansible-realm',
  clientId: 'ansible-builder-client'
});

export default keycloak;
