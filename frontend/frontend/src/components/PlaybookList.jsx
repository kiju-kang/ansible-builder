import React, { useState } from 'react';
import { Eye, Edit, Trash2, RefreshCw } from 'lucide-react';

const API_URL = '/api';

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
      alert('Failed to load playbook: ' + err.message);
    }
  };

  const generateYAML = (pb) => {
    let yaml = `---\n- name: ${pb.name}\n  hosts: ${pb.hosts}\n`;
    if (pb.become) yaml += `  become: yes\n`;
    yaml += `  tasks:\n`;
    
    pb.tasks.forEach(task => {
      yaml += `    - name: ${task.name || 'Unnamed task'}\n`;
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
          <h2 className="text-2xl font-bold">Saved Playbooks</h2>
          <button 
            onClick={onRefresh}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            <RefreshCw size={18} />
            Refresh
          </button>
        </div>

        <div className="space-y-3">
          {playbooks.map(pb => (
            <div key={pb.id} className="p-4 border rounded hover:bg-gray-50 transition">
              <div className="flex justify-between items-start">
                <div className="flex-1 cursor-pointer" onClick={() => loadPlaybookDetail(pb.id)}>
                  <h3 className="font-bold text-lg">{pb.name}</h3>
                  <p className="text-sm text-gray-600">Hosts: {pb.hosts} | Tasks: {pb.tasks.length}</p>
                  <p className="text-xs text-gray-500">ID: {pb.id}</p>
                </div>
                <div className="flex gap-2">
                  <button 
                    onClick={() => loadPlaybookDetail(pb.id)} 
                    className="p-2 text-blue-600 hover:bg-blue-50 rounded" 
                    title="View"
                  >
                    <Eye size={18} />
                  </button>
                  {/* ⭐ Edit 버튼 수정 */}
                  <button 
                    onClick={() => handleEdit(pb)} 
                    className="p-2 text-green-600 hover:bg-green-50 rounded" 
                    title="Edit"
                  >
                    <Edit size={18} />
                  </button>
                  <button 
                    onClick={() => onDelete(pb.id)} 
                    className="p-2 text-red-600 hover:bg-red-50 rounded" 
                    title="Delete"
                  >
                    <Trash2 size={18} />
                  </button>
                </div>
              </div>
            </div>
          ))}
          {playbooks.length === 0 && (
            <p className="text-gray-500 text-center py-8">No saved playbooks</p>
          )}
        </div>
      </div>

      {viewingPlaybook && (
        <div className="bg-white rounded-lg shadow-lg p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-2xl font-bold">Playbook Detail</h2>
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
              <p><strong>Hosts:</strong> {viewingPlaybook.hosts}</p>
              <p><strong>Become:</strong> {viewingPlaybook.become ? 'Yes' : 'No'}</p>
              <p><strong>Created:</strong> {new Date(viewingPlaybook.created_at).toLocaleString()}</p>
            </div>
          </div>

          <div className="mb-4">
            <h4 className="font-semibold mb-2">Tasks ({viewingPlaybook.tasks.length})</h4>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {viewingPlaybook.tasks.map((task, idx) => (
                <div key={idx} className="p-3 bg-gray-50 rounded border">
                  <p className="font-medium">{idx + 1}. {task.name}</p>
                  <p className="text-sm text-gray-600">Module: {task.module}</p>
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
            <h4 className="font-semibold mb-2">YAML Preview</h4>
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
              Edit This Playbook
            </button>
            <button 
              onClick={() => setViewingPlaybook(null)} 
              className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}