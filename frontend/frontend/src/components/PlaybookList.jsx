import React, { useState } from 'react';
import { Eye, Edit, Trash2, RefreshCw } from 'lucide-react';

// 환경 변수에서 API URL 읽기 (Vite: import.meta.env)
const API_URL = import.meta.env.VITE_API_URL || '/api';

export default function PlaybookList({ playbooks, onEdit, onDelete, onRefresh, onNavigate }) {
  const [viewingPlaybook, setViewingPlaybook] = useState(null);

  const loadPlaybookDetail = async (id) => {
    try {
      const res = await fetch(`${API_URL}/playbooks/${id}`);
      const data = await res.json();
      setViewingPlaybook(data);
    } catch (err) {
      console.error('Failed to load playbook detail:', err);
    }
  };

  // ⭐ Edit 버튼 핸들러 수정
  const handleEdit = async (pb) => {
    try {
      // 최신 데이터 로드
      const res = await fetch(`${API_URL}/playbooks/${pb.id}`);
      const fullPlaybook = await res.json();

      // Builder로 이동하면서 데이터 전달
      if (onNavigate) {
        onNavigate('builder', { editingPlaybook: fullPlaybook });
      } else if (onEdit) {
        // 하위 호환성
        onEdit(fullPlaybook);
      }
    } catch (err) {
      alert('플레이북 로드 실패: ' + err.message);
    }
  };

  const generateYAML = (pb) => {
    let yaml = `---\n- name: ${pb.name}\n  hosts: ${pb.hosts}\n`;
    if (pb.become) yaml += `  become: yes\n`;
    yaml += `  tasks:\n`;

    pb.tasks.forEach(task => {
      yaml += `    - name: ${task.name || '이름 없는 작업'}\n`;
      yaml += `      ${task.module}:\n`;
      Object.entries(task.params).forEach(([key, value]) => {
        if (value) yaml += `        ${key}: ${value}\n`;
      });
    });

    return yaml;
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div className="bg-white rounded-lg shadow-lg p-6">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-2xl font-bold">저장된 작업목록</h2>
          <button
            onClick={onRefresh}
            className="flex items-center gap-2 px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600"
          >
            <RefreshCw size={18} />
            새로고침
          </button>
        </div>

        <div className="space-y-3">
          {playbooks.map(pb => (
            <div key={pb.id} className="p-4 border rounded hover:bg-gray-50 transition">
              <div className="flex justify-between items-start">
                <div className="flex-1 cursor-pointer" onClick={() => loadPlaybookDetail(pb.id)}>
                  <h3 className="font-bold text-lg">{pb.name}</h3>
                  <p className="text-sm text-gray-600">작업 대상: {pb.hosts} | 작업: {pb.tasks.length}개</p>
                  <p className="text-xs text-gray-500">ID: {pb.id}</p>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => loadPlaybookDetail(pb.id)}
                    className="p-2 text-blue-600 hover:bg-blue-50 rounded"
                    title="보기"
                  >
                    <Eye size={18} />
                  </button>
                  {/* ⭐ Edit 버튼 수정 */}
                  <button
                    onClick={() => handleEdit(pb)}
                    className="p-2 text-green-600 hover:bg-green-50 rounded"
                    title="수정"
                  >
                    <Edit size={18} />
                  </button>
                  <button
                    onClick={() => onDelete(pb.id)}
                    className="p-2 text-red-600 hover:bg-red-50 rounded"
                    title="삭제"
                  >
                    <Trash2 size={18} />
                  </button>
                </div>
              </div>
            </div>
          ))}
          {playbooks.length === 0 && (
            <p className="text-gray-500 text-center py-8">저장된 작업목록이 없습니다</p>
          )}
        </div>
      </div>

      {viewingPlaybook && (
        <div className="bg-white rounded-lg shadow-lg p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-2xl font-bold">작업 상세</h2>
            <button
              onClick={() => setViewingPlaybook(null)}
              className="text-gray-500 hover:text-gray-700 text-2xl"
            >
              ✕
            </button>
          </div>

          <div className="mb-4 space-y-2">
            <h3 className="font-bold text-lg">{viewingPlaybook.name}</h3>
            <div className="text-sm text-gray-600 space-y-1">
              <p><strong>ID:</strong> {viewingPlaybook.id}</p>
              <p><strong>작업 대상:</strong> {viewingPlaybook.hosts}</p>
              <p><strong>권한 상승:</strong> {viewingPlaybook.become ? '예' : '아니오'}</p>
              <p><strong>생성일:</strong> {new Date(viewingPlaybook.created_at).toLocaleString()}</p>
            </div>
          </div>

          <div className="mb-4">
            <h4 className="font-semibold mb-2">작업 ({viewingPlaybook.tasks.length}개)</h4>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {viewingPlaybook.tasks.map((task, idx) => (
                <div key={idx} className="p-3 bg-gray-50 rounded border">
                  <p className="font-medium">{idx + 1}. {task.name}</p>
                  <p className="text-sm text-gray-600">모듈: {task.module}</p>
                  <div className="text-xs text-gray-500 mt-1">
                    {Object.entries(task.params).map(([k, v]) => v && (
                      <div key={k}>{k}: {v}</div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div>
            <h4 className="font-semibold mb-2">YAML 미리보기</h4>
            <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-x-auto text-xs max-h-96 overflow-y-auto font-mono">
              {generateYAML(viewingPlaybook)}
            </pre>
          </div>

          {/* ⭐ Detail 뷰에서도 Edit 가능 */}
          <div className="mt-4 flex gap-2">
            <button
              onClick={() => handleEdit(viewingPlaybook)}
              className="flex-1 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
            >
              이 작업 수정
            </button>
            <button
              onClick={() => setViewingPlaybook(null)}
              className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700"
            >
              닫기
            </button>
          </div>
        </div>
      )}
    </div>
  );
}