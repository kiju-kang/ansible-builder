import React, { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Login from './components/Login';
import PlaybookBuilder from './components/PlaybookBuilder';
import PlaybookList from './components/PlaybookList';
import InventoryManager from './components/InventoryManager';
import ExecutionPanel from './components/ExecutionPanel';
import ExecutionHistory from './components/ExecutionHistory';
import { LogOut, User } from 'lucide-react';

// 환경 변수에서 API URL 읽기 (Vite: import.meta.env)
const API_URL = import.meta.env.VITE_API_URL || '/api';

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
    if (view === 'execute' || view === 'execute-local' || view === 'execute-remote') {
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
    if (!confirm('이 작업목록을 삭제하시겠습니까?')) return;

    try {
      await fetch(`${API_URL}/playbooks/${id}`, { method: 'DELETE' });
      alert('✅ 작업목록이 삭제되었습니다');
      loadPlaybooks();
    } catch (err) {
      alert('❌ 삭제에 실패했습니다');
    }
  };

  // 로딩 중이면 로딩 화면 표시
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">로딩 중...</p>
        </div>
      </div>
    );
  }

  // 인증되지 않은 경우 로그인 화면 표시
  if (!isAuthenticated) {
    return <Login />;
  }

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col">
      {/* Top Header Bar */}
      <header className="bg-[#131921] text-white px-4 py-2 flex justify-between items-center flex-shrink-0">
        <div className="flex items-center gap-3">
          <span className="text-xl font-semibold">GAIA Builder</span>
          <span className="text-xs text-gray-400 border-l border-gray-600 pl-3">Console</span>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-sm">
            <User size={16} className="text-gray-300" />
            <span className="text-gray-200">{user?.username}</span>
            <span className="text-xs text-gray-400 bg-[#232f3e] px-2 py-0.5 rounded">{user?.role}</span>
          </div>
          <button
            onClick={logout}
            className="flex items-center gap-1 px-3 py-1.5 text-sm text-gray-300 hover:text-white hover:bg-[#37475a] rounded transition"
          >
            <LogOut size={14} />
            로그아웃
          </button>
        </div>
      </header>

      {/* Main Layout: Sidebar + Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Sidebar Navigation */}
        <aside className="w-56 bg-[#232f3e] text-white flex-shrink-0 overflow-y-auto">
          {/* 작업 그룹 */}
          <div className="border-b border-gray-600">
            <div className="px-4 py-3 text-[#ff9900] text-xs font-bold uppercase tracking-wide">
              작업
            </div>
            <nav className="pb-2">
              <button
                onClick={() => navigate('builder')}
                className={`w-full text-left px-4 py-2.5 text-sm flex items-center gap-2 transition ${view === 'builder'
                  ? 'bg-[#37475a] text-white border-l-4 border-[#ff9900]'
                  : 'text-gray-300 hover:bg-[#37475a] hover:text-white border-l-4 border-transparent'
                  }`}
              >
                📝 생성
              </button>
              <button
                onClick={() => navigate('playbooks')}
                className={`w-full text-left px-4 py-2.5 text-sm flex items-center gap-2 transition ${view === 'playbooks'
                  ? 'bg-[#37475a] text-white border-l-4 border-[#ff9900]'
                  : 'text-gray-300 hover:bg-[#37475a] hover:text-white border-l-4 border-transparent'
                  }`}
              >
                📚 작업목록
              </button>
              <button
                onClick={() => navigate('inventories')}
                className={`w-full text-left px-4 py-2.5 text-sm flex items-center gap-2 transition ${view === 'inventories'
                  ? 'bg-[#37475a] text-white border-l-4 border-[#ff9900]'
                  : 'text-gray-300 hover:bg-[#37475a] hover:text-white border-l-4 border-transparent'
                  }`}
              >
                🖥️ 대상
              </button>
            </nav>
          </div>

          {/* 실행 그룹 */}
          <div className="border-b border-gray-600">
            <div className="px-4 py-3 text-[#ff9900] text-xs font-bold uppercase tracking-wide">
              실행
            </div>
            <nav className="pb-2">
              <button
                onClick={() => navigate('execute-local')}
                className={`w-full text-left px-4 py-2.5 text-sm flex items-center gap-2 transition ${view === 'execute-local'
                  ? 'bg-[#37475a] text-white border-l-4 border-[#ff9900]'
                  : 'text-gray-300 hover:bg-[#37475a] hover:text-white border-l-4 border-transparent'
                  }`}
              >
                💻 로컬 실행
              </button>
              <button
                onClick={() => navigate('execute-remote')}
                className={`w-full text-left px-4 py-2.5 text-sm flex items-center gap-2 transition ${view === 'execute-remote'
                  ? 'bg-[#37475a] text-white border-l-4 border-[#ff9900]'
                  : 'text-gray-300 hover:bg-[#37475a] hover:text-white border-l-4 border-transparent'
                  }`}
              >
                ☁️ 원격 실행 (GAIA)
              </button>
              <button
                onClick={() => navigate('executions')}
                className={`w-full text-left px-4 py-2.5 text-sm flex items-center gap-2 transition ${view === 'executions'
                  ? 'bg-[#37475a] text-white border-l-4 border-[#ff9900]'
                  : 'text-gray-300 hover:bg-[#37475a] hover:text-white border-l-4 border-transparent'
                  }`}
              >
                📋 실행 이력
              </button>
            </nav>
          </div>
        </aside>

        {/* Main Content Area */}
        <main className="flex-1 overflow-y-auto p-6">
          <div className="max-w-7xl mx-auto">
            {view === 'builder' && (
              <PlaybookBuilder
                onSave={loadPlaybooks}
                onNavigate={navigate}
                editingPlaybook={viewData?.editingPlaybook}
              />
            )}

            {view === 'playbooks' && (
              <PlaybookList
                playbooks={playbooks}
                onEdit={(pb) => navigate('builder', { editingPlaybook: pb })}
                onDelete={deletePlaybook}
                onRefresh={loadPlaybooks}
                onNavigate={navigate}
              />
            )}

            {view === 'inventories' && (
              <InventoryManager
                inventories={inventories}
                onRefresh={loadInventories}
              />
            )}

            {view === 'execute-local' && (
              <ExecutionPanel
                playbooks={playbooks}
                inventories={inventories}
                onNavigate={navigate}
                mode="local"
                onExecute={(execId) => {
                  setCurrentExecution(execId);
                  setIsExecuting(true);
                  navigate('executions');
                }}
              />
            )}

            {view === 'execute-remote' && (
              <ExecutionPanel
                playbooks={playbooks}
                inventories={inventories}
                onNavigate={navigate}
                mode="remote"
                onExecute={(execId) => {
                  setCurrentExecution(execId);
                  setIsExecuting(true);
                  navigate('executions');
                }}
              />
            )}

            {/* Legacy execute view redirects to local */}
            {view === 'execute' && (
              <ExecutionPanel
                playbooks={playbooks}
                inventories={inventories}
                onNavigate={navigate}
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
        </main>
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