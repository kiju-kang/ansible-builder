/**
 * ConfigContext - 동적 설정 관리
 * Kubernetes ConfigMap에서 환경변수를 로드하여 Frontend에 제공
 * IP 변경 시 빌드 없이 ConfigMap만 수정하면 됨
 */
import React, { createContext, useContext, useState, useEffect } from 'react';

const ConfigContext = createContext(null);

// 기본값 (API 로드 전 또는 실패 시 사용)
const defaultConfig = {
    keycloak_url: `http://${window.location.hostname}:30002`,
    keycloak_realm: 'ansible-realm',
    keycloak_client_id: 'ansible-builder-client',
    awx_url: `http://${window.location.hostname}:30000`,
    app_title: 'Ansible 작업 생성기',
    app_env: 'development',
    keycloak_enabled: true,
};

export function ConfigProvider({ children }) {
    const [config, setConfig] = useState(defaultConfig);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const loadConfig = async () => {
            try {
                const res = await fetch('/api/config');
                if (res.ok) {
                    const data = await res.json();
                    setConfig({ ...defaultConfig, ...data });
                    console.log('✅ Config loaded from backend:', data);
                } else {
                    console.warn('⚠️ Failed to load config, using defaults');
                }
            } catch (err) {
                console.warn('⚠️ Config API not available, using defaults:', err.message);
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        loadConfig();
    }, []);

    return (
        <ConfigContext.Provider value={{ config, loading, error }}>
            {children}
        </ConfigContext.Provider>
    );
}

export function useConfig() {
    const context = useContext(ConfigContext);
    if (!context) {
        throw new Error('useConfig must be used within ConfigProvider');
    }
    return context;
}

// 간편하게 config만 가져오기
export function useConfigValue() {
    const { config } = useConfig();
    return config;
}

export default ConfigContext;
