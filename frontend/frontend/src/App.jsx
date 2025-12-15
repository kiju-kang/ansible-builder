import React, { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Login from './components/Login';
import PlaybookBuilder from './components/PlaybookBuilder';
import PlaybookList from './components/PlaybookList';
import InventoryManager from './components/InventoryManager';
import ExecutionPanel from './components/ExecutionPanel';
import ExecutionHistory from './components/ExecutionHistory';
import { LogOut, User } from 'lucide-react';

const API_URL = '/api';

function AppContent() {
  const { user, logout, isAuthenticated, loading, getAuthHeader } = useAuth();
  const [view, setView] = useState('builder');
  const [viewData, setViewData] = useState(null);
  const [playbooks, setPlaybooks] = useState([]);
  const [inventories, setInventories] = useState([]);
  const [executions, setExecutions] = useState([]);
  const [currentExecution, setCurrentExecution] = useState(null);
  const [isExecuting, setIsExecuting] = useState(false);

  const navigate = (newView, data = null) => {
    setView(newView);
    setViewData(data);
  };

  // Load data on view change
  useEffect(() => {
    if (view === 'playbooks') loadPlaybooks();
    if (view === 'inventories') loadInventories();
    if (view === 'executions') loadExecutions();
    if (view === 'execute') {
      loadPlaybooks();
      loadInventories();
    }
  }, [view]);

  // Poll execution status
  useEffect(() => {
    let interval;
    if (isExecuting && currentExecution) {
      interval = setInterval(async () => {
        try {
          const res = await fetch(`${API_URL}/executions/${currentExecution}`);
          const data = await res.json();
          
          if (data.status === 'completed' || data.status === 'failed' || data.status === 'error') {
            setIsExecuting(false);
            clearInterval(interval);
          }
          
          setExecutions(prev => {
            const idx = prev.findIndex(e => e.id === currentExecution);
            if (idx >= 0) {
              const updated = [...prev];
              updated[idx] = data;
              return updated;
            }
            return [data, ...prev];
          });
        } catch (err) {
          console.error('Failed to poll execution:', err);
        }
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [isExecuting, currentExecution]);

  const loadPlaybooks = async () => {
    try {
      const res = await fetch(`${API_URL}/playbooks`, {
        headers: getAuthHeader()
      });
      const data = await res.json();
      setPlaybooks(data);
    } catch (err) {
      console.error('Failed to load playbooks:', err);
    }
  };

  const loadInventories = async () => {
    try {
      const res = await fetch(`${API_URL}/inventories`, {
        headers: getAuthHeader()
      });
      const data = await res.json();
      setInventories(data);
    } catch (err) {
      console.error('Failed to load inventories:', err);
    }
  };

  const loadExecutions = async () => {
    try {
      const res = await fetch(`${API_URL}/executions`);
      const data = await res.json();
      setExecutions(data);
    } catch (err) {
      console.error('Failed to load executions:', err);
    }
  };

  const deletePlaybook = async (id) => {
    if (!confirm('Delete this playbook?')) return;

    try {
      await fetch(`${API_URL}/playbooks/${id}`, { method: 'DELETE' });
      alert('✅ Playbook deleted');
      loadPlaybooks();
    } catch (err) {
      alert('❌ Failed to delete');
    }
  };

  // 로딩 중이면 로딩 화면 표시
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  // 인증되지 않은 경우 로그인 화면 표시
  if (!isAuthenticated) {
    return <Login />;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navigation */}
      <nav className="bg-blue-600 text-white p-4 shadow-lg">
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          <h1 className="text-2xl font-bold">🚀 Ansible Playbook Builder</h1>
          <div className="flex items-center gap-4">
            <div className="flex gap-2">
            <button 
              onClick={() => navigate('builder')} 
              className={`px-4 py-2 rounded transition ${view === 'builder' ? 'bg-blue-800' : 'bg-blue-500 hover:bg-blue-700'}`}
            >
              Builder
            </button>
            <button 
              onClick={() => navigate('playbooks')} 
              className={`px-4 py-2 rounded transition ${view === 'playbooks' ? 'bg-blue-800' : 'bg-blue-500 hover:bg-blue-700'}`}
            >
              Playbooks
            </button>
            <button 
              onClick={() => navigate('inventories')} 
              className={`px-4 py-2 rounded transition ${view === 'inventories' ? 'bg-blue-800' : 'bg-blue-500 hover:bg-blue-700'}`}
            >
              Inventories
            </button>
            <button 
              onClick={() => navigate('execute')} 
              className={`px-4 py-2 rounded transition ${view === 'execute' ? 'bg-blue-800' : 'bg-blue-500 hover:bg-blue-700'}`}
            >
              Execute
            </button>
            <button
              onClick={() => navigate('executions')}
              className={`px-4 py-2 rounded transition ${view === 'executions' ? 'bg-blue-800' : 'bg-blue-500 hover:bg-blue-700'}`}
            >
              History
            </button>
            </div>
            <div className="flex items-center gap-3 border-l border-blue-500 pl-4">
              <div className="flex items-center gap-2">
                <User size={20} />
                <div className="text-sm">
                  <div className="font-medium">{user?.username}</div>
                  <div className="text-xs text-blue-200">{user?.role}</div>
                </div>
              </div>
              <button
                onClick={logout}
                className="flex items-center gap-2 px-3 py-2 bg-red-500 hover:bg-red-600 rounded transition"
                title="Logout"
              >
                <LogOut size={18} />
                Logout
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto p-6">
        {view === 'builder' && (
          <PlaybookBuilder 
            onSave={loadPlaybooks}
            onNavigate={navigate}
            editingPlaybook={viewData?.editingPlaybook} // ⭐ 전달
          />
        )}

        {view === 'playbooks' && (
          <PlaybookList 
            playbooks={playbooks}
            onEdit={(pb) => {
              // ⭐ 수정: navigate 함수 사용
              navigate('builder', { editingPlaybook: pb });
            }}
            onDelete={deletePlaybook}
            onRefresh={loadPlaybooks}
            onNavigate={navigate} // ⭐ 추가
          />
        )}

        {view === 'inventories' && (
          <InventoryManager 
            inventories={inventories}
            onRefresh={loadInventories}
          />
        )}

        {view === 'execute' && (
          <ExecutionPanel 
            playbooks={playbooks}
            inventories={inventories}
            onExecute={(execId) => {
              setCurrentExecution(execId);
              setIsExecuting(true);
              navigate('executions');
            }}
          />
        )}

        {view === 'executions' && (
          <ExecutionHistory 
            executions={executions}
            currentExecution={currentExecution}
            isExecuting={isExecuting}
            onRefresh={loadExecutions}
          />
        )}
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}