import React from 'react';
import { Key } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

export default function Login() {
  const { login } = useAuth();

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-500 to-purple-600 p-4">
      <div className="bg-white rounded-lg shadow-2xl p-8 w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-20 h-20 bg-blue-100 rounded-full mb-6">
            <Key className="text-blue-600" size={40} />
          </div>
          <h1 className="text-3xl font-bold text-gray-800 mb-2">Ansible Builder</h1>
          <p className="text-gray-600">Sign in with Keycloak SSO</p>
        </div>

        <div className="mb-6">
          <button
            onClick={login}
            className="w-full flex items-center justify-center gap-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white py-4 px-6 rounded-lg hover:from-purple-700 hover:to-blue-700 focus:ring-4 focus:ring-purple-300 font-medium transition shadow-lg text-lg"
          >
            <Key size={24} />
            Sign in with Keycloak SSO
          </button>
        </div>

        <div className="mt-8 text-center">
          <p className="text-xs text-blue-600">
            All authentication is managed through Keycloak SSO
          </p>
        </div>
      </div>
    </div>
  );
}
