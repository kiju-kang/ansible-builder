import React, { useState } from 'react';
import { Plus, Trash2, Upload, FileText, Eye, Edit } from 'lucide-react';

const API_URL = '/api';

export default function InventoryManager({ inventories, onRefresh }) {
  const [inventory, setInventory] = useState({
    name: 'My Inventory',
    content: '[webservers]\n192.168.1.10 ansible_user=ubuntu\n\n[dbservers]\n192.168.1.20 ansible_user=root'
  });

  const [inventoryGroups, setInventoryGroups] = useState([
    {
      name: 'webservers',
      hosts: [{ hostname: '192.168.1.10', ansible_user: 'ubuntu', ansible_port: '', ansible_connection: '' }]
    }
  ]);

  const [useVisualEditor, setUseVisualEditor] = useState(true);
  const [viewingInventory, setViewingInventory] = useState(null);
  const [showImportModal, setShowImportModal] = useState(false);
  const [importText, setImportText] = useState('');
  const [importName, setImportName] = useState('');

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

  const saveInventory = async (fromVisual = false) => {
    const invToSave = fromVisual ? { ...inventory, content: generateInventoryContent() } : inventory;
    
    try {
      const res = await fetch(`${API_URL}/inventories`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(invToSave)
      });
      const saved = await res.json();
      alert(`✅ Inventory saved: ${saved.name} (ID: ${saved.id})`);
      if (onRefresh) onRefresh();
    } catch (err) {
      alert('❌ Failed to save inventory');
    }
  };

  const deleteInventory = async (id) => {
    if (!confirm('Delete this inventory?')) return;
    try {
      await fetch(`${API_URL}/inventories/${id}`, { method: 'DELETE' });
      alert('✅ Inventory deleted');
      if (onRefresh) onRefresh();
      if (viewingInventory?.id === id) setViewingInventory(null);
    } catch (err) {
      alert('❌ Failed to delete inventory');
    }
  };

  const loadInventoryDetail = async (id) => {
    try {
      const res = await fetch(`${API_URL}/inventories/${id}`);
      const data = await res.json();
      setViewingInventory(data);
    } catch (err) {
      console.error('Failed to load inventory:', err);
    }
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

  const importInventoryFile = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    const endpoint = file.name.endsWith('.csv') 
      ? `${API_URL}/inventories/import-csv`
      : `${API_URL}/inventories/import`;

    try {
      const res = await fetch(endpoint, { method: 'POST', body: formData });
      const result = await res.json();
      
      if (result.status === 'success') {
        alert(`✅ Inventory imported!\n\nName: ${result.inventory_name}\nHosts: ${result.host_count}`);
        if (onRefresh) onRefresh();
      } else {
        alert('❌ Failed to import: ' + result.detail);
      }
    } catch (err) {
      alert('❌ Import failed: ' + err.message);
    }
    
    event.target.value = '';
  };

  const importInventoryText = async () => {
    if (!importText.trim()) {
      alert('Please enter inventory content');
      return;
    }

    try {
      const res = await fetch(`${API_URL}/inventories/import-text`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: importName || `Imported_${Date.now()}`,
          content: importText
        })
      });
      const result = await res.json();
      
      if (result.status === 'success') {
        alert(`✅ Inventory imported!\n\nName: ${result.inventory_name}\nHosts: ${result.host_count}`);
        setShowImportModal(false);
        setImportText('');
        setImportName('');
        if (onRefresh) onRefresh();
      } else {
        alert('❌ Failed to import: ' + result.detail);
      }
    } catch (err) {
      alert('❌ Import failed: ' + err.message);
    }
  };

  return (
    <>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow-lg p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold">Inventory Manager</h2>
            <div className="flex gap-2">
              <label className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700 cursor-pointer">
                <Upload size={20} />
                Import File
                <input type="file" accept=".ini,.txt,.csv" onChange={importInventoryFile} className="hidden" />
              </label>
              <button 
                onClick={() => setShowImportModal(true)} 
                className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700"
              >
                <FileText size={20} />
                Paste Text
              </button>
            </div>
          </div>
          
          <div className="mb-4">
            <label className="block text-sm font-medium mb-2">Inventory Name</label>
            <input 
              type="text" 
              value={inventory.name} 
              onChange={(e) => setInventory({ ...inventory, name: e.target.value })} 
              className="w-full px-3 py-2 border rounded focus:ring-2 focus:ring-blue-500 focus:outline-none" 
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
                onClick={() => saveInventory(true)}
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
                className="w-full px-3 py-2 border rounded font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
              <button 
                onClick={() => saveInventory(false)} 
                className="mt-4 w-full px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
              >
                💾 Save Inventory
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
                    <button 
                      onClick={() => loadInventoryDetail(inv.id)} 
                      className="p-2 text-blue-600 hover:bg-blue-50 rounded"
                    >
                      <Eye size={18} />
                    </button>
                    <button 
                      onClick={() => deleteInventory(inv.id)} 
                      className="p-2 text-red-600 hover:bg-red-50 rounded"
                    >
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
              <button 
                onClick={() => setViewingInventory(null)} 
                className="text-gray-500 hover:text-gray-700 text-2xl"
              >
                ✕
              </button>
            </div>
            <div className="mb-4">
              <h3 className="font-bold text-lg">{viewingInventory.name}</h3>
              <p className="text-sm text-gray-600">ID: {viewingInventory.id}</p>
              <p className="text-sm text-gray-600">Created: {new Date(viewingInventory.created_at).toLocaleString()}</p>
            </div>
            <div>
              <h4 className="font-semibold mb-2">Content</h4>
              <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-x-auto text-sm whitespace-pre-wrap font-mono">
                {viewingInventory.content}
              </pre>
            </div>
          </div>
        )}
      </div>

      {/* Import Modal */}
      {showImportModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-4xl w-full mx-4 max-h-[85vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-2xl font-bold">Import Inventory</h3>
              <button onClick={() => setShowImportModal(false)} className="text-gray-500 hover:text-gray-700 text-3xl">×</button>
            </div>
            
            <div className="mb-4">
              <label className="block text-sm font-medium mb-2">Inventory Name (Optional)</label>
              <input
                type="text"
                value={importName}
                onChange={(e) => setImportName(e.target.value)}
                className="w-full px-3 py-2 border rounded focus:ring-2 focus:ring-blue-500 focus:outline-none"
                placeholder="Leave empty for auto-generated name"
              />
            </div>
            
            <div className="mb-4">
              <label className="block text-sm font-medium mb-2">Inventory Content (INI Format)</label>
              <textarea
                value={importText}
                onChange={(e) => setImportText(e.target.value)}
                rows={20}
                className="w-full px-3 py-2 border rounded font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                placeholder="[webservers]&#10;web1.example.com ansible_user=ubuntu&#10;192.168.1.10 ansible_user=admin"
              />
            </div>
            
            <div className="flex gap-2 justify-end">
              <button onClick={() => setShowImportModal(false)} className="px-6 py-2 border rounded hover:bg-gray-100">
                Cancel
              </button>
              <button onClick={importInventoryText} className="px-6 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700">
                Import
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}