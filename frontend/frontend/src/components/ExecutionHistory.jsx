import React, { useState } from 'react';
import { CheckCircle, XCircle, Loader, Clock, RefreshCw, Filter } from 'lucide-react';

export default function ExecutionHistory({ executions, currentExecution, isExecuting, onRefresh }) {
  const [typeFilter, setTypeFilter] = useState('all'); // 'all', 'local', 'remote'

  const getStatusIcon = (status) => {
    if (status === 'completed') return <CheckCircle className="text-green-600" size={20} />;
    if (status === 'failed' || status === 'error') return <XCircle className="text-red-600" size={20} />;
    if (status === 'running') return <Loader className="text-blue-600 animate-spin" size={20} />;
    return <Clock className="text-yellow-600" size={20} />;
  };

  const getStatusBadge = (status) => {
    const badges = {
      'completed': 'bg-green-100 text-green-800',
      'failed': 'bg-red-100 text-red-800',
      'error': 'bg-red-100 text-red-800',
      'running': 'bg-blue-100 text-blue-800',
      'pending': 'bg-yellow-100 text-yellow-800'
    };

    return badges[status] || 'bg-gray-100 text-gray-800';
  };

  // 필터링된 실행 목록
  const filteredExecutions = executions.filter(exec => {
    if (typeFilter === 'all') return true;
    if (typeFilter === 'local') return exec.execution_type !== 'remote';
    if (typeFilter === 'remote') return exec.execution_type === 'remote';
    return true;
  });

  return (
    <div className="bg-white rounded-lg shadow-lg p-6">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold">실행 이력</h2>
        <div className="flex items-center gap-3">
          {/* 필터 버튼 그룹 */}
          <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
            <button
              onClick={() => setTypeFilter('all')}
              className={`px-3 py-1.5 text-sm rounded-md transition ${typeFilter === 'all'
                ? 'bg-white text-gray-900 shadow-sm font-medium'
                : 'text-gray-600 hover:text-gray-900'
                }`}
            >
              전체
            </button>
            <button
              onClick={() => setTypeFilter('local')}
              className={`px-3 py-1.5 text-sm rounded-md transition flex items-center gap-1 ${typeFilter === 'local'
                ? 'bg-white text-gray-900 shadow-sm font-medium'
                : 'text-gray-600 hover:text-gray-900'
                }`}
            >
              💻 로컬
            </button>
            <button
              onClick={() => setTypeFilter('remote')}
              className={`px-3 py-1.5 text-sm rounded-md transition flex items-center gap-1 ${typeFilter === 'remote'
                ? 'bg-white text-purple-700 shadow-sm font-medium'
                : 'text-gray-600 hover:text-gray-900'
                }`}
            >
              ☁️ GAIA
            </button>
          </div>
          <button
            onClick={onRefresh}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            <RefreshCw size={18} />
            새로고침
          </button>
        </div>
      </div>

      {isExecuting && currentExecution && (
        <div className="mb-4 p-4 bg-blue-50 border-l-4 border-blue-500 rounded">
          <div className="flex items-center gap-2">
            <Loader className="animate-spin text-blue-600" size={20} />
            <span className="font-medium text-blue-800">
              실행 중... (ID: {currentExecution})
            </span>
          </div>
        </div>
      )}

      <div className="space-y-4">
        {filteredExecutions.map(exec => (
          <div
            key={exec.id}
            className={`border rounded-lg p-4 transition ${exec.id === currentExecution && isExecuting
              ? 'border-blue-500 bg-blue-50 shadow-md'
              : 'hover:shadow-md'
              }`}
          >
            {/* Header */}
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-3">
                {getStatusIcon(exec.status)}
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-lg">실행 #{exec.id}</span>
                    <span className={`px-2 py-1 rounded text-xs font-semibold ${getStatusBadge(exec.status)}`}>
                      {exec.status.toUpperCase()}
                    </span>
                    {/* 실행 유형 배지 */}
                    <span className={`px-2 py-1 rounded text-xs font-semibold ${exec.execution_type === 'remote'
                      ? 'bg-purple-100 text-purple-800'
                      : 'bg-gray-100 text-gray-800'
                      }`}>
                      {exec.execution_type === 'remote' ? '☁️ GAIA' : '💻 로컬'}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600">
                    작업: {exec.playbook_id} | 작업대상: {exec.inventory_id}
                  </p>
                </div>
              </div>

              {exec.return_code !== null && (
                <div className="text-right">
                  <p className="text-sm font-semibold">반환 코드</p>
                  <p className={`text-2xl font-bold ${exec.return_code === 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {exec.return_code}
                  </p>
                </div>
              )}
            </div>

            {/* Timestamps */}
            <div className="grid grid-cols-2 gap-4 mb-3 text-sm">
              {exec.started_at && (
                <div>
                  <p className="text-gray-600">시작</p>
                  <p className="font-medium">{new Date(exec.started_at).toLocaleString()}</p>
                </div>
              )}
              {exec.ended_at && (
                <div>
                  <p className="text-gray-600">종료</p>
                  <p className="font-medium">{new Date(exec.ended_at).toLocaleString()}</p>
                </div>
              )}
            </div>

            {/* Duration */}
            {exec.started_at && exec.ended_at && (
              <div className="mb-3 text-sm">
                <p className="text-gray-600">소요 시간</p>
                <p className="font-medium">
                  {Math.round((new Date(exec.ended_at) - new Date(exec.started_at)) / 1000)}s
                </p>
              </div>
            )}

            {/* Output */}
            {exec.output && (
              <details className="mt-3" open={exec.id === currentExecution && isExecuting}>
                <summary className="cursor-pointer font-semibold text-sm mb-2 hover:text-blue-600">
                  📋 출력 보기 ({exec.output.split('\n').length}줄)
                </summary>
                <div className="mt-2">
                  <pre className="p-3 bg-gray-900 text-green-400 rounded text-xs overflow-x-auto max-h-96 overflow-y-auto font-mono whitespace-pre-wrap">
                    {exec.output}
                  </pre>
                </div>
              </details>
            )}

            {/* Error */}
            {exec.error && (
              <details className="mt-3" open>
                <summary className="cursor-pointer font-semibold text-sm mb-2 text-red-700 hover:text-red-800">
                  ❌ 오류 상세
                </summary>
                <div className="mt-2">
                  <pre className="p-3 bg-red-100 rounded text-xs overflow-x-auto text-red-800 font-mono whitespace-pre-wrap">
                    {exec.error}
                  </pre>
                </div>
              </details>
            )}

            {/* Live Status Indicator */}
            {exec.id === currentExecution && isExecuting && (
              <div className="mt-3 flex items-center gap-2 text-sm text-blue-700 font-medium animate-pulse">
                <span className="inline-block w-2 h-2 bg-blue-600 rounded-full"></span>
                실시간 실행 중...
              </div>
            )}
          </div>
        ))}

        {executions.length === 0 && (
          <div className="text-center py-12">
            <Clock className="mx-auto text-gray-400 mb-4" size={48} />
            <p className="text-gray-500 text-lg">실행 이력이 없습니다</p>
            <p className="text-gray-400 text-sm mt-2">플레이북을 실행하면 결과가 여기에 표시됩니다</p>
          </div>
        )}
      </div>
    </div>
  );
}