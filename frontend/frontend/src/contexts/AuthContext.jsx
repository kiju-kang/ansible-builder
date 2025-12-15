import React, { createContext, useContext, useState, useEffect } from 'react';
import keycloak from '../keycloak';

const AuthContext = createContext(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    initKeycloak();
  }, []);

  const initKeycloak = async () => {
    try {
      // Keycloak 초기화
      const authenticated = await keycloak.init({
        onLoad: 'check-sso',
        silentCheckSsoRedirectUri: window.location.origin + '/silent-check-sso.html',
        checkLoginIframe: false
        // pkceMethod는 HTTP 환경에서 Web Crypto API 에러를 발생시키므로 제거
        // HTTPS 환경에서는 pkceMethod: 'S256' 사용 권장
      });

      if (authenticated) {
        // Keycloak 인증됨
        setToken(keycloak.token);

        // 사용자 정보 가져오기
        const profile = await keycloak.loadUserProfile();
        const userData = {
          id: profile.id,
          username: profile.username,
          email: profile.email,
          full_name: `${profile.firstName || ''} ${profile.lastName || ''}`.trim() || profile.username,
          role: keycloak.hasRealmRole('admin') ? 'admin' : 'user'
        };
        setUser(userData);
        localStorage.setItem('user', JSON.stringify(userData));

        // 토큰 자동 갱신 (1분마다 체크)
        setInterval(() => {
          keycloak.updateToken(70).then(refreshed => {
            if (refreshed) {
              setToken(keycloak.token);
            }
          }).catch(() => {
            console.error('Failed to refresh token');
          });
        }, 60000);
      }

      setLoading(false);
    } catch (error) {
      console.error('Keycloak initialization failed', error);
      setLoading(false);
    }
  };

  const login = () => {
    keycloak.login({
      redirectUri: window.location.origin
    });
  };

  const logout = () => {
    keycloak.logout({
      redirectUri: window.location.origin
    });
    setUser(null);
    setToken(null);
    localStorage.removeItem('user');
  };

  const getAuthHeader = () => {
    return token ? { 'Authorization': `Bearer ${token}` } : {};
  };

  const value = {
    user,
    token,
    login,
    logout,
    getAuthHeader,
    isAuthenticated: !!token,
    isAdmin: user?.role === 'admin',
    loading
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
