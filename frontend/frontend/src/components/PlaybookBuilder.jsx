import React, { useState, useEffect, useRef } from 'react';
import { Plus, Trash2, Download, Save, Upload, FileText, MoreVertical } from 'lucide-react';

// 환경 변수에서 API URL 읽기 (Vite: import.meta.env)
const API_URL = import.meta.env.VITE_API_URL || '/api';

const moduleTemplates = {
  'apt': {
    name: '',
    state: 'present',
    update_cache: 'no',
    cache_valid_time: '',
    force: 'no',
    install_recommends: 'yes',
    autoremove: 'no',
    autoclean: 'no'
  },
  'yum': {
    name: '',
    state: 'present',
    disable_gpg_check: 'no',
    enablerepo: '',
    disablerepo: '',
    update_cache: 'no'
  },
  'copy': {
    src: '',
    dest: '',
    mode: '0644',
    owner: '',
    group: '',
    backup: 'no',
    force: 'yes',
    remote_src: 'no'
  },
  'file': {
    path: '',
    state: 'file',
    mode: '',
    owner: '',
    group: '',
    recurse: 'no',
    force: 'no'
  },
  'service': {
    name: '',
    state: 'started',
    enabled: 'no',
    daemon_reload: 'no',
    pattern: ''
  },
  'command': {
    cmd: '',
    chdir: '',
    creates: '',
    removes: ''
  },
  'shell': {
    cmd: '',
    chdir: '',
    creates: '',
    removes: ''
  },
  'template': {
    src: '',
    dest: '',
    mode: '0644',
    owner: '',
    group: '',
    backup: 'no',
    force: 'yes'
  },
  'user': {
    name: '',
    state: 'present',
    uid: '',
    group: '',
    groups: '',
    shell: '/bin/bash',
    home: '',
    create_home: 'yes',
    password: '',
    append: 'no',
    remove: 'no'
  },
  'git': {
    repo: '',
    dest: '',
    version: 'HEAD',
    force: 'no',
    update: 'yes',
    depth: '',
    clone: 'yes',
    accept_hostkey: 'no'
  },
  'package': {
    name: '',
    state: 'present'
  }
};

// Parameter field types and options
const parameterFieldTypes = {
  'apt': {
    state: { type: 'select', options: ['present', 'absent', 'latest'] },
    update_cache: { type: 'select', options: ['yes', 'no'] },
    force: { type: 'select', options: ['yes', 'no'] },
    install_recommends: { type: 'select', options: ['yes', 'no'] },
    autoremove: { type: 'select', options: ['yes', 'no'] },
    autoclean: { type: 'select', options: ['yes', 'no'] }
  },
  'yum': {
    state: { type: 'select', options: ['present', 'absent', 'latest', 'installed', 'removed'] },
    disable_gpg_check: { type: 'select', options: ['yes', 'no'] },
    update_cache: { type: 'select', options: ['yes', 'no'] }
  },
  'copy': {
    backup: { type: 'select', options: ['yes', 'no'] },
    force: { type: 'select', options: ['yes', 'no'] },
    remote_src: { type: 'select', options: ['yes', 'no'] }
  },
  'file': {
    state: { type: 'select', options: ['file', 'directory', 'link', 'hard', 'touch', 'absent'] },
    recurse: { type: 'select', options: ['yes', 'no'] },
    force: { type: 'select', options: ['yes', 'no'] }
  },
  'service': {
    state: { type: 'select', options: ['started', 'stopped', 'restarted', 'reloaded'] },
    enabled: { type: 'select', options: ['yes', 'no'] },
    daemon_reload: { type: 'select', options: ['yes', 'no'] }
  },
  'template': {
    backup: { type: 'select', options: ['yes', 'no'] },
    force: { type: 'select', options: ['yes', 'no'] }
  },
  'user': {
    state: { type: 'select', options: ['present', 'absent'] },
    create_home: { type: 'select', options: ['yes', 'no'] },
    append: { type: 'select', options: ['yes', 'no'] },
    remove: { type: 'select', options: ['yes', 'no'] }
  },
  'git': {
    force: { type: 'select', options: ['yes', 'no'] },
    update: { type: 'select', options: ['yes', 'no'] },
    clone: { type: 'select', options: ['yes', 'no'] },
    accept_hostkey: { type: 'select', options: ['yes', 'no'] }
  },
  'package': {
    state: { type: 'select', options: ['present', 'absent', 'latest'] }
  }
};

export default function PlaybookBuilder({ onSave, onNavigate, editingPlaybook }) {
  const [playbook, setPlaybook] = useState({
    name: '내 플레이북',
    hosts: 'all',
    become: false,
    tasks: []
  });

  const [isEditMode, setIsEditMode] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [showScriptModal, setShowScriptModal] = useState(false);
  const [importText, setImportText] = useState('');
  const [scriptText, setScriptText] = useState('');
  const [scriptName, setScriptName] = useState('');

  // Syntax validation states
  const [yamlValidation, setYamlValidation] = useState(null);
  const [scriptValidation, setScriptValidation] = useState(null);
  const [isValidatingYaml, setIsValidatingYaml] = useState(false);
  const [isValidatingScript, setIsValidatingScript] = useState(false);

  // 햄버거 메뉴 상태
  const [showHamburgerMenu, setShowHamburgerMenu] = useState(false);
  const yamlFileRef = useRef(null);
  const scriptFileRef = useRef(null);
  const menuRef = useRef(null);

  // 메뉴 외부 클릭 시 닫기
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setShowHamburgerMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // ⭐ editingPlaybook prop 감지
  useEffect(() => {
    if (editingPlaybook) {
      console.log('Loading playbook for edit:', editingPlaybook);
      setPlaybook({
        id: editingPlaybook.id,
        name: editingPlaybook.name,
        hosts: editingPlaybook.hosts,
        become: editingPlaybook.become,
        tasks: editingPlaybook.tasks
      });
      setIsEditMode(true);
    } else {
      resetBuilder();
    }
  }, [editingPlaybook]);

  const resetBuilder = () => {
    setPlaybook({
      name: '내 플레이북',
      hosts: 'all',
      become: false,
      tasks: []
    });
    setIsEditMode(false);
  };

  const addTask = () => {
    setPlaybook({
      ...playbook,
      tasks: [...playbook.tasks, { name: '', module: 'apt', params: { ...moduleTemplates.apt } }]
    });
  };

  const removeTask = (index) => {
    setPlaybook({
      ...playbook,
      tasks: playbook.tasks.filter((_, i) => i !== index)
    });
  };

  const updateTask = (index, field, value) => {
    setPlaybook(prevPlaybook => {
      const newTasks = [...prevPlaybook.tasks];
      if (field === 'module') {
        newTasks[index] = {
          ...newTasks[index],
          module: value,
          params: { ...moduleTemplates[value] }
        };
      } else if (field === 'taskName') {
        newTasks[index] = {
          ...newTasks[index],
          name: value
        };
      } else {
        newTasks[index] = {
          ...newTasks[index],
          params: {
            ...newTasks[index].params,
            [field]: value
          }
        };
      }
      return { ...prevPlaybook, tasks: newTasks };
    });
  };

  const generateYAML = () => {
    let yaml = `---\n- name: ${playbook.name}\n  hosts: ${playbook.hosts}\n`;
    if (playbook.become) yaml += `  become: yes\n`;
    yaml += `  tasks:\n`;

    playbook.tasks.forEach(task => {
      yaml += `    - name: ${task.name || '이름 없는 작업'}\n`;
      yaml += `      ${task.module}:\n`;

      Object.entries(task.params).forEach(([key, value]) => {
        if (!value) return;

        if ((task.module === "shell" || task.module === "command") && key === "cmd") {
          const lines = value.split("\n").map(l => `          ${l}`).join("\n");
          yaml += `        ${key}: |\n${lines}\n`;
        } else {
          yaml += `        ${key}: ${value}\n`;
        }
      });
    });

    return yaml;
  };

  const savePlaybook = async () => {
    try {
      let res;

      if (isEditMode && playbook.id) {
        // ⭐ 수정 모드: PUT
        res = await fetch(`${API_URL}/playbooks/${playbook.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: playbook.name,
            hosts: playbook.hosts,
            become: playbook.become,
            tasks: playbook.tasks
          })
        });
      } else {
        // ⭐ 생성 모드: POST
        res = await fetch(`${API_URL}/playbooks`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(playbook)
        });
      }

      const saved = await res.json();
      alert(`✅ 플레이북 ${isEditMode ? '수정됨' : '저장됨'}: ${saved.name} (ID: ${saved.id})`);

      if (onSave) onSave();
      if (onNavigate) onNavigate('playbooks');

      resetBuilder();

    } catch (err) {
      alert(`❌ 플레이북 ${isEditMode ? '수정' : '저장'} 실패`);
    }
  };

  const downloadPlaybook = () => {
    const yaml = generateYAML();
    const blob = new Blob([yaml], { type: 'text/yaml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${playbook.name.replace(/\s+/g, '_')}.yml`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const importYamlFile = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    try {
      // Read file content first
      const fileContent = await file.text();

      // Validate YAML syntax before importing
      const validateRes = await fetch(`${API_URL}/playbooks/validate-yaml`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: fileContent })
      });
      const validationResult = await validateRes.json();

      if (!validationResult.valid) {
        let errorMessage = `❌ YAML Syntax Error in "${file.name}":\n\n${validationResult.error}`;
        if (validationResult.line) {
          errorMessage += `\n\nLine: ${validationResult.line}`;
          if (validationResult.column) {
            errorMessage += `, Column: ${validationResult.column}`;
          }
        }
        alert(errorMessage);
        event.target.value = '';
        return;
      }

      // Proceed with import if validation passed
      const formData = new FormData();
      formData.append('file', file);

      const res = await fetch(`${API_URL}/playbooks/import`, {
        method: 'POST',
        body: formData
      });
      const result = await res.json();

      if (result.status === 'success') {
        result.playbook.tasks = normalizeImportedTasks(result.playbook.tasks);
        setPlaybook(result.playbook);
        setIsEditMode(false); // Import는 새 playbook

        if (onSave) onSave();
        if (onNavigate) onNavigate('playbooks');
      } else {
        alert('❌ 가져오기 실패: ' + result.detail);
      }
    } catch (err) {
      alert('❌ 가져오기 실패: ' + err.message);
    }

    event.target.value = '';
  };

  function normalizeImportedTasks(tasks) {
    return tasks.map(task => {
      if (!task.params) return task;

      if (task.params.cmd && task.params.cmd.includes("\n")) {
        task.params.cmd = `|\n` + task.params.cmd
          .split("\n")
          .map(line => "      " + line)
          .join("\n");
      }

      return task;
    });
  }

  const importYamlText = async () => {
    if (!importText.trim()) {
      alert('YAML 내용을 입력해주세요');
      return;
    }

    try {
      const res = await fetch(`${API_URL}/playbooks/import-text`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: importText })
      });
      const result = await res.json();

      if (result.status === 'success') {
        alert(`✅ 플레이북 가져오기 완료!\n\n이름: ${result.playbook_name}\n작업: ${result.tasks_count}개`);
        setShowImportModal(false);
        setImportText('');
        if (onSave) onSave();
        if (onNavigate) onNavigate('playbooks');
      } else {
        alert('❌ 가져오기 실패: ' + result.detail);
      }
    } catch (err) {
      alert('❌ 가져오기 실패: ' + err.message);
    }
  };

  const importScriptFile = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    try {
      // Read file content first
      const fileContent = await file.text();

      // Validate script syntax before importing
      const validateRes = await fetch(`${API_URL}/playbooks/validate-script`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: fileContent })
      });
      const validationResult = await validateRes.json();

      if (!validationResult.valid) {
        let errorMessage = `❌ Script Syntax Error in "${file.name}":\n\n${validationResult.error}`;
        if (validationResult.line) {
          errorMessage += `\n\nLine: ${validationResult.line}`;
        }
        alert(errorMessage);
        event.target.value = '';
        return;
      }

      // Proceed with import if validation passed
      const formData = new FormData();
      formData.append('file', file);

      const res = await fetch(`${API_URL}/playbooks/import-script`, {
        method: 'POST',
        body: formData
      });
      const result = await res.json();

      if (result.status === 'success') {
        result.playbook.tasks = normalizeImportedTasks(result.playbook.tasks);
        setPlaybook(result.playbook);
        setShowImportModal(false);
        setImportText('');
        setIsEditMode(false); // Import는 새 playbook

        if (onSave) onSave();
        if (onNavigate) onNavigate('playbooks');
      } else {
        alert('❌ Failed to import: ' + result.detail);
      }
    } catch (err) {
      alert('❌ Import failed: ' + err.message);
    }

    event.target.value = '';
  };

  const importScriptText = async () => {
    if (!scriptText.trim()) {
      alert('스크립트 내용을 입력해주세요');
      return;
    }

    try {
      const res = await fetch(`${API_URL}/playbooks/import-script-text`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: scriptName || `Script_Playbook_${Date.now()}`,
          content: scriptText
        })
      });
      const result = await res.json();

      if (result.status === 'success') {
        alert(`✅ 스크립트 변환 완료!\n\n이름: ${result.playbook_name}\n작업: ${result.tasks_count}개`);
        setShowScriptModal(false);
        setScriptText('');
        setScriptName('');
        if (onSave) onSave();
        if (onNavigate) onNavigate('playbooks');
      } else {
        alert('❌ 가져오기 실패: ' + result.detail);
      }
    } catch (err) {
      alert('❌ 가져오기 실패: ' + err.message);
    }
  };

  // Syntax validation functions
  const validateYaml = async () => {
    if (!importText.trim()) {
      setYamlValidation({ valid: false, error: 'YAML 내용을 입력해주세요' });
      return;
    }

    setIsValidatingYaml(true);
    setYamlValidation(null);

    try {
      const res = await fetch(`${API_URL}/playbooks/validate-yaml`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: importText })
      });
      const result = await res.json();
      setYamlValidation(result);
    } catch (err) {
      setYamlValidation({ valid: false, error: '검증 요청 실패: ' + err.message });
    } finally {
      setIsValidatingYaml(false);
    }
  };

  const validateScript = async () => {
    if (!scriptText.trim()) {
      setScriptValidation({ valid: false, error: '스크립트 내용을 입력해주세요' });
      return;
    }

    setIsValidatingScript(true);
    setScriptValidation(null);

    try {
      const res = await fetch(`${API_URL}/playbooks/validate-script`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: scriptText })
      });
      const result = await res.json();
      setScriptValidation(result);
    } catch (err) {
      setScriptValidation({ valid: false, error: '검증 요청 실패: ' + err.message });
    } finally {
      setIsValidatingScript(false);
    }
  };

  // Reset validation when modal closes or text changes
  const handleYamlTextChange = (e) => {
    setImportText(e.target.value);
    setYamlValidation(null);
  };

  const handleScriptTextChange = (e) => {
    setScriptText(e.target.value);
    setScriptValidation(null);
  };

  const handleCloseImportModal = () => {
    setShowImportModal(false);
    setYamlValidation(null);
  };

  const handleCloseScriptModal = () => {
    setShowScriptModal(false);
    setScriptValidation(null);
  };

  return (
    <>
      <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
        <div className="flex justify-between items-center mb-6">
          <div>
            <h2 className="text-2xl font-bold">
              {isEditMode ? `✏️ 수정: ${playbook.name}` : '플레이북 생성기'}
            </h2>
            {isEditMode && (
              <p className="text-sm text-gray-600 mt-1">
                플레이북 ID: {playbook.id} 수정 중
              </p>
            )}
          </div>
          <div className="flex gap-2 items-center">
            {isEditMode && (
              <button
                onClick={resetBuilder}
                className="flex items-center gap-2 px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600"
              >
                <Plus size={20} />
                새 작업
              </button>
            )}
            <button onClick={downloadPlaybook} className="flex items-center gap-2 px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600">
              <Download size={20} />
              다운로드
            </button>

            {/* 햄버거 메뉴 */}
            <div className="relative" ref={menuRef}>
              <button
                onClick={() => setShowHamburgerMenu(!showHamburgerMenu)}
                className="flex items-center justify-center w-10 h-10 bg-gray-500 text-white rounded hover:bg-gray-600"
              >
                <MoreVertical size={20} />
              </button>

              {showHamburgerMenu && (
                <div className="absolute right-0 mt-2 w-56 bg-white rounded-lg shadow-lg border z-50">
                  <div className="py-1">
                    <button
                      onClick={() => {
                        yamlFileRef.current?.click();
                        setShowHamburgerMenu(false);
                      }}
                      className="w-full text-left px-4 py-3 text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-2"
                    >
                      <Upload size={16} />
                      YAML/Script 가져오기
                    </button>
                    <button
                      onClick={() => {
                        setShowImportModal(true);
                        setShowHamburgerMenu(false);
                      }}
                      className="w-full text-left px-4 py-3 text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-2"
                    >
                      <FileText size={16} />
                      YAML/Script 붙여넣기
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Hidden file inputs */}
            <input
              ref={yamlFileRef}
              type="file"
              accept=".yml,.yaml,.sh,.bash,.zsh"
              onChange={(e) => {
                const file = e.target.files[0];
                if (file) {
                  if (file.name.endsWith('.yml') || file.name.endsWith('.yaml')) {
                    importYamlFile(e);
                  } else {
                    importScriptFile(e);
                  }
                }
              }}
              className="hidden"
            />
          </div>
        </div>

        {/* ... 나머지 폼은 동일 ... */}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div>
            <label className="block text-sm font-medium mb-2">플레이북 이름</label>
            <input
              type="text"
              value={playbook.name}
              onChange={(e) => setPlaybook({ ...playbook, name: e.target.value })}
              className="w-full px-3 py-2 border rounded focus:ring-2 focus:ring-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-2">대상 호스트</label>
            <input
              type="text"
              value={playbook.hosts}
              onChange={(e) => setPlaybook({ ...playbook, hosts: e.target.value })}
              className="w-full px-3 py-2 border rounded focus:ring-2 focus:ring-blue-500 focus:outline-none"
            />
          </div>
          <div className="flex items-end">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={playbook.become}
                onChange={(e) => setPlaybook({ ...playbook, become: e.target.checked })}
                className="w-4 h-4"
              />
              <span>권한 상승 (sudo)</span>
            </label>
          </div>
        </div>

        <div className="flex justify-between items-center mb-4">
          <h3 className="text-xl font-semibold">작업 목록</h3>
          <button onClick={addTask} className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
            <Plus size={20} />
            작업 추가
          </button>
        </div>

        <div className="space-y-4">
          {playbook.tasks.map((task, index) => (
            <div key={index} className="border rounded-lg p-4 bg-gray-50">
              <div className="flex justify-between mb-4">
                <h4 className="font-medium">작업 {index + 1}</h4>
                <button onClick={() => removeTask(index)} className="text-red-600 hover:text-red-800">
                  <Trash2 size={20} />
                </button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2">작업 이름</label>
                  <input
                    type="text"
                    value={task.name}
                    onChange={(e) => updateTask(index, 'taskName', e.target.value)}
                    className="w-full px-3 py-2 border rounded focus:ring-2 focus:ring-blue-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">모듈</label>
                  <select
                    value={task.module}
                    onChange={(e) => updateTask(index, 'module', e.target.value)}
                    className="w-full px-3 py-2 border rounded focus:ring-2 focus:ring-blue-500 focus:outline-none"
                  >
                    {Object.keys(moduleTemplates).map(mod => (
                      <option key={mod} value={mod}>{mod}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                {Object.keys(task.params).map(param => {
                  const fieldType = parameterFieldTypes[task.module]?.[param];
                  const isSelect = fieldType?.type === 'select';

                  return (
                    <div key={param}>
                      <label className="block text-sm font-medium mb-2 capitalize">
                        {param.replace(/_/g, ' ')}
                      </label>
                      {isSelect ? (
                        <select
                          value={task.params[param] || ''}
                          onChange={(e) => updateTask(index, param, e.target.value)}
                          className="w-full px-3 py-2 border rounded focus:ring-2 focus:ring-blue-500 focus:outline-none"
                        >
                          {fieldType.options.map(opt => (
                            <option key={opt} value={opt}>{opt}</option>
                          ))}
                        </select>
                      ) : (
                        <input
                          type="text"
                          value={task.params[param] || ''}
                          onChange={(e) => updateTask(index, param, e.target.value)}
                          className="w-full px-3 py-2 border rounded focus:ring-2 focus:ring-blue-500 focus:outline-none"
                          placeholder={param === 'cmd' ? '명령어를 입력하세요...' : ''}
                        />
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {/* 저장 버튼 - 작업 영역 하단 오른쪽 */}
        <div className="flex justify-end mt-6">
          <button onClick={savePlaybook} className="flex items-center gap-2 px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 font-medium shadow-lg">
            <Save size={20} />
            {isEditMode ? '작업 수정' : '작업 저장'}
          </button>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow-lg p-6">
        <h3 className="text-xl font-semibold mb-4">YAML 미리보기</h3>
        <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-x-auto text-sm font-mono">
          {generateYAML()}
        </pre>
      </div>

      {/* Import YAML Modal */}
      {showImportModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-4xl w-full mx-4 max-h-[85vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-2xl font-bold">YAML 가져오기</h3>
              <button onClick={handleCloseImportModal} className="text-gray-500 hover:text-gray-700 text-3xl">×</button>
            </div>

            <div className="mb-4">
              <label className="block text-sm font-medium mb-2">YAML 내용 붙여넣기</label>
              <textarea
                value={importText}
                onChange={handleYamlTextChange}
                rows={20}
                className="w-full px-3 py-2 border rounded font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                placeholder="---&#10;- name: My Playbook&#10;  hosts: all&#10;  tasks:&#10;    - name: Install nginx&#10;      apt:&#10;        name: nginx"
              />
            </div>

            {/* Validation Result Display */}
            {yamlValidation && (
              <div className={`mb-4 p-4 rounded-lg border-l-4 ${yamlValidation.valid
                ? 'bg-green-50 border-green-500 text-green-800'
                : 'bg-red-50 border-red-500 text-red-800'
                }`}>
                <div className="flex items-start gap-2">
                  <span className="text-xl">{yamlValidation.valid ? '✅' : '❌'}</span>
                  <div>
                    <p className="font-semibold">
                      {yamlValidation.valid ? '문법 정상' : '문법 오류'}
                    </p>
                    <p className="text-sm mt-1">
                      {yamlValidation.valid ? yamlValidation.message : yamlValidation.error}
                    </p>
                    {!yamlValidation.valid && yamlValidation.line && (
                      <p className="text-sm mt-1 font-mono">
                        Line: {yamlValidation.line}{yamlValidation.column ? `, Column: ${yamlValidation.column}` : ''}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            )}

            <div className="flex gap-2 justify-end">
              <button onClick={handleCloseImportModal} className="px-6 py-2 border rounded hover:bg-gray-100">
                취소
              </button>
              <button
                onClick={validateYaml}
                disabled={isValidatingYaml}
                className="px-6 py-2 bg-yellow-500 text-white rounded hover:bg-yellow-600 disabled:opacity-50"
              >
                {isValidatingYaml ? '⏳ 검사 중...' : '🔍 문법 검사'}
              </button>
              <button onClick={importYamlText} className="px-6 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700">
                가져오기
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Import Script Modal */}
      {showScriptModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-4xl w-full mx-4 max-h-[85vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-2xl font-bold">쉘 스크립트 가져오기</h3>
              <button onClick={handleCloseScriptModal} className="text-gray-500 hover:text-gray-700 text-3xl">×</button>
            </div>

            <div className="mb-4">
              <label className="block text-sm font-medium mb-2">플레이북 이름 (선택사항)</label>
              <input
                type="text"
                value={scriptName}
                onChange={(e) => setScriptName(e.target.value)}
                className="w-full px-3 py-2 border rounded focus:ring-2 focus:ring-blue-500 focus:outline-none"
                placeholder="비워두면 자동 생성"
              />
            </div>

            <div className="mb-4">
              <label className="block text-sm font-medium mb-2">쉘 스크립트 내용</label>
              <textarea
                value={scriptText}
                onChange={handleScriptTextChange}
                rows={20}
                className="w-full px-3 py-2 border rounded font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                placeholder="#!/bin/bash&#10;&#10;apt-get update&#10;apt-get install -y nginx&#10;systemctl start nginx"
              />
            </div>

            {/* Validation Result Display */}
            {scriptValidation && (
              <div className={`mb-4 p-4 rounded-lg border-l-4 ${scriptValidation.valid
                ? 'bg-green-50 border-green-500 text-green-800'
                : 'bg-red-50 border-red-500 text-red-800'
                }`}>
                <div className="flex items-start gap-2">
                  <span className="text-xl">{scriptValidation.valid ? '✅' : '❌'}</span>
                  <div>
                    <p className="font-semibold">
                      {scriptValidation.valid ? '문법 정상' : '문법 오류'}
                    </p>
                    <p className="text-sm mt-1">
                      {scriptValidation.valid ? scriptValidation.message : scriptValidation.error}
                    </p>
                    {!scriptValidation.valid && scriptValidation.line && (
                      <p className="text-sm mt-1 font-mono">
                        줄: {scriptValidation.line}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            )}

            <div className="bg-blue-50 border-l-4 border-blue-500 p-4 mb-4 rounded">
              <h4 className="font-bold text-blue-800 mb-2">🔄 자동 변환 기능:</h4>
              <ul className="text-sm text-blue-700 space-y-1 ml-4">
                <li><strong>• 패키지 설치:</strong> apt/yum → apt/yum 모듈</li>
                <li><strong>• 서비스 제어:</strong> systemctl → service 모듈</li>
                <li><strong>• 디렉토리 생성:</strong> mkdir → file 모듈</li>
              </ul>
            </div>

            <div className="flex gap-2 justify-end">
              <button onClick={handleCloseScriptModal} className="px-6 py-2 border rounded hover:bg-gray-100">
                취소
              </button>
              <button
                onClick={validateScript}
                disabled={isValidatingScript}
                className="px-6 py-2 bg-yellow-500 text-white rounded hover:bg-yellow-600 disabled:opacity-50"
              >
                {isValidatingScript ? '⏳ 검사 중...' : '🔍 문법 검사'}
              </button>
              <button onClick={importScriptText} className="px-6 py-2 bg-orange-600 text-white rounded hover:bg-orange-700">
                플레이북으로 변환
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}