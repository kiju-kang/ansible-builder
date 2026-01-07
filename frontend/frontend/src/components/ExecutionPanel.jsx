import React, { useState, useEffect } from 'react';
import { Play, Plus, Loader, RefreshCw, Database, ExternalLink } from 'lucide-react';

// 환경 변수에서 API URL 읽기 (Vite: import.meta.env)
const API_URL = import.meta.env.VITE_API_URL || '/api';
const AWX_DEV_URL = import.meta.env.VITE_AWX_DEV_URL || '';
const AWX_PROD_URL = import.meta.env.VITE_AWX_PROD_URL || '';

export default function ExecutionPanel({ playbooks, inventories, onExecute, onNavigate, mode = 'both' }) {
  const [selectedPlaybook, setSelectedPlaybook] = useState(null);
  const [selectedInventory, setSelectedInventory] = useState(null);

  // Inventory source: 'local' or 'external'
  const [inventorySource, setInventorySource] = useState('local');
  const [externalInventories, setExternalInventories] = useState([]);
  const [loadingExternal, setLoadingExternal] = useState(false);

  // 환경 선택: 'dev' or 'prod'
  const [selectedEnv, setSelectedEnv] = useState('dev');

  // AWX Configuration - URL은 선택된 환경에 따라 자동 설정
  const [awxConfig, setAwxConfig] = useState({
    url: AWX_DEV_URL,
    template_id: null
  });

  const [awxTemplates, setAwxTemplates] = useState([]);
  const [creatingTemplate, setCreatingTemplate] = useState(false);
  const [executorStatus, setExecutorStatus] = useState(null);

  // API 인벤토리 모달 상태
  const [showApiModal, setShowApiModal] = useState(false);
  const [apiInventoryList, setApiInventoryList] = useState([]);
  const [loadingApiInventory, setLoadingApiInventory] = useState(false);
  const [selectedApiItems, setSelectedApiItems] = useState([]);
  const [apiSearchTerm, setApiSearchTerm] = useState('');

  // 환경 변경 시 AWX URL 업데이트
  useEffect(() => {
    const newUrl = selectedEnv === 'dev' ? AWX_DEV_URL : AWX_PROD_URL;
    setAwxConfig(prev => ({ ...prev, url: newUrl }));
  }, [selectedEnv]);

  // Load default AWX config on mount
  useEffect(() => {
    const loadConfig = async () => {
      try {
        const res = await fetch(`${API_URL}/awx/config`);
        const data = await res.json();
        if (data.url) {
          setAwxConfig(prev => ({ ...prev, url: data.url }));
        }
      } catch (err) {
        console.error('Failed to load AWX config:', err);
      }
    };
    loadConfig();
  }, []);

  // Check executor status when AWX config changes
  useEffect(() => {
    const checkExecutor = async () => {
      if (awxConfig.url) {
        try {
          const params = new URLSearchParams({
            awx_url: awxConfig.url
          });

          const res = await fetch(`${API_URL}/awx/check-executor?${params}`);
          const data = await res.json();
          setExecutorStatus(data);
        } catch (err) {
          console.error('Failed to check executor status:', err);
        }
      }
    };

    const timeoutId = setTimeout(checkExecutor, 500);
    return () => clearTimeout(timeoutId);
  }, [awxConfig.url]);

  const executePlaybook = async () => {
    if (!selectedPlaybook || !selectedInventory) {
      alert('플레이북과 인벤토리를 모두 선택하세요');
      return;
    }

    try {
      const res = await fetch(`${API_URL}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          playbook_id: selectedPlaybook,
          inventory_id: selectedInventory,
          extra_vars: {}
        })
      });
      const result = await res.json();

      if (onExecute) {
        onExecute(result.execution_id);
      }
    } catch (err) {
      alert('❌ 실행 실패');
    }
  };

  const loadAwxTemplates = async () => {
    try {
      const params = new URLSearchParams({
        awx_url: awxConfig.url
      });
      const res = await fetch(`${API_URL}/awx/templates?${params}`);
      const data = await res.json();
      setAwxTemplates(data.templates || []);

      if (data.templates && data.templates.length > 0) {
        setAwxConfig({ ...awxConfig, template_id: data.templates[0].id });
      }

      alert(`✅ ${data.templates.length}개 템플릿 로드됨`);
    } catch (err) {
      alert('❌ AWX 템플릿 로드 실패: ' + err.message);
    }
  };

  // Load inventories from external API (AWX)
  const loadExternalInventories = async () => {
    if (!awxConfig.url) {
      alert('AWX URL을 먼저 입력하세요');
      return;
    }

    setLoadingExternal(true);
    try {
      const params = new URLSearchParams({ awx_url: awxConfig.url });
      const res = await fetch(`${API_URL}/awx/inventories?${params}`);
      const data = await res.json();

      if (data.inventories) {
        setExternalInventories(data.inventories);
        alert(`✅ ${data.inventories.length}개의 외부 Inventory를 불러왔습니다`);
      } else {
        setExternalInventories([]);
        alert('외부 Inventory를 찾을 수 없습니다');
      }
    } catch (err) {
      alert('❌ 외부 Inventory 불러오기 실패: ' + err.message);
    } finally {
      setLoadingExternal(false);
    }
  };

  // 외부 API에서 인벤토리 목록 불러오기
  const loadApiInventories = async () => {
    setLoadingApiInventory(true);
    setShowApiModal(true);
    try {
      const res = await fetch(`${API_URL}/proxy/inventory/list`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      const data = await res.json();
      setApiInventoryList(Array.isArray(data) ? data : data.data || data.list || data.items || []);
    } catch (err) {
      alert('❌ API 인벤토리 불러오기 실패: ' + err.message);
      setApiInventoryList([]);
    } finally {
      setLoadingApiInventory(false);
    }
  };

  // 선택한 API 인벤토리를 작업대상으로 저장
  const saveSelectedApiInventory = async (item) => {
    try {
      // 선택한 항목을 INI 형식으로 변환
      const inventoryContent = item.hosts
        ? (Array.isArray(item.hosts) ? item.hosts.join('\n') : item.hosts)
        : `[${item.name || 'ungrouped'}]\n${item.ip || item.host || item.address || ''}`;

      const res = await fetch(`${API_URL}/inventories`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: item.name || item.id || 'API-Import-' + Date.now(),
          content: inventoryContent
        })
      });
      const saved = await res.json();
      alert(`✅ 작업대상 저장됨: ${saved.name} (ID: ${saved.id})`);
      setShowApiModal(false);
      setSelectedApiItems([]);
      // 인벤토리 목록 새로고침
      window.location.reload();
    } catch (err) {
      alert('❌ 작업대상 저장 실패: ' + err.message);
    }
  };

  const createAwxTemplate = async () => {
    if (!selectedPlaybook || !selectedInventory) {
      alert('플레이북과 인벤토리를 모두 선택하세요');
      return;
    }

    setCreatingTemplate(true);
    try {
      const res = await fetch(`${API_URL}/awx/create-template`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          playbook_id: selectedPlaybook,
          inventory_id: selectedInventory,
          awx_url: awxConfig.url
        })
      });

      const result = await res.json();

      if (!res.ok) {
        alert(`❌ 오류: ${result.detail || '템플릿 생성 실패'}`);
        return;
      }

      if (result.status === 'success') {
        alert(`✅ Job 템플릿 생성 완료!\n\n이름: ${result.template_name}\n템플릿 ID: ${result.template_id}\n\n인벤토리가 그룹과 함께 생성되었습니다!`);
        setAwxConfig({ ...awxConfig, template_id: result.template_id });
        loadAwxTemplates();

        if (result.template_url) {
          window.open(result.template_url, '_blank');
        }
      } else if (result.status === 'setup_required') {
        alert(`⚠️ 설정 필요\n\n${result.instructions}`);
      }
    } catch (err) {
      alert('❌ AWX 템플릿 생성 실패: ' + err.message);
    } finally {
      setCreatingTemplate(false);
    }
  };

  const launchAwxJob = async () => {
    if (!selectedPlaybook || !selectedInventory) {
      alert('플레이북과 인벤토리를 모두 선택하세요');
      return;
    }
    if (!awxConfig.template_id) {
      alert('Job 템플릿을 먼저 선택하거나 생성하세요');
      return;
    }

    try {
      const res = await fetch(`${API_URL}/awx/launch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          playbook_id: selectedPlaybook,
          inventory_id: selectedInventory,
          awx_url: awxConfig.url,
          job_template_id: awxConfig.template_id
        })
      });
      const result = await res.json();

      if (result.status === 'success') {
        alert(`✅ AWX Job 실행됨!\n\nJob ID: ${result.awx_job_id}`);
        if (result.awx_job_url) {
          // OIDC 리디렉션 엔드포인트를 통해 AWX Job 페이지 열기
          const redirectUrl = `${API_URL}/awx/oidc-redirect?job_url=${encodeURIComponent(result.awx_job_url)}`;
          window.open(redirectUrl, '_blank');
        }
      }
    } catch (err) {
      alert('❌ AWX Job 실행 실패: ' + err.message);
    }
  };

  const checkExecutorStatus = async () => {
    try {
      const params = new URLSearchParams({
        awx_url: awxConfig.url
      });

      const res = await fetch(`${API_URL}/awx/check-executor?${params}`);
      const data = await res.json();
      setExecutorStatus(data);

      if (data.status === 'ready') {
        alert('✅ Executor 플레이북이 준비되었습니다!');
      } else {
        alert('⚠️ Executor 설정이 필요합니다. 위의 안내를 참조하세요.');
      }
    } catch (err) {
      alert('❌ Executor 상태 확인 실패');
    }
  };

  return (
    <div className="space-y-6">
      {/* Local Execution */}
      {(mode === 'local' || mode === 'both') && (
        <div className="bg-white rounded-lg shadow-lg p-6">
          <h2 className="text-2xl font-bold mb-6">플레이북 실행 (로컬)</h2>

          <div className="mb-4">
            <div className="flex justify-between items-center mb-2">
              <label className="block text-sm font-medium">작업 선택</label>
              {onNavigate && (
                <button
                  onClick={() => onNavigate('builder')}
                  className="text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1"
                >
                  <Plus size={14} />
                  작업 생성
                </button>
              )}
            </div>
            <select
              value={selectedPlaybook || ''}
              onChange={(e) => setSelectedPlaybook(e.target.value)}
              className="w-full px-3 py-2 border rounded focus:ring-2 focus:ring-blue-500 focus:outline-none"
            >
              <option value="">-- 작업 선택 --</option>
              {playbooks.map(pb => (
                <option key={pb.id} value={pb.id}>{pb.name} (ID: {pb.id})</option>
              ))}
            </select>
          </div>

          <div className="mb-4">
            <label className="block text-sm font-medium mb-2">작업 대상 선택</label>
            <select
              value={selectedInventory || ''}
              onChange={(e) => setSelectedInventory(e.target.value)}
              className="w-full px-3 py-2 border rounded focus:ring-2 focus:ring-blue-500 focus:outline-none"
            >
              <option value="">-- 작업대상 선택 --</option>
              {inventories.map(inv => (
                <option key={inv.id} value={inv.id}>{inv.name} (ID: {inv.id})</option>
              ))}
            </select>
          </div>

          <button
            onClick={executePlaybook}
            className="w-full px-6 py-3 bg-green-600 text-white rounded hover:bg-green-700 flex items-center justify-center gap-2 font-medium"
          >
            <Play size={20} />
            로컬 실행
          </button>
        </div>
      )}

      {/* AWX Execution */}
      {(mode === 'remote' || mode === 'both') && (
        <div className="bg-white rounded-lg shadow-lg p-6">
          <h2 className="text-2xl font-bold mb-6">GAIA를 통한 실행</h2>

          {/* Executor Status Warning */}
          {executorStatus?.status === 'setup_required' && (
            <div className="bg-yellow-50 border-l-4 border-yellow-500 p-6 mb-6 rounded-lg">
              <div className="flex items-start">
                <div className="flex-shrink-0">
                  <svg className="h-6 w-6 text-yellow-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                </div>
                <div className="ml-3 flex-1">
                  <h3 className="text-lg font-bold text-yellow-800 mb-2">⚙️ 초기 설정 필요</h3>
                  <p className="text-sm text-yellow-700 mb-3">
                    동적 플레이북 실행을 위해 AWX 프로젝트에 executor 플레이북을 추가하세요.
                  </p>

                  <div className="bg-white border border-yellow-200 rounded p-4 mb-3">
                    <h4 className="font-semibold text-yellow-800 mb-2">설정 안내:</h4>
                    <pre className="text-xs bg-gray-50 p-3 rounded overflow-x-auto whitespace-pre-wrap text-gray-800">
                      {executorStatus.instructions}
                    </pre>
                  </div>

                  <details className="bg-white border border-yellow-200 rounded p-4 mb-3">
                    <summary className="font-semibold text-yellow-800 cursor-pointer">
                      📄 플레이북 내용 보기
                    </summary>
                    <pre className="text-xs bg-gray-900 text-green-400 p-3 rounded overflow-x-auto mt-2 max-h-96 overflow-y-auto font-mono">
                      {executorStatus.playbook_content}
                    </pre>
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(executorStatus.playbook_content);
                        alert('✅ 플레이북 내용이 클립보드에 복사되었습니다!');
                      }}
                      className="mt-2 px-4 py-2 bg-yellow-600 text-white rounded hover:bg-yellow-700 text-sm"
                    >
                      📋 클립보드에 복사
                    </button>
                  </details>

                  <button
                    onClick={checkExecutorStatus}
                    className="px-4 py-2 bg-yellow-600 text-white rounded hover:bg-yellow-700 flex items-center gap-2"
                  >
                    <RefreshCw size={18} />
                    상태 다시 확인
                  </button>
                </div>
              </div>
            </div>
          )}

          <div className="mb-6">
            <label className="block text-sm font-medium mb-2">실행 환경</label>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setSelectedEnv('dev')}
                className={`flex-1 px-4 py-3 rounded-lg text-center font-medium transition ${selectedEnv === 'dev'
                  ? 'bg-blue-600 text-white shadow-md'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
              >
                🔧 개발
              </button>
              <button
                onClick={() => setSelectedEnv('prod')}
                className={`flex-1 px-4 py-3 rounded-lg text-center font-medium transition ${selectedEnv === 'prod'
                  ? 'bg-orange-600 text-white shadow-md'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
              >
                🚀 운영
              </button>
            </div>
            <p className="mt-2 text-sm text-gray-600">
              ✓ GAIA 인증은 Keycloak SSO를 통해 자동으로 처리됩니다
            </p>
          </div>

          <div className="mb-4">
            <div className="flex justify-between items-center mb-2">
              <label className="block text-sm font-medium">작업 선택</label>
              {onNavigate && (
                <button
                  onClick={() => onNavigate('builder')}
                  className="text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1"
                >
                  <Plus size={14} />
                  작업 생성
                </button>
              )}
            </div>
            <select
              value={selectedPlaybook || ''}
              onChange={(e) => setSelectedPlaybook(e.target.value)}
              className="w-full px-3 py-2 border rounded focus:ring-2 focus:ring-blue-500 focus:outline-none"
            >
              <option value="">-- 작업 선택 --</option>
              {playbooks.map(pb => (
                <option key={pb.id} value={pb.id}>{pb.name} (ID: {pb.id})</option>
              ))}
            </select>
          </div>

          <div className="mb-6">
            <label className="block text-sm font-medium mb-2">작업 대상 선택</label>

            <div className="flex gap-2 mb-3">
              <select
                value={selectedInventory || ''}
                onChange={(e) => setSelectedInventory(e.target.value)}
                className="flex-1 px-3 py-2 border rounded focus:ring-2 focus:ring-blue-500 focus:outline-none"
              >
                <option value="">-- 작업대상 선택 --</option>
                {inventories.map(inv => (
                  <option key={inv.id} value={inv.id}>{inv.name} (ID: {inv.id})</option>
                ))}
              </select>
              <button
                onClick={loadApiInventories}
                disabled={loadingApiInventory}
                className="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 flex items-center gap-2"
              >
                {loadingApiInventory ? <Loader className="animate-spin" size={16} /> : <ExternalLink size={16} />}
                API로 불러오기
              </button>
            </div>
          </div>

          <div className="mb-6 pb-6 border-b">
            <button
              onClick={createAwxTemplate}
              disabled={creatingTemplate || executorStatus?.status === 'setup_required'}
              className={`w-full px-6 py-3 text-white rounded flex items-center justify-center gap-2 font-medium ${executorStatus?.status === 'setup_required' || creatingTemplate
                ? 'bg-gray-400 cursor-not-allowed'
                : 'bg-indigo-600 hover:bg-indigo-700'
                }`}
            >
              {creatingTemplate ? (
                <>
                  <Loader className="animate-spin" size={20} />
                  템플릿 생성 중...
                </>
              ) : executorStatus?.status === 'setup_required' ? (
                <>
                  <span>⚠️</span>
                  설정 필요 (위 참조)
                </>
              ) : (
                <>
                  <Plus size={20} />
                  AWX에 Job 템플릿 생성
                </>
              )}
            </button>
            <p className="text-xs text-gray-600 mt-2 text-center">
              이 버튼을 클릭하면 AWX에 새 Job 템플릿, 프로젝트, 인벤토리가 자동으로 생성됩니다
            </p>
          </div>

          <div className="mb-4">
            <label className="block text-sm font-medium mb-2">기존 Job 템플릿</label>
            <div className="flex gap-2">
              <select
                value={awxConfig.template_id || ''}
                onChange={(e) => setAwxConfig({ ...awxConfig, template_id: parseInt(e.target.value) })}
                className="flex-1 px-3 py-2 border rounded focus:ring-2 focus:ring-blue-500 focus:outline-none"
              >
                <option value="">-- 템플릿 선택 --</option>
                {awxTemplates.map(tpl => (
                  <option key={tpl.id} value={tpl.id}>{tpl.name}</option>
                ))}
              </select>
              <button
                onClick={loadAwxTemplates}
                className="px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600 flex items-center gap-2"
              >
                <RefreshCw size={18} />
                새로고침
              </button>
            </div>
          </div>

          <button
            onClick={launchAwxJob}
            className="w-full px-6 py-3 bg-purple-600 text-white rounded hover:bg-purple-700 flex items-center justify-center gap-2 font-medium"
          >
            <Play size={20} />
            AWX에서 Job 실행
          </button>

          <div className="mt-6 p-4 bg-blue-50 border-l-4 border-blue-500 rounded">
            <p className="text-sm text-blue-800">
              <strong>사용 방법:</strong>
            </p>
            <ol className="text-sm text-blue-800 mt-2 ml-4 list-decimal space-y-1">
              <li>플레이북과 인벤토리 선택</li>
              <li>"AWX에 Job 템플릿 생성" 클릭하여 자동 생성</li>
              <li>또는 기존 템플릿 선택 후 "AWX에서 Job 실행" 클릭</li>
            </ol>
          </div>
        </div>
      )}

      {/* API 인벤토리 선택 모달 */}
      {showApiModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-xl font-bold">API 인벤토리 선택</h3>
              <button
                onClick={() => setShowApiModal(false)}
                className="text-gray-500 hover:text-gray-700 text-2xl"
              >
                ×
              </button>
            </div>

            {loadingApiInventory ? (
              <div className="flex items-center justify-center py-12">
                <Loader className="animate-spin mr-2" size={24} />
                <span>API에서 인벤토리 목록을 불러오는 중...</span>
              </div>
            ) : apiInventoryList.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                <p>불러올 인벤토리가 없습니다.</p>
                <p className="text-sm mt-2">API 서버 연결을 확인하세요.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {/* 검색 입력창 */}
                <div className="mb-4">
                  <input
                    type="text"
                    placeholder="호스트명, IP, Zone으로 검색..."
                    value={apiSearchTerm}
                    onChange={(e) => setApiSearchTerm(e.target.value)}
                    className="w-full px-3 py-2 border rounded focus:ring-2 focus:ring-purple-500 focus:outline-none"
                  />
                </div>
                {(() => {
                  const searchLower = apiSearchTerm.toLowerCase();
                  const filteredList = apiSearchTerm.trim() === ''
                    ? apiInventoryList
                    : apiInventoryList.filter(item => {
                      const hostNm = (item.host_nm || item.name || '').toLowerCase();
                      const mgmtIp = (item.mgmt_ip || item.ip || '');
                      const zone = (item.zone || '').toLowerCase();
                      const hostGroup = (item.host_group_nm || '').toLowerCase();
                      return hostNm.includes(searchLower) ||
                        mgmtIp.includes(apiSearchTerm) ||
                        zone.includes(searchLower) ||
                        hostGroup.includes(searchLower);
                    });
                  const displayList = filteredList.slice(0, 100);

                  return (
                    <>
                      <p className="text-sm text-gray-600 mb-4">
                        검색 결과: {filteredList.length}개 중 {displayList.length}개 표시 / 전체 {apiInventoryList.length}개
                      </p>
                      {displayList.map((item, index) => (
                        <div
                          key={item.id || item.equnr || index}
                          className="p-4 border rounded-lg hover:bg-gray-50 cursor-pointer transition flex justify-between items-center"
                        >
                          <div className="flex-1 min-w-0">
                            <p className="font-medium truncate">{item.host_nm || item.name || item.id || `항목 ${index + 1}`}</p>
                            {(item.mgmt_ip || item.ip) && (
                              <p className="text-sm text-gray-500">IP: {item.mgmt_ip || item.ip}</p>
                            )}
                            {item.zone && <p className="text-sm text-gray-500">Zone: {item.zone}</p>}
                            {item.host_group_nm && (
                              <p className="text-sm text-gray-400 truncate">{item.host_group_nm}</p>
                            )}
                          </div>
                          <button
                            onClick={() => saveSelectedApiInventory(item)}
                            className="ml-4 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 text-sm flex-shrink-0"
                          >
                            저장
                          </button>
                        </div>
                      ))}
                    </>
                  );
                })()}
              </div>
            )}

            <div className="flex justify-end mt-6">
              <button
                onClick={() => setShowApiModal(false)}
                className="px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600"
              >
                닫기
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}