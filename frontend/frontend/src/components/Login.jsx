import React from 'react';
import { Key } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

export default function Login() {
  const { login } = useAuth();

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#232f3e] p-4">
      <div className="bg-white rounded-lg shadow-2xl p-8 w-full max-w-md border-t-4 border-[#ff9900]">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-[#232f3e] rounded-lg mb-6">
            <Key className="text-[#ff9900]" size={32} />
          </div>
          <h1 className="text-2xl font-bold text-[#232f3e] mb-2">GAIA Builder</h1>
          <p className="text-gray-500 text-sm">Console에 로그인</p>
        </div>

        <div className="mb-6">
          <button
            onClick={login}
            className="w-full flex items-center justify-center gap-3 bg-[#ff9900] text-white py-3 px-6 rounded hover:bg-[#ec7211] focus:ring-4 focus:ring-[#ff9900]/30 font-medium transition shadow-md text-base"
          >
            <Key size={20} />
            SSO로 로그인
          </button>
        </div>

        <div className="border-t border-gray-200 pt-4 mt-6">
          <p className="text-xs text-gray-400 text-center">
            Keycloak SSO를 통해 인증됩니다
          </p>
        </div>
      </div>
    </div>
  );
}
