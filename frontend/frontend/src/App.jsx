import React, { useState, useEffect } from 'react';
import { Plus, Trash2, Download, Play, Save, CheckCircle, XCircle, Loader, Clock, Eye, Edit, Upload, FileText } from 'lucide-react';

const API_URL = '/api';

export default function App() {
  const [view, setView] = useState('builder');
  const [playbooks, setPlaybooks] = useState([]);
  const [inventories, setInventories] = useState([]);
  const [executions, setExecutions] = useState([]);
  const [selectedPlaybook, setSelectedPlaybook] = useState(null);
  const [selectedInventory, setSelectedInventory] = useState(null);
  const [viewingPlaybook, setViewingPlaybook] = useState(null);
  const [viewingInventory, setViewingInventory] = useState(null);
  const [currentExecution, setCurrentExecution] = useState(null);
  const [isExecuting, setIsExecuting] = useState(false);
  const [awxConfig, setAwxConfig] = useState({
    url: 'http://192.168.64.26:30000',
    username: 'admin',
    password: '',
    template_id: null
  });
  const [awxTemplates, setAwxTemplates] = useState([]);
  const [creatingTemplate, setCreatingTemplate] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [importYamlText, setImportYamlText] = useState('');

  const [playbook, setPlaybook] = useState({
    name: 'My Playbook',
    hosts: 'all',
    become: false,
    tasks: []
  });

  const [inventory, setInventory] = useState({
    name: 'My Inventory',
    content: '[webservers]\n192.168.1.10 ansible_user=ubuntu\n192.168.1.11 ansible_user=ubuntu\n\n[dbservers]\n192.168.1.20 ansible_user=root'
  });

  const [inventoryGroups, setInventoryGroups] = useState([
    {
      name: 'webservers',
      hosts: [
        { hostname: '192.168.1.10', ansible_user: 'ubuntu', ansible_port: '', ansible_connection: '' },
        { hostname: '192.168.1.11', ansible_user: 'ubuntu', ansible_port: '', ansible_connection: '' }
      ]
    },
    {
      name: 'dbservers',
      hosts: [
        { hostname: '192.168.1.20', ansible_user: 'root', ansible_port: '', ansible_connection: '' }
      ]
    }
  ]);
  const [useVisualEditor, setUseVisualEditor] = useState(true);

  const moduleTemplates = {
    'apt': { name: '', state: 'present', update_cache: 'yes' },
    'yum': { name: '', state: 'present' },
    'copy': { src: '', dest: '', mode: '0644' },
    'file': { path: '', state: 'directory', mode: '0755' },
    'service': { name: '', state: 'started', enabled: 'yes' },
    'command': { cmd: '' },
    'shell': { cmd: '' },
    'template': { src: '', dest: '' },
    'user': { name: '', state: 'present' },
    'git': { repo: '', dest: '' }
  };

  useEffect(() => {
    if (view === 'playbooks') {
      loadPlaybooks();
    }
    if (view === 'inventories') {
      loadInventories();
    }
    if (view === 'executions') {
      loadExecutions();
    }
    if (view === 'execute') {
      loadPlaybooks();
      loadInventories();
    }
  }, [view]);

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
      const res = await fetch(`${API_URL}/playbooks`);
      const data = await res.json();
      setPlaybooks(data);
    } catch (err) {
      console.error('Failed to load playbooks:', err);
    }
  };

  const loadInventories = async () => {
    try {
      const res = await fetch(`${API_URL}/inventories`);
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

  const savePlaybook = async () => {
    try {
      const res = await fetch(`${API_URL}/playbooks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(playbook)
      });
      const saved = await res.json();
      alert(`Playbook saved: ${saved.id}`);
      loadPlaybooks();
    } catch (err) {
      alert('Failed to save playbook');
    }
  };

  const deletePlaybook = async (id) => {
    if (!confirm('Delete this playbook?')) return;
    try {
      await fetch(`${API_URL}/playbooks/${id}`, { method: 'DELETE' });
      alert('Playbook deleted');
      loadPlaybooks();
      if (viewingPlaybook?.id === id) setViewingPlaybook(null);
    } catch (err) {
      alert('Failed to delete playbook');
    }
  };

  const loadPlaybookDetail = async (id) => {
    try {
      const res = await fetch(`${API_URL}/playbooks/${id}`);
      const data = await res.json();
      setViewingPlaybook(data);
    } catch (err) {
      console.error('Failed to load playbook detail:', err);
    }
  };

  const editPlaybook = (pb) => {
    setPlaybook(pb);
    setView('builder');
  };

  const saveInventory = async () => {
    try {
      const res = await fetch(`${API_URL}/inventories`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(inventory)
      });
      const saved = await res.json();
      alert(`Inventory saved: ${saved.id}`);
      loadInventories();
    } catch (err) {
      alert('Failed to save inventory');
    }
  };

  const deleteInventory = async (id) => {
    if (!confirm('Delete this inventory?')) return;
    try {
      await fetch(`${API_URL}/inventories/${id}`, { method: 'DELETE' });
      alert('Inventory deleted');
      loadInventories();
      if (viewingInventory?.id === id) setViewingInventory(null);
    } catch (err) {
      alert('Failed to delete inventory');
    }
  };

  const loadInventoryDetail = async (id) => {
    try {
      const res = await fetch(`${API_URL}/inventories/${id}`);
      const data = await res.json();
      setViewingInventory(data);
    } catch (err) {
      console.error('Failed to load inventory detail:', err);
    }
  };

  const editInventory = (inv) => {
    setInventory(inv);
    parseInventoryToGroups(inv.content);
    setView('inventories');
  };

  const parseInventoryToGroups = (content) => {
    const groups = [];
    const lines = content.split('\n');
    let currentGroup = null;

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#')) continue;

      if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
        const groupName = trimmed.slice(1, -1);
        currentGroup = { name: groupName, hosts: [] };
        groups.push(currentGroup);
      } else if (currentGroup) {
        const parts = trimmed.split(/\s+/);
        const hostname = parts[0];
        const host = { hostname, ansible_user: '', ansible_port: '', ansible_connection: '' };

        for (let i = 1; i < parts.length; i++) {
          const [key, value] = parts[i].split('=');
          if (key === 'ansible_user') host.ansible_user = value;
          if (key === 'ansible_port') host.ansible_port = value;
          if (key === 'ansible_connection') host.ansible_connection = value;
        }

        currentGroup.hosts.push(host);
      }
    }

    setInventoryGroups(groups.length > 0 ? groups : [{ name: 'default', hosts: [] }]);
  };

  const generateInventoryContent = () => {
    let content = '';
    inventoryGroups.forEach(group => {
      content += `[${group.name}]\n`;
      group.hosts.forEach(host => {
        let line = host.hostname;
        if (host.ansible_user) line += ` ansible_user=${host.ansible_user}`;
        if (host.ansible_port) line += ` ansible_port=${host.ansible_port}`;
        if (host.ansible_connection) line += ` ansible_connection=${host.ansible_connection}`;
        content += line + '\n';
      });
      content += '\n';
    });
    return content.trim();
  };

  const addInventoryGroup = () => {
    setInventoryGroups([...inventoryGroups, { name: 'new_group', hosts: [] }]);
  };

  const removeInventoryGroup = (index) => {
    setInventoryGroups(inventoryGroups.filter((_, i) => i !== index));
  };

  const updateGroupName = (index, name) => {
    const updated = [...inventoryGroups];
    updated[index].name = name;
    setInventoryGroups(updated);
  };

  const addHost = (groupIndex) => {
    const updated = [...inventoryGroups];
    updated[groupIndex].hosts.push({ hostname: '', ansible_user: '', ansible_port: '', ansible_connection: '' });
    setInventoryGroups(updated);
  };

  const removeHost = (groupIndex, hostIndex) => {
    const updated = [...inventoryGroups];
    updated[groupIndex].hosts = updated[groupIndex].hosts.filter((_, i) => i !== hostIndex);
    setInventoryGroups(updated);
  };

  const updateHost = (groupIndex, hostIndex, field, value) => {
    const updated = [...inventoryGroups];
    updated[groupIndex].hosts[hostIndex][field] = value;
    setInventoryGroups(updated);
  };

  const saveInventoryFromVisual = async () => {
    const content = generateInventoryContent();
    const invToSave = { ...inventory, content };
    
    try {
      const res = await fetch(`${API_URL}/inventories`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(invToSave)
      });
      const saved = await res.json();
      alert(`Inventory saved: ${saved.id}`);
      loadInventories();
    } catch (err) {
      alert('Failed to save inventory');
    }
  };

  const executePlaybook = async () => {
    if (!selectedPlaybook || !selectedInventory) {
      alert('Select both playbook and inventory');
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
      setCurrentExecution(result.execution_id);
      setIsExecuting(true);
      setView('executions');
    } catch (err) {
      alert('Execution failed');
    }
  };

  const loadAwxTemplates = async () => {
    if (!awxConfig.username || !awxConfig.password) {
      alert('Enter AWX credentials');
      return;
    }
    try {
      const params = new URLSearchParams({
        awx_url: awxConfig.url,
        awx_username: awxConfig.username,
        awx_password: awxConfig.password
      });
      const res = await fetch(`${API_URL}/awx/templates?${params}`);
      const data = await res.json();
      setAwxTemplates(data.templates || []);
      if (data.templates && data.templates.length > 0) {
        setAwxConfig({ ...awxConfig, template_id: data.templates[0].id });
      }
      alert(`Loaded ${data.templates.length} templates`);
    } catch (err) {
      alert('Failed to load AWX templates: ' + err.message);
    }
  };

  const createAwxTemplate = async () => {
    if (!selectedPlaybook || !selectedInventory) {
      alert('Select both playbook and inventory');
      return;
    }
    if (!awxConfig.username || !awxConfig.password) {
      alert('Enter AWX credentials');
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
          awx_url: awxConfig.url,
          awx_username: awxConfig.username,
          awx_password: awxConfig.password
        })
      });
      
      const result = await res.json();
      
      if (!res.ok) {
        alert(`Error: ${result.detail || 'Failed to create template'}`);
        console.error('AWX Error:', result);
        return;
      }
      
      if (result.status === 'success') {
        alert(`Job Template Created!\nName: ${result.template_name}\nTemplate ID: ${result.template_id}\n\nInventory: ${result.inventory_url || 'Created'}`);
        setAwxConfig({ ...awxConfig, template_id: result.template_id });
        loadAwxTemplates();
        if (result.inventory_url) {
          window.open(result.inventory_url, '_blank');
        }
      }
    } catch (err) {
      alert('Failed to create AWX template: ' + err.message);
      console.error(err);
    } finally {
      setCreatingTemplate(false);
    }
  };

  const launchAwxJob = async () => {
    if (!selectedPlaybook || !selectedInventory) {
      alert('Select both playbook and inventory');
      return;
    }
    if (!awxConfig.username || !awxConfig.password) {
      alert('Enter AWX credentials');
      return;
    }
    if (!awxConfig.template_id) {
      alert('Select or create a Job Template first');
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
          awx_username: awxConfig.username,
          awx_password: awxConfig.password,
          job_template_id: awxConfig.template_id
        })
      });
      const result = await res.json();
      if (result.status === 'success') {
        alert(`AWX Job launched!\nJob ID: ${result.awx_job_id}\nURL: ${result.awx_job_url}`);
        window.open(result.awx_job_url, '_blank');
      }
    } catch (err) {
      alert('Failed to launch AWX job: ' + err.message);
    }
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
    const newTasks = [...playbook.tasks];
    if (field === 'module') {
      newTasks[index] = {
        ...newTasks[index],
        module: value,
        params: { ...moduleTemplates[value] }
      };
    } else if (field === 'name') {
      newTasks[index].name = value;
    } else {
      newTasks[index].params[field] = value;
    }
    setPlaybook({ ...playbook, tasks: newTasks });
  };

  const generateYAML = (pb = playbook) => {
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

  const downloadPlaybook = () => {
    const yaml = generateYAML();
    const blob = new Blob([yaml], { type: 'text/yaml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'playbook.yml';
    a.click();
  };

  const importYamlFile = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`${API_URL}/playbooks/import`, {
        method: 'POST',
        body: formData
      });
      const result = await res.json();
      
      if (result.status === 'success') {
        alert(`Playbook imported successfully!\nName: ${result.playbook_name}\nTasks: ${result.tasks_count}`);
        loadPlaybooks();
        setView('playbooks');
      } else {
        alert('Failed to import: ' + result.detail);
      }
    } catch (err) {
      alert('Import failed: ' + err.message);
    }
    
    event.target.value = '';
  };

  const importYamlFromText = async () => {
    if (!importYamlText.trim()) {
      alert('Please enter YAML content');
      return;
    }

    try {
      const res = await fetch(`${API_URL}/playbooks/import-text`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(importYamlText)
      });
      const result = await res.json();
      
      if (result.status === 'success') {
        alert(`Playbook imported successfully!\nName: ${result.playbook_name}\nTasks: ${result.tasks_count}`);
        setShowImportModal(false);
        setImportYamlText('');
        loadPlaybooks();
        setView('playbooks');
      } else {
        alert('Failed to import: ' + result.detail);
      }
    } catch (err) {
      alert('Import failed: ' + err.message);
    }
  };

  const getStatusIcon = (status) => {
    if (status === 'completed') return <CheckCircle className="text-green-600" size={20} />;
    if (status === 'failed' || status === 'error') return <XCircle className="text-red-600" size={20} />;
    if (status === 'running') return <Loader className="text-blue-600 animate-spin" size={20} />;
    return <Clock className="text-yellow-600" size={20} />;
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-blue-600 text-white p-4">
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          <h1 className="text-2xl font-bold">Ansible Playbook Builder</h1>
          <div className="flex gap-2">
            <button onClick={() => setView('builder')} className={`px-4 py-2 rounded ${view === 'builder' ? 'bg-blue-800' : 'bg-blue-500'}`}>Builder</button>
            <button onClick={() => setView('playbooks')} className={`px-4 py-2 rounded ${view === 'playbooks' ? 'bg-blue-800' : 'bg-blue-500'}`}>Playbooks</button>
            <button onClick={() => setView('inventories')} className={`px-4 py-2 rounded ${view === 'inventories' ? 'bg-blue-800' : 'bg-blue-500'}`}>Inventories</button>
            <button onClick={() => setView('execute')} className={`px-4 py-2 rounded ${view === 'execute' ? 'bg-blue-800' : 'bg-blue-500'}`}>Execute</button>
            <button onClick={() => setView('executions')} className={`px-4 py-2 rounded ${view === 'executions' ? 'bg-blue-800' : 'bg-blue-500'}`}>History</button>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto p-6">
        {view === 'builder' && (
          <div>
            <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-bold">Playbook Builder</h2>
                <div className="flex gap-2">
                  <label className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700 cursor-pointer">
                    <Upload size={20} />
                    Import YAML
                    <input type="file" accept=".yml,.yaml" onChange={importYamlFile} className="hidden" />
                  </label>
                  <button onClick={() => setShowImportModal(true)} className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700">
                    <FileText size={20} />
                    Paste YAML
                  </button>
                  <button onClick={savePlaybook} className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700">
                    <Save size={20} />Save
                  </button>
                  <button onClick={downloadPlaybook} className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
                    <Download size={20} />Download
                  </button>
                </div>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                <div>
                  <label className="block text-sm font-medium mb-2">Playbook Name</label>
                  <input type="text" value={playbook.name} onChange={(e) => setPlaybook({ ...playbook, name: e.target.value })} className="w-full px-3 py-2 border rounded" />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">Hosts</label>
                  <input type="text" value={playbook.hosts} onChange={(e) => setPlaybook({ ...playbook, hosts: e.target.value })} className="w-full px-3 py-2 border rounded" />
                </div>
                <div className="flex items-end">
                  <label className="flex items-center gap-2">
                    <input type="checkbox" checked={playbook.become} onChange={(e) => setPlaybook({ ...playbook, become: e.target.checked })} className="w-4 h-4" />
                    <span>Become (sudo)</span>
                  </label>
                </div>
              </div>

              <div className="flex justify-between items-center mb-4">
                <h3 className="text-xl font-semibold">Tasks</h3>
                <button onClick={addTask} className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
                  <Plus size={20} />Add Task
                </button>
              </div>

              <div className="space-y-4">
                {playbook.tasks.map((task, index) => (
                  <div key={index} className="border rounded-lg p-4 bg-gray-50">
                    <div className="flex justify-between mb-4">
                      <h4 className="font-medium">Task {index + 1}</h4>
                      <button onClick={() => removeTask(index)} className="text-red-600 hover:text-red-800">
                        <Trash2 size={20} />
                      </button>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium mb-2">Task Name</label>
                        <input type="text" value={task.name} onChange={(e) => updateTask(index, 'name', e.target.value)} className="w-full px-3 py-2 border rounded" />
                      </div>
                      <div>
                        <label className="block text-sm font-medium mb-2">Module</label>
                        <select value={task.module} onChange={(e) => updateTask(index, 'module', e.target.value)} className="w-full px-3 py-2 border rounded">
                          {Object.keys(moduleTemplates).map(mod => (
                            <option key={mod} value={mod}>{mod}</option>
                          ))}
                        </select>
                      </div>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                      {Object.keys(task.params).map(param => (
                        <div key={param}>
                          <label className="block text-sm font-medium mb-2 capitalize">{param.replace('_', ' ')}</label>
                          <input type="text" value={task.params[param]} onChange={(e) => updateTask(index, param, e.target.value)} className="w-full px-3 py-2 border rounded" />
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white rounded-lg shadow-lg p-6">
              <h3 className="text-xl font-semibold mb-4">Preview YAML</h3>
              <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-x-auto text-sm">{generateYAML()}</pre>
            </div>
          </div>
        )}

        {view === 'playbooks' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white rounded-lg shadow-lg p-6">
              <h2 className="text-2xl font-bold mb-6">Saved Playbooks</h2>
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
                        <button onClick={() => loadPlaybookDetail(pb.id)} className="p-2 text-blue-600 hover:bg-blue-50 rounded" title="View">
                          <Eye size={18} />
                        </button>
                        <button onClick={() => editPlaybook(pb)} className="p-2 text-green-600 hover:bg-green-50 rounded" title="Edit">
                          <Edit size={18} />
                        </button>
                        <button onClick={() => deletePlaybook(pb.id)} className="p-2 text-red-600 hover:bg-red-50 rounded" title="Delete">
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
                  <button onClick={() => setViewingPlaybook(null)} className="text-gray-500 hover:text-gray-700">✕</button>
                </div>
                <div className="mb-4">
                  <h3 className="font-bold text-lg">{viewingPlaybook.name}</h3>
                  <p className="text-sm text-gray-600">ID: {viewingPlaybook.id}</p>
                  <p className="text-sm text-gray-600">Hosts: {viewingPlaybook.hosts}</p>
                  <p className="text-sm text-gray-600">Become: {viewingPlaybook.become ? 'Yes' : 'No'}</p>
                </div>
                <div className="mb-4">
                  <h4 className="font-semibold mb-2">Tasks ({viewingPlaybook.tasks.length})</h4>
                  <div className="space-y-2">
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
                  <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-x-auto text-xs">{generateYAML(viewingPlaybook)}</pre>
                </div>
              </div>
            )}
          </div>
        )}

        {view === 'inventories' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white rounded-lg shadow-lg p-6">
              <h2 className="text-2xl font-bold mb-6">Inventory Manager</h2>
              
              <div className="mb-4">
                <label className="block text-sm font-medium mb-2">Inventory Name</label>
                <input 
                  type="text" 
                  value={inventory.name} 
                  onChange={(e) => setInventory({ ...inventory, name: e.target.value })} 
                  className="w-full px-3 py-2 border rounded" 
                />
              </div>

              <div className="flex items-center gap-4 mb-6 border-b pb-2">
                <button
                  onClick={() => setUseVisualEditor(true)}
                  className={`px-6 py-2 rounded-t font-medium ${useVisualEditor ? 'bg-blue-600 text-white' : 'bg-gray-100 hover:bg-gray-200'}`}
                >
                  📝 Visual Editor
                </button>
                <button
                  onClick={() => {
                    setUseVisualEditor(false);
                    if (inventoryGroups.length > 0) {
                      setInventory({ ...inventory, content: generateInventoryContent() });
                    }
                  }}
                  className={`px-6 py-2 rounded-t font-medium ${!useVisualEditor ? 'bg-blue-600 text-white' : 'bg-gray-100 hover:bg-gray-200'}`}
                >
                  📄 Text Editor
                </button>
              </div>

              {useVisualEditor ? (
                <div className="space-y-4">
                  {inventoryGroups.map((group, groupIndex) => (
                    <div key={groupIndex} className="border-2 border-gray-200 rounded-lg p-4 bg-gradient-to-br from-gray-50 to-white">
                      <div className="flex justify-between items-center mb-3">
                        <div className="flex items-center gap-2">
                          <span className="text-gray-500">📁</span>
                          <input
                            type="text"
                            value={group.name}
                            onChange={(e) => updateGroupName(groupIndex, e.target.value)}
                            className="text-lg font-semibold px-3 py-1 border-2 border-blue-300 rounded focus:border-blue-500 focus:outline-none"
                            placeholder="Group name"
                          />
                        </div>
                        <button
                          onClick={() => removeInventoryGroup(groupIndex)}
                          className="p-2 text-red-600 hover:bg-red-50 rounded-full"
                          title="Delete group"
                        >
                          <Trash2 size={18} />
                        </button>
                      </div>

                      <div className="space-y-2 ml-6">
                        <div className="grid grid-cols-12 gap-2 text-xs font-semibold text-gray-600 mb-1">
                          <div className="col-span-3">Hostname/IP</div>
                          <div className="col-span-3">User</div>
                          <div className="col-span-2">Port</div>
                          <div className="col-span-3">Connection</div>
                          <div className="col-span-1"></div>
                        </div>
                        {group.hosts.map((host, hostIndex) => (
                          <div key={hostIndex} className="grid grid-cols-12 gap-2 items-center bg-white p-2 rounded border hover:border-blue-300 transition">
                            <input
                              type="text"
                              value={host.hostname}
                              onChange={(e) => updateHost(groupIndex, hostIndex, 'hostname', e.target.value)}
                              placeholder="192.168.1.10"
                              className="col-span-3 px-2 py-1.5 border rounded text-sm focus:border-blue-500 focus:outline-none"
                            />
                            <input
                              type="text"
                              value={host.ansible_user}
                              onChange={(e) => updateHost(groupIndex, hostIndex, 'ansible_user', e.target.value)}
                              placeholder="ubuntu"
                              className="col-span-3 px-2 py-1.5 border rounded text-sm focus:border-blue-500 focus:outline-none"
                            />
                            <input
                              type="text"
                              value={host.ansible_port}
                              onChange={(e) => updateHost(groupIndex, hostIndex, 'ansible_port', e.target.value)}
                              placeholder="22"
                              className="col-span-2 px-2 py-1.5 border rounded text-sm focus:border-blue-500 focus:outline-none"
                            />
                            <input
                              type="text"
                              value={host.ansible_connection}
                              onChange={(e) => updateHost(groupIndex, hostIndex, 'ansible_connection', e.target.value)}
                              placeholder="ssh"
                              className="col-span-3 px-2 py-1.5 border rounded text-sm focus:border-blue-500 focus:outline-none"
                            />
                            <button
                              onClick={() => removeHost(groupIndex, hostIndex)}
                              className="col-span-1 p-1 text-red-600 hover:bg-red-50 rounded"
                            >
                              <Trash2 size={16} />
                            </button>
                          </div>
                        ))}
                      </div>

                      <button
                        onClick={() => addHost(groupIndex)}
                        className="mt-3 ml-6 text-sm text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1"
                      >
                        <Plus size={16} />
                        Add Host to {group.name}
                      </button>
                    </div>
                  ))}

                  <button
                    onClick={addInventoryGroup}
                    className="w-full py-3 border-2 border-dashed border-gray-300 rounded-lg hover:border-blue-500 hover:bg-blue-50 hover:text-blue-600 flex items-center justify-center gap-2 font-medium transition"
                  >
                    <Plus size={20} />
                    Add New Group
                  </button>

                  <button
                    onClick={saveInventoryFromVisual}
                    className="w-full mt-6 px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 font-medium shadow-lg"
                  >
                    💾 Save Inventory
                  </button>
                </div>
              ) : (
                <div>
                  <label className="block text-sm font-medium mb-2">Inventory Content (INI format)</label>
                  <textarea
                    value={inventory.content}
                    onChange={(e) => setInventory({ ...inventory, content: e.target.value })}
                    rows={12}
                    className="w-full px-3 py-2 border rounded font-mono text-sm"
                  />
                  <div className="mt-2 p-3 bg-gray-50 border rounded text-sm">
                    <p className="font-semibold mb-2">Format Examples:</p>
                    <pre className="text-xs">
{`[webservers]
192.168.1.10 ansible_user=ubuntu
web1.example.com ansible_user=admin

[dbservers]
db1.example.com ansible_user=root ansible_port=2222

[local]
localhost ansible_connection=local`}
                    </pre>
                  </div>
                  <button onClick={saveInventory} className="mt-4 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700">
                    Save Inventory
                  </button>
                </div>
              )}

              <h3 className="text-xl font-semibold mt-8 mb-4">Saved Inventories</h3>
              <div className="space-y-2">
                {inventories.map(inv => (
                  <div key={inv.id} className="p-4 border rounded hover:bg-gray-50 transition">
                    <div className="flex justify-between items-center">
                      <div className="flex-1 cursor-pointer" onClick={() => loadInventoryDetail(inv.id)}>
                        <h4 className="font-medium">{inv.name}</h4>
                        <p className="text-sm text-gray-600">ID: {inv.id}</p>
                      </div>
                      <div className="flex gap-2">
                        <button onClick={() => loadInventoryDetail(inv.id)} className="p-2 text-blue-600 hover:bg-blue-50 rounded" title="View">
                          <Eye size={18} />
                        </button>
                        <button onClick={() => editInventory(inv)} className="p-2 text-green-600 hover:bg-green-50 rounded" title="Edit">
                          <Edit size={18} />
                        </button>
                        <button onClick={() => deleteInventory(inv.id)} className="p-2 text-red-600 hover:bg-red-50 rounded" title="Delete">
                          <Trash2 size={18} />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
                {inventories.length === 0 && (
                  <p className="text-gray-500 text-center py-8">No saved inventories</p>
                )}
              </div>
            </div>

            {viewingInventory && (
              <div className="bg-white rounded-lg shadow-lg p-6">
                <div className="flex justify-between items-center mb-4">
                  <h2 className="text-2xl font-bold">Inventory Detail</h2>
                  <button onClick={() => setViewingInventory(null)} className="text-gray-500 hover:text-gray-700">✕</button>
                </div>
                <div className="mb-4">
                  <h3 className="font-bold text-lg">{viewingInventory.name}</h3>
                  <p className="text-sm text-gray-600">ID: {viewingInventory.id}</p>
                  <p className="text-sm text-gray-600">Created: {new Date(viewingInventory.created_at).toLocaleString()}</p>
                </div>
                <div>
                  <h4 className="font-semibold mb-2">Content</h4>
                  <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-x-auto text-sm whitespace-pre-wrap">{viewingInventory.content}</pre>
                </div>
              </div>
            )}
          </div>
        )}

        {view === 'execute' && (
          <div className="space-y-6">
            <div className="bg-white rounded-lg shadow-lg p-6">
              <h2 className="text-2xl font-bold mb-6">Execute Playbook (Local)</h2>
              <div className="mb-4">
                <label className="block text-sm font-medium mb-2">Select Playbook</label>
                <select value={selectedPlaybook || ''} onChange={(e) => setSelectedPlaybook(e.target.value)} className="w-full px-3 py-2 border rounded">
                  <option value="">-- Select Playbook --</option>
                  {playbooks.map(pb => (
                    <option key={pb.id} value={pb.id}>{pb.name} ({pb.id})</option>
                  ))}
                </select>
              </div>
              <div className="mb-4">
                <label className="block text-sm font-medium mb-2">Select Inventory</label>
                <select value={selectedInventory || ''} onChange={(e) => setSelectedInventory(e.target.value)} className="w-full px-3 py-2 border rounded">
                  <option value="">-- Select Inventory --</option>
                  {inventories.map(inv => (
                    <option key={inv.id} value={inv.id}>{inv.name} ({inv.id})</option>
                  ))}
                </select>
              </div>
              <button onClick={executePlaybook} className="px-6 py-3 bg-green-600 text-white rounded hover:bg-green-700 flex items-center gap-2">
                <Play size={20} />Execute Locally
              </button>
            </div>

            <div className="bg-white rounded-lg shadow-lg p-6">
              <h2 className="text-2xl font-bold mb-6">Execute via AWX</h2>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                <div>
                  <label className="block text-sm font-medium mb-2">AWX URL</label>
                  <input 
                    type="text" 
                    value={awxConfig.url} 
                    onChange={(e) => setAwxConfig({ ...awxConfig, url: e.target.value })} 
                    className="w-full px-3 py-2 border rounded"
                    placeholder="http://192.168.64.26:30000"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">Username</label>
                  <input 
                    type="text" 
                    value={awxConfig.username} 
                    onChange={(e) => setAwxConfig({ ...awxConfig, username: e.target.value })} 
                    className="w-full px-3 py-2 border rounded"
                    placeholder="admin"
                  />
                </div>
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium mb-2">Password</label>
                  <input 
                    type="password" 
                    value={awxConfig.password} 
                    onChange={(e) => setAwxConfig({ ...awxConfig, password: e.target.value })} 
                    className="w-full px-3 py-2 border rounded"
                    placeholder="Enter password"
                  />
                </div>
              </div>

              <div className="mb-4">
                <label className="block text-sm font-medium mb-2">Select Playbook</label>
                <select value={selectedPlaybook || ''} onChange={(e) => setSelectedPlaybook(e.target.value)} className="w-full px-3 py-2 border rounded">
                  <option value="">-- Select Playbook --</option>
                  {playbooks.map(pb => (
                    <option key={pb.id} value={pb.id}>{pb.name} ({pb.id})</option>
                  ))}
                </select>
              </div>
              
              <div className="mb-6">
                <label className="block text-sm font-medium mb-2">Select Inventory</label>
                <select value={selectedInventory || ''} onChange={(e) => setSelectedInventory(e.target.value)} className="w-full px-3 py-2 border rounded">
                  <option value="">-- Select Inventory --</option>
                  {inventories.map(inv => (
                    <option key={inv.id} value={inv.id}>{inv.name} ({inv.id})</option>
                  ))}
                </select>
              </div>

              <div className="mb-6 pb-6 border-b">
                <button 
                  onClick={createAwxTemplate} 
                  disabled={creatingTemplate}
                  className="w-full px-6 py-3 bg-indigo-600 text-white rounded hover:bg-indigo-700 flex items-center justify-center gap-2 disabled:bg-gray-400"
                >
                  {creatingTemplate ? (
                    <>
                      <Loader className="animate-spin" size={20} />
                      Creating Template...
                    </>
                  ) : (
                    <>
                      <Plus size={20} />
                      Create Job Template in AWX
                    </>
                  )}
                </button>
                <p className="text-xs text-gray-600 mt-2">
                  This will automatically create a new Job Template, Project, and Inventory in AWX
                </p>
              </div>

              <div className="mb-4">
                <label className="block text-sm font-medium mb-2">Existing Job Templates</label>
                <div className="flex gap-2">
                  <select 
                    value={awxConfig.template_id || ''} 
                    onChange={(e) => setAwxConfig({ ...awxConfig, template_id: parseInt(e.target.value) })} 
                    className="flex-1 px-3 py-2 border rounded"
                  >
                    <option value="">-- Select Template --</option>
                    {awxTemplates.map(tpl => (
                      <option key={tpl.id} value={tpl.id}>{tpl.name}</option>
                    ))}
                  </select>
                  <button 
                    onClick={loadAwxTemplates} 
                    className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                  >
                    Refresh
                  </button>
                </div>
              </div>

              <button 
                onClick={launchAwxJob} 
                className="w-full px-6 py-3 bg-purple-600 text-white rounded hover:bg-purple-700 flex items-center justify-center gap-2"
              >
                <Play size={20} />
                Execute Job in AWX
              </button>

              <div className="mt-6 p-4 bg-yellow-50 border-l-4 border-yellow-500 rounded">
                <p className="text-sm text-yellow-800">
                  <strong>Steps:</strong>
                </p>
                <ol className="text-sm text-yellow-800 mt-2 ml-4 list-decimal">
                  <li>Select Playbook and Inventory</li>
                  <li>Click "Create Job Template" to auto-create in AWX</li>
                  <li>Or select existing template and click "Execute Job"</li>
                </ol>
              </div>
            </div>
          </div>
        )}

        {view === 'executions' && (
          <div className="bg-white rounded-lg shadow-lg p-6">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-2xl font-bold">Execution History</h2>
              <button onClick={loadExecutions} className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">Refresh</button>
            </div>
            {isExecuting && (
              <div className="mb-4 p-4 bg-blue-50 border-l-4 border-blue-500 rounded">
                <div className="flex items-center gap-2">
                  <Loader className="animate-spin text-blue-600" size={20} />
                  <span className="font-medium text-blue-800">Execution in progress...</span>
                </div>
              </div>
            )}
            <div className="space-y-4">
              {executions.map(exec => (
                <div key={exec.id} className={`p-4 border rounded ${exec.id === currentExecution && isExecuting ? 'border-blue-500 bg-blue-50' : ''}`}>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      {getStatusIcon(exec.status)}
                      <span className="font-bold">{exec.id}</span>
                      <span className="text-sm text-gray-600">Status: {exec.status}</span>
                    </div>
                  </div>
                  <p className="text-sm text-gray-600">Playbook: {exec.playbook_id} | Inventory: {exec.inventory_id}</p>
                  {exec.output && (
                    <div className="mt-2">
                      <h4 className="text-sm font-semibold mb-1">Output:</h4>
                      <pre className="p-3 bg-gray-900 text-green-400 rounded text-xs overflow-x-auto max-h-96 overflow-y-auto">{exec.output}</pre>
                    </div>
                  )}
                  {exec.error && (
                    <div className="mt-2">
                      <h4 className="text-sm font-semibold mb-1 text-red-700">Error:</h4>
                      <pre className="p-3 bg-red-100 rounded text-xs overflow-x-auto text-red-800">{exec.error}</pre>
                    </div>
                  )}
                </div>
              ))}
              {executions.length === 0 && (
                <p className="text-gray-500 text-center py-8">No execution history</p>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Import YAML Modal */}
      {showImportModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-3xl w-full mx-4 max-h-[80vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-xl font-bold">Import YAML</h3>
              <button onClick={() => setShowImportModal(false)} className="text-gray-500 hover:text-gray-700 text-2xl">×</button>
            </div>
            
            <div className="mb-4">
              <label className="block text-sm font-medium mb-2">Paste YAML Content</label>
              <textarea
                value={importYamlText}
                onChange={(e) => setImportYamlText(e.target.value)}
                rows={20}
                className="w-full px-3 py-2 border rounded font-mono text-sm"
                placeholder={`---
- name: My Playbook
  hosts: all
  become: yes
  tasks:
    - name: Install nginx
      apt:
        name: nginx
        state: present
        update_cache: yes`}
              />
            </div>
            
            <div className="flex gap-2 justify-end">
              <button onClick={() => setShowImportModal(false)} className="px-4 py-2 border rounded hover:bg-gray-100">Cancel</button>
              <button onClick={importYamlFromText} className="px-4 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700">Import</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
