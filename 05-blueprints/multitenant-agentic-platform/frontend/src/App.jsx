import { useState, useEffect } from 'react';
import './App.css';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts';
import {
  Button,
  Card,
  Modal,
  TextField,
  Label,
  Input,
  TextArea,
  Select,
  ListBox,
  Chip,
  Spinner,
  Checkbox,
  Description
} from '@heroui/react';
import { validateTokenLimit, calculateUsagePercentage, getUsageColor } from './utils/validation.js';

const API_ENDPOINT = window.APP_CONFIG?.API_ENDPOINT || 'http://localhost:3000';
const API_KEY = window.APP_CONFIG?.API_KEY || '';

function App() {
  const [tenantId, setTenantId] = useState('');
  const [deploymentStatus, setDeploymentStatus] = useState('');
  const [deployedAgent, setDeployedAgent] = useState(null);
  const [tokenUsage, setTokenUsage] = useState([]);
  const [agents, setAgents] = useState([]);
  const [deployLoading, setDeployLoading] = useState(false);
  const [invokeLoading, setInvokeLoading] = useState(false);
  const [invokeMessage, setInvokeMessage] = useState('');
  const [invokeResponse, setInvokeResponse] = useState('');
  const [selectedAgentForInvoke, setSelectedAgentForInvoke] = useState(null);
  const [showAdvancedConfig, setShowAdvancedConfig] = useState(false);
  const [agentConfig, setAgentConfig] = useState({
    modelId: 'global.anthropic.claude-sonnet-4-5-20250929-v1:0',
    systemPrompt: 'You are a helpful AI assistant.',
    customSettings: {}
  });
  const [useCustomTemplate, setUseCustomTemplate] = useState(false);
  const [templateConfig, setTemplateConfig] = useState({
    source: 'github',
    repo: '',
    path: 'templates/main.py',
    branch: 'main',
    token: ''
  });
  const [availableTools, setAvailableTools] = useState([]);
  const [selectedTools, setSelectedTools] = useState([]);
  const [loadingTools, setLoadingTools] = useState(false);
  const [toolsRepo, setToolsRepo] = useState('');
  const [agentsSortConfig, setAgentsSortConfig] = useState({ key: null, direction: 'asc' });
  const [usageSortConfig, setUsageSortConfig] = useState({ key: null, direction: 'asc' });
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [deploymentNotification, setDeploymentNotification] = useState(null);
  const [tenantExists, setTenantExists] = useState(null); // null = not checked, true/false = checked
  const [tokenLimit, setTokenLimit] = useState('');
  const [tokenLimitError, setTokenLimitError] = useState('');
  const [infrastructureCosts, setInfrastructureCosts] = useState([]); // Infrastructure costs per tenant
  const [isDarkMode, setIsDarkMode] = useState(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('theme');
      if (saved) return saved === 'dark';
      return window.matchMedia('(prefers-color-scheme: dark)').matches;
    }
    return false;
  });

  // Apply theme to document
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', isDarkMode ? 'dark' : 'light');
    localStorage.setItem('theme', isDarkMode ? 'dark' : 'light');
  }, [isDarkMode]);

  // Check if tenant exists when tenant ID changes (debounced)
  useEffect(() => {
    if (!tenantId || tenantId.trim() === '') {
      setTenantExists(null);
      setTokenLimit('');
      setTokenLimitError('');
      return;
    }
    
    const timeoutId = setTimeout(async () => {
      try {
        // Check if tenant exists in token usage data
        const existingTenant = tokenUsage.find(
          item => item.tenant_id === tenantId && item.aggregation_key?.startsWith('tenant:')
        );
        setTenantExists(!!existingTenant);
        if (existingTenant) {
          setTokenLimit(''); // Clear token limit for existing tenants
          setTokenLimitError('');
        }
      } catch (error) {
        console.error('Error checking tenant:', error);
        setTenantExists(null);
      }
    }, 500); // 500ms debounce
    
    return () => clearTimeout(timeoutId);
  }, [tenantId, tokenUsage]);

  const fetchTokenUsage = async () => {
    try {
      const response = await axios.get(`${API_ENDPOINT}/usage`, {
        headers: { 'x-api-key': API_KEY }
      });
      const data = Array.isArray(response.data) ? response.data : JSON.parse(response.data);
      setTokenUsage(data || []);
    } catch (error) {
      console.error('Error fetching token usage:', error);
    }
  };

  const fetchInfrastructureCosts = async () => {
    try {
      const response = await axios.get(`${API_ENDPOINT}/infrastructure-costs`, {
        headers: { 'x-api-key': API_KEY }
      });
      const data = Array.isArray(response.data) ? response.data : JSON.parse(response.data);
      setInfrastructureCosts(data || []);
    } catch (error) {
      console.error('Error fetching infrastructure costs:', error);
      // Don't fail silently - set empty array so UI shows $0.000000
      setInfrastructureCosts([]);
    }
  };

  const fetchAgents = async () => {
    try {
      const response = await axios.get(`${API_ENDPOINT}/agents`, {
        headers: { 'x-api-key': API_KEY }
      });
      const data = Array.isArray(response.data) ? response.data : JSON.parse(response.data);
      setAgents(data || []);
      // Only set default selection if no agent is currently selected
      // Use functional update to avoid stale closure issues
      setSelectedAgentForInvoke(current => {
        if (current === null && data && data.length > 0) {
          return data[0];
        }
        // If current selection exists, verify it's still in the list
        if (current && data) {
          const stillExists = data.find(a => a.agentRuntimeId === current.agentRuntimeId);
          if (stillExists) {
            // Update with fresh data in case agent details changed
            return stillExists;
          }
          // Agent was deleted, select first available or null
          return data.length > 0 ? data[0] : null;
        }
        return current;
      });
    } catch (error) {
      console.error('Error fetching agents:', error);
    }
  };

  const extractRepoPath = (repoInput) => {
    if (!repoInput) return '';
    if (repoInput.match(/^[^\/]+\/[^\/]+$/)) return repoInput;
    const match = repoInput.match(/github\.com\/([^\/]+\/[^\/]+)/);
    if (match) return match[1].replace(/\.git$/, '');
    return repoInput;
  };

  const fetchToolCatalog = async () => {
    if (!toolsRepo) {
      setAvailableTools([]);
      return;
    }
    setLoadingTools(true);
    try {
      const repoPath = extractRepoPath(toolsRepo);
      const branch = templateConfig.branch || 'main';
      const url = `https://api.github.com/repos/${repoPath}/contents/catalog.json?ref=${branch}`;
      const headers = { 'Accept': 'application/vnd.github.v3+json' };
      if (templateConfig.token) headers['Authorization'] = `token ${templateConfig.token}`;
      const response = await axios.get(url, { headers });
      const content = atob(response.data.content);
      const catalog = JSON.parse(content);
      setAvailableTools(catalog.tools || []);
    } catch (error) {
      console.error('Error fetching tool catalog:', error);
      setAvailableTools([]);
      alert('Failed to fetch tool catalog.');
    } finally {
      setLoadingTools(false);
    }
  };

  const toggleToolSelection = (tool) => {
    const isSelected = selectedTools.some(t => t.id === tool.id);
    if (isSelected) {
      setSelectedTools(selectedTools.filter(t => t.id !== tool.id));
    } else {
      setSelectedTools([...selectedTools, { ...tool, config: {} }]);
    }
  };

  const deleteAgent = async (tenantId, agentRuntimeId, agentName) => {
    if (!window.confirm(`Delete agent "${agentName}" for tenant: ${tenantId}?`)) return;
    try {
       await axios.delete(
        `${API_ENDPOINT}/agent?tenantId=${tenantId}&agentRuntimeId=${agentRuntimeId}`,
        { headers: { 'x-api-key': API_KEY } }
      );
      alert(`Agent "${agentName}" deleted successfully`);
      fetchAgents();
      // Use functional update to avoid stale closure
      setSelectedAgentForInvoke(current => 
        current?.agentRuntimeId === agentRuntimeId ? null : current
      );
      setDeployedAgent(current => {
        if (current?.agentRuntimeId === agentRuntimeId) {
          setDeploymentStatus('');
          return null;
        }
        return current;
      });
    } catch (error) {
      alert(`Error deleting agent: ${error.response?.data?.error || error.message}`);
    }
  };

  const sortData = (data, sortConfig) => {
    if (!sortConfig.key) return data;
    return [...data].sort((a, b) => {
      let aVal = a[sortConfig.key], bVal = b[sortConfig.key];
      if (aVal == null) return 1;
      if (bVal == null) return -1;
      if (sortConfig.key === 'deployedAt') {
        aVal = new Date(aVal).getTime();
        bVal = new Date(bVal).getTime();
      }
      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return sortConfig.direction === 'asc' ? aVal - bVal : bVal - aVal;
      }
      const aStr = String(aVal).toLowerCase(), bStr = String(bVal).toLowerCase();
      if (aStr < bStr) return sortConfig.direction === 'asc' ? -1 : 1;
      if (aStr > bStr) return sortConfig.direction === 'asc' ? 1 : -1;
      return 0;
    });
  };

  const handleAgentsSort = (key) => {
    setAgentsSortConfig(prev => ({
      key,
      direction: prev.key === key && prev.direction === 'asc' ? 'desc' : 'asc'
    }));
  };

  const handleUsageSort = (key) => {
    setUsageSortConfig(prev => ({
      key,
      direction: prev.key === key && prev.direction === 'asc' ? 'desc' : 'asc'
    }));
  };

  // Sort indicator icon component
  const SortIcon = ({ columnKey, sortConfig }) => {
    const isActive = sortConfig.key === columnKey;
    const isAsc = sortConfig.direction === 'asc';
    
    if (!isActive) {
      // Default unsorted state - show both arrows (chevron up and down)
      return (
        <svg
          aria-hidden="true"
          fill="none"
          focusable="false"
          height="1em"
          role="presentation"
          viewBox="0 0 24 24"
          width="1em"
          className="text-default-400 opacity-50"
        >
          <path
            d="M12 6l4 4H8l4-4z"
            fill="currentColor"
          />
          <path
            d="M12 18l-4-4h8l-4 4z"
            fill="currentColor"
          />
        </svg>
      );
    }
    
    // Active sorted state - show single arrow
    return (
      <svg
        aria-hidden="true"
        fill="none"
        focusable="false"
        height="1em"
        role="presentation"
        viewBox="0 0 24 24"
        width="1em"
        className="text-foreground"
      >
        {isAsc ? (
          <path
            d="M12 6l4 4H8l4-4z"
            fill="currentColor"
          />
        ) : (
          <path
            d="M12 18l-4-4h8l-4 4z"
            fill="currentColor"
          />
        )}
      </svg>
    );
  };

  useEffect(() => {
    fetchTokenUsage();
    fetchAgents();
    fetchInfrastructureCosts();
    const interval = setInterval(() => {
      fetchTokenUsage();
      fetchAgents();
      fetchInfrastructureCosts();
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  const deployAgent = async () => {
    if (!tenantId) {
      alert('Please enter a Tenant ID');
      return;
    }
    
    // Validate token limit for new tenants
    if (tenantExists === false) {
      const validation = validateTokenLimit(tokenLimit);
      if (!validation.valid) {
        setTokenLimitError(validation.error);
        return;
      }
    }
    
    setDeployLoading(true);
    setDeploymentStatus('Starting agent deployment...');
    try {
      // If new tenant, set token limit first
      if (tenantExists === false && tokenLimit) {
        try {
          await axios.post(
            `${API_ENDPOINT}/tenant-limit`,
            { tenantId, tokenLimit: parseInt(tokenLimit, 10) },
            { headers: { 'Content-Type': 'application/json', 'x-api-key': API_KEY } }
          );
        } catch (limitError) {
          console.error('Error setting token limit:', limitError);
          setDeploymentStatus(`Error setting token limit: ${limitError.response?.data?.error || limitError.message}`);
          setDeployLoading(false);
          return;
        }
      }
      
      const payload = { config: agentConfig };
      if (useCustomTemplate && templateConfig.repo) {
        payload.template = {
          source: 'github',
          repo: extractRepoPath(templateConfig.repo),
          path: templateConfig.path || 'templates/main.py',
          branch: templateConfig.branch || 'main',
          token: templateConfig.token || undefined
        };
      }
      if (selectedTools.length > 0 && toolsRepo) {
        payload.tools = {
          repo: extractRepoPath(toolsRepo),
          branch: templateConfig.branch || 'main',
          selected: selectedTools.map(tool => ({ id: tool.id, config: tool.config || {} }))
        };
      }
      const response = await axios.post(
        `${API_ENDPOINT}/deploy?tenantId=${tenantId}`,
        payload,
        { headers: { 'x-api-key': API_KEY, 'Content-Type': 'application/json' }, timeout: 30000 }
      );
      const data = typeof response.data === 'string' ? JSON.parse(response.data) : response.data;
      if (response.status === 202 || data.status === 'deploying') {
        setIsModalOpen(false);
        setDeploymentNotification({ tenantId, status: 'deploying', message: `Deploying agent for tenant: ${tenantId}...` });
        setDeploymentStatus('');
        setDeployedAgent({ tenantId, status: 'deploying', note: 'Agent is being deployed in the background' });
        let pollCount = 0;
        const maxPolls = 36;
        const pollInterval = setInterval(async () => {
          pollCount++;
          try {
            const agentResponse = await axios.get(`${API_ENDPOINT}/agent?tenantId=${tenantId}`, {
              headers: { 'x-api-key': API_KEY }
            });
            if (agentResponse.status === 200 && agentResponse.data) {
              clearInterval(pollInterval);
              setDeployedAgent(agentResponse.data);
              setDeploymentNotification(null);
              fetchAgents();
              fetchTokenUsage();
            }
          } catch (error) {
            if (error.response?.status !== 404) console.error('Error polling:', error);
          }
          fetchTokenUsage();
          if (pollCount >= maxPolls) {
            clearInterval(pollInterval);
            setDeploymentNotification({ tenantId, status: 'timeout', message: 'Deployment taking longer than expected.' });
            setTimeout(() => setDeploymentNotification(null), 10000);
          }
        }, 5000);
      } else {
        setDeployedAgent(data);
        setIsModalOpen(false);
        setDeploymentNotification({ tenantId, status: 'success', message: `Agent deployed successfully!` });
        setTimeout(() => setDeploymentNotification(null), 5000);
      }
      fetchTokenUsage();
    } catch (error) {
      setDeploymentStatus(error.code === 'ECONNABORTED' ? 'Request timeout.' : `Error: ${error.response?.data?.error || error.message}`);
    } finally {
      setDeployLoading(false);
    }
  };

  const invokeAgent = async () => {
    if (!selectedAgentForInvoke || !invokeMessage) {
      alert('Please select an agent and enter a message');
      return;
    }
    setInvokeLoading(true);
    setInvokeResponse('Invoking agent...');
    try {
      const response = await axios.post(
        `${API_ENDPOINT}/invoke`,
        { 
          agentId: selectedAgentForInvoke.agentRuntimeArn, 
          inputText: invokeMessage, 
          sessionId: `session-${Date.now()}`,
          tenantId: selectedAgentForInvoke.tenantId  // Pass tenant ID for limit checking
        },
        { headers: { 'Content-Type': 'application/json', 'x-api-key': API_KEY }, timeout: 60000 }
      );
      const extractText = (obj) => {
        if (typeof obj === 'string') {
          if (obj.trim().startsWith('{') || obj.trim().startsWith('[')) {
            try { obj = JSON.parse(obj); } catch (e) {
              try { obj = JSON.parse(obj.replace(/'/g, '"').replace(/True/g, 'true').replace(/False/g, 'false').replace(/None/g, 'null')); } catch (e2) { return obj; }
            }
          } else return obj;
        }
        if (typeof obj === 'object' && obj !== null) {
          if (obj.result) return extractText(obj.result);
          if (obj.role && obj.content) return extractText(obj.content);
          if (Array.isArray(obj.content)) return obj.content.map(item => typeof item === 'string' ? item : item.text || '').filter(Boolean).join('\n\n');
          if (Array.isArray(obj)) return obj.map(item => typeof item === 'string' ? item : item.text || extractText(item)).filter(Boolean).join('\n\n');
          if (obj.text) return obj.text;
          if (obj.message) return extractText(obj.message);
          if (obj.completion) return extractText(obj.completion);
        }
        return typeof obj === 'string' ? obj : JSON.stringify(obj);
      };
      let responseText = extractText(response.data).replace(/\\n/g, '\n').replace(/\\t/g, '\t');
      setInvokeResponse(responseText);
      setTimeout(() => fetchTokenUsage(), 2000);
    } catch (error) {
      setInvokeResponse(`Error: ${error.response?.data?.error || error.message || 'Unknown error'}`);
    } finally {
      setInvokeLoading(false);
    }
  };

  const getStatusColor = (status) => {
    const s = status?.toLowerCase();
    if (s === 'ready' || s === 'READY') return 'success';
    if (s === 'deploying' || s === 'CREATING') return 'warning';
    if (s === 'failed' || s === 'FAILED') return 'danger';
    return 'default';
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-separator bg-surface px-6 py-4">
        <div className="mx-auto max-w-7xl flex items-center justify-between">
          <div className="flex-1" />
          <div className="text-center">
            <h1 className="text-2xl font-bold text-foreground">✨ Bedrock Agent Dashboard</h1>
            <p className="text-sm text-muted">Deploy and manage your AI agents</p>
          </div>
          <div className="flex-1 flex items-center justify-end">
            <button
              onClick={() => setIsDarkMode(!isDarkMode)}
              className={`w-10 h-10 rounded-full border-2 flex items-center justify-center hover:border-accent transition-colors ${isDarkMode ? 'border-gray-500' : 'border-separator'}`}
              aria-label={isDarkMode ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              {isDarkMode ? (
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="5" />
                  <line x1="12" y1="1" x2="12" y2="3" />
                  <line x1="12" y1="21" x2="12" y2="23" />
                  <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
                  <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
                  <line x1="1" y1="12" x2="3" y2="12" />
                  <line x1="21" y1="12" x2="23" y2="12" />
                  <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
                  <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
                </svg>
              ) : (
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
                </svg>
              )}
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl p-6 space-y-6">
        {/* Notification Banner */}
        {deploymentNotification && (
          <div className={`flex items-center justify-between rounded-xl p-4 ${
            deploymentNotification.status === 'deploying' ? 'bg-accent-soft' :
            deploymentNotification.status === 'success' ? 'bg-success-soft' : 'bg-warning-soft'
          }`}>
            <div className="flex items-center gap-3">
              {deploymentNotification.status === 'deploying' && (
                <svg className="w-5 h-5 animate-spin text-accent" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" strokeOpacity="0.25" />
                  <path d="M12 2a10 10 0 0 1 10 10" strokeLinecap="round" />
                </svg>
              )}
              {deploymentNotification.status === 'success' && (
                <svg className="w-5 h-5 text-success" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10" />
                  <path d="M9 12l2 2 4-4" />
                </svg>
              )}
              {deploymentNotification.status === 'timeout' && (
                <svg className="w-5 h-5 text-warning" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12 6 12 12 16 14" />
                </svg>
              )}
              <span className="font-medium">{deploymentNotification.message}</span>
            </div>
            <Button variant="ghost" size="sm" isIconOnly onPress={() => setDeploymentNotification(null)}>×</Button>
          </div>
        )}

        {/* Deploy Button */}
        <Button onPress={() => setIsModalOpen(true)} size="lg" variant="primary">➕ Deploy New Agent</Button>

        {/* Invoke Agent Card */}
        <Card>
          <Card.Header>
            <Card.Title>Invoke Agent</Card.Title>
            <Card.Description>Send messages to your deployed agents</Card.Description>
          </Card.Header>
          <Card.Content className="space-y-4">
            <Select
              className="w-full"
              placeholder="Select an agent"
              isDisabled={invokeLoading || agents.length === 0}
              value={selectedAgentForInvoke?.agentRuntimeId ?? null}
              onChange={(key) => setSelectedAgentForInvoke(agents.find(a => a.agentRuntimeId === key) || null)}
            >
              <Label>Select Agent</Label>
              <Select.Trigger>
                <Select.Value />
                <Select.Indicator />
              </Select.Trigger>
              <Select.Popover>
                <ListBox>
                  {agents.length === 0 ? (
                    <ListBox.Item id="none" textValue="No agents">No agents available<ListBox.ItemIndicator /></ListBox.Item>
                  ) : agents.map((agent) => (
                    <ListBox.Item key={agent.agentRuntimeId} id={agent.agentRuntimeId} textValue={`${agent.tenantId} - ${agent.agentName || 'Unnamed'}`}>
                      {agent.tenantId} - {agent.agentName || 'Unnamed'} ({agent.status || 'unknown'})
                      <ListBox.ItemIndicator />
                    </ListBox.Item>
                  ))}
                </ListBox>
              </Select.Popover>
            </Select>

            {selectedAgentForInvoke && (
              <div className="rounded-lg bg-surface-secondary p-4 space-y-1">
                <p className="text-sm"><span className="font-medium">Selected:</span> {selectedAgentForInvoke.agentName || selectedAgentForInvoke.tenantId}</p>
                <p className="text-sm"><span className="font-medium">Tenant:</span> {selectedAgentForInvoke.tenantId}</p>
                <p className="text-sm flex items-center gap-2">
                  <span className="font-medium">Status:</span>
                  <Chip size="sm" color={getStatusColor(selectedAgentForInvoke.status)}>{selectedAgentForInvoke.status || 'unknown'}</Chip>
                </p>
              </div>
            )}

            <TextField className="w-full" onChange={setInvokeMessage}>
              <Label>Message</Label>
              <TextArea
                placeholder="Enter your message to the agent..."
                rows={4}
                value={invokeMessage}
                disabled={invokeLoading || !selectedAgentForInvoke}
              />
            </TextField>

            <Button onPress={invokeAgent} isDisabled={invokeLoading || !selectedAgentForInvoke} isPending={invokeLoading} variant="primary">
              {({ isPending }) => isPending ? <><Spinner size="sm" color="current" /> Invoking...</> : 'Invoke Agent'}
            </Button>

            {invokeResponse && (
              <div className="rounded-lg bg-surface-secondary p-4">
                <h3 className="font-semibold mb-2">Response:</h3>
                <div className="whitespace-pre-wrap font-mono text-sm">{invokeResponse}</div>
              </div>
            )}
          </Card.Content>
        </Card>

        {/* Active Agents Card */}
        <Card>
          <Card.Header className="flex flex-row items-center justify-between">
            <div>
              <Card.Title>Active Agents</Card.Title>
              <Card.Description>Manage your deployed agents</Card.Description>
            </div>
            <Button variant="secondary" size="sm" onPress={fetchAgents}>Refresh</Button>
          </Card.Header>
          <Card.Content>
            {agents.length === 0 ? (
              <p className="text-center text-muted py-8">No active agents found.</p>
            ) : (
              <div className="relative overflow-x-auto">
                <table className="min-w-full">
                  <thead>
                    <tr className="border-b border-divider">
                      <th 
                        className="group px-3 py-3 text-left text-xs font-semibold uppercase tracking-wider cursor-pointer select-none hover:bg-default-100 transition-colors"
                        onClick={() => handleAgentsSort('tenantId')}
                      >
                        <div className="flex items-center gap-1">
                          <span>Tenant ID</span>
                          <SortIcon columnKey="tenantId" sortConfig={agentsSortConfig} />
                        </div>
                      </th>
                      <th 
                        className="group px-3 py-3 text-left text-xs font-semibold uppercase tracking-wider cursor-pointer select-none hover:bg-default-100 transition-colors"
                        onClick={() => handleAgentsSort('agentName')}
                      >
                        <div className="flex items-center gap-1">
                          <span>Agent Name</span>
                          <SortIcon columnKey="agentName" sortConfig={agentsSortConfig} />
                        </div>
                      </th>
                      <th 
                        className="group px-3 py-3 text-left text-xs font-semibold uppercase tracking-wider cursor-pointer select-none hover:bg-default-100 transition-colors"
                        onClick={() => handleAgentsSort('agentRuntimeId')}
                      >
                        <div className="flex items-center gap-1">
                          <span>Agent ID</span>
                          <SortIcon columnKey="agentRuntimeId" sortConfig={agentsSortConfig} />
                        </div>
                      </th>
                      <th 
                        className="group px-3 py-3 text-left text-xs font-semibold uppercase tracking-wider cursor-pointer select-none hover:bg-default-100 transition-colors"
                        onClick={() => handleAgentsSort('status')}
                      >
                        <div className="flex items-center gap-1">
                          <span>Status</span>
                          <SortIcon columnKey="status" sortConfig={agentsSortConfig} />
                        </div>
                      </th>
                      <th 
                        className="group px-3 py-3 text-left text-xs font-semibold uppercase tracking-wider cursor-pointer select-none hover:bg-default-100 transition-colors"
                        onClick={() => handleAgentsSort('deployedAt')}
                      >
                        <div className="flex items-center gap-1">
                          <span>Deployed At</span>
                          <SortIcon columnKey="deployedAt" sortConfig={agentsSortConfig} />
                        </div>
                      </th>
                      <th className="px-3 py-3 text-left text-xs font-semibold uppercase tracking-wider">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-divider">
                    {sortData(agents, agentsSortConfig).map((agent, index) => (
                      <tr 
                        key={agent.agentRuntimeId} 
                        className={`group hover:bg-default-50 transition-colors ${index % 2 === 0 ? '' : 'bg-default-50/50'}`}
                      >
                        <td className="px-3 py-4 text-sm font-medium">{agent.tenantId}</td>
                        <td className="px-3 py-4 text-sm">{agent.agentName || 'N/A'}</td>
                        <td className="px-3 py-4 text-sm">
                          <code className="text-xs bg-default-100 px-2 py-1 rounded font-mono">
                            {agent.agentRuntimeId || 'N/A'}
                          </code>
                        </td>
                        <td className="px-3 py-4 text-sm">
                          <Chip size="sm" color={getStatusColor(agent.status)} variant="flat">
                            {agent.status || 'unknown'}
                          </Chip>
                        </td>
                        <td className="px-3 py-4 text-sm text-default-600">
                          {agent.deployedAt ? new Date(agent.deployedAt).toLocaleString() : 'N/A'}
                        </td>
                        <td className="px-3 py-4 text-sm">
                          <Button 
                            color="danger" 
                            size="sm" 
                            variant="flat"
                            onPress={() => deleteAgent(agent.tenantId, agent.agentRuntimeId, agent.agentName)}
                          >
                            🗑️ Delete
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card.Content>
        </Card>

        {/* Token Usage Card */}
        <Card>
          <Card.Header className="flex flex-row items-center justify-between">
            <div>
              <Card.Title>Token Usage by Tenant</Card.Title>
              <Card.Description>Monitor token consumption and costs</Card.Description>
            </div>
            <Button variant="secondary" size="sm" onPress={fetchTokenUsage}>Refresh</Button>
          </Card.Header>
          <Card.Content className="space-y-6">
            {tokenUsage.length === 0 ? (
              <p className="text-center text-muted py-8">No token usage data available yet.</p>
            ) : (
              <>
                <div className="relative overflow-x-auto">
                  <table className="min-w-full">
                    <thead>
                      <tr className="border-b border-divider">
                        <th 
                          className="group px-3 py-3 text-left text-xs font-semibold uppercase tracking-wider cursor-pointer select-none hover:bg-default-100 transition-colors"
                          onClick={() => handleUsageSort('tenant_id')}
                        >
                          <div className="flex items-center gap-1">
                            <span>Tenant ID</span>
                            <SortIcon columnKey="tenant_id" sortConfig={usageSortConfig} />
                          </div>
                        </th>
                        <th 
                          className="group px-3 py-3 text-left text-xs font-semibold uppercase tracking-wider cursor-pointer select-none hover:bg-default-100 transition-colors"
                          onClick={() => handleUsageSort('input_tokens')}
                        >
                          <div className="flex items-center gap-1">
                            <span>Input Tokens</span>
                            <SortIcon columnKey="input_tokens" sortConfig={usageSortConfig} />
                          </div>
                        </th>
                        <th 
                          className="group px-3 py-3 text-left text-xs font-semibold uppercase tracking-wider cursor-pointer select-none hover:bg-default-100 transition-colors"
                          onClick={() => handleUsageSort('output_tokens')}
                        >
                          <div className="flex items-center gap-1">
                            <span>Output Tokens</span>
                            <SortIcon columnKey="output_tokens" sortConfig={usageSortConfig} />
                          </div>
                        </th>
                        <th 
                          className="group px-3 py-3 text-left text-xs font-semibold uppercase tracking-wider cursor-pointer select-none hover:bg-default-100 transition-colors"
                          onClick={() => handleUsageSort('total_tokens')}
                        >
                          <div className="flex items-center gap-1">
                            <span>Total Tokens</span>
                            <SortIcon columnKey="total_tokens" sortConfig={usageSortConfig} />
                          </div>
                        </th>
                        <th 
                          className="group px-3 py-3 text-left text-xs font-semibold uppercase tracking-wider cursor-pointer select-none hover:bg-default-100 transition-colors"
                          onClick={() => handleUsageSort('request_count')}
                        >
                          <div className="flex items-center gap-1">
                            <span>Requests</span>
                            <SortIcon columnKey="request_count" sortConfig={usageSortConfig} />
                          </div>
                        </th>
                        <th 
                          className="group px-3 py-3 text-left text-xs font-semibold uppercase tracking-wider cursor-pointer select-none hover:bg-default-100 transition-colors"
                          onClick={() => handleUsageSort('total_cost')}
                        >
                          <div className="flex items-center gap-1">
                            <span>Inference Cost</span>
                            <SortIcon columnKey="total_cost" sortConfig={usageSortConfig} />
                          </div>
                        </th>
                        <th 
                          className="group px-3 py-3 text-left text-xs font-semibold uppercase tracking-wider cursor-pointer select-none hover:bg-default-100 transition-colors"
                          onClick={() => handleUsageSort('infrastructure_cost')}
                        >
                          <div className="flex items-center gap-1">
                            <span>Infra Cost</span>
                            <SortIcon columnKey="infrastructure_cost" sortConfig={usageSortConfig} />
                          </div>
                        </th>
                        <th 
                          className="group px-3 py-3 text-left text-xs font-semibold uppercase tracking-wider cursor-pointer select-none hover:bg-default-100 transition-colors"
                          onClick={() => handleUsageSort('combined_total_cost')}
                        >
                          <div className="flex items-center gap-1">
                            <span>Total Cost</span>
                            <SortIcon columnKey="combined_total_cost" sortConfig={usageSortConfig} />
                          </div>
                        </th>
                        <th 
                          className="group px-3 py-3 text-left text-xs font-semibold uppercase tracking-wider"
                        >
                          <div className="flex items-center gap-1">
                            <span>Usage %</span>
                          </div>
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-divider">
                      {sortData(tokenUsage.filter(item => item.aggregation_key?.startsWith('tenant:')).map(item => {
                        // Find infrastructure cost for this tenant
                        const infraCostData = infrastructureCosts.find(ic => ic.tenant_id === item.tenant_id);
                        const infrastructureCost = infraCostData ? Number(infraCostData.infrastructure_cost) || 0 : 0;
                        const inputTokens = Number(item.input_tokens) || 0;
                        const outputTokens = Number(item.output_tokens) || 0;
                        const inferenceCost = Number(item.total_cost) || ((inputTokens * 0.003 / 1000) + (outputTokens * 0.015 / 1000));
                        return {
                          ...item,
                          infrastructure_cost: infrastructureCost,
                          combined_total_cost: inferenceCost + infrastructureCost
                        };
                      }), usageSortConfig).map((item, index) => {
                        const inputTokens = Number(item.input_tokens) || 0;
                        const outputTokens = Number(item.output_tokens) || 0;
                        const totalTokens = Number(item.total_tokens) || 0;
                        const tokenLimitValue = item.token_limit ? Number(item.token_limit) : null;
                        const usagePercentage = calculateUsagePercentage(totalTokens, tokenLimitValue);
                        const inferenceCost = Number(item.total_cost) || ((inputTokens * 0.003 / 1000) + (outputTokens * 0.015 / 1000));
                        const infrastructureCost = item.infrastructure_cost || 0;
                        const totalCost = inferenceCost + infrastructureCost;
                        return (
                          <tr 
                            key={item.aggregation_key} 
                            className={`group hover:bg-default-50 transition-colors ${index % 2 === 0 ? '' : 'bg-default-50/50'}`}
                          >
                            <td className="px-3 py-4 text-sm font-medium">{item.tenant_id}</td>
                            <td className="px-3 py-4 text-sm text-default-600">{inputTokens.toLocaleString()}</td>
                            <td className="px-3 py-4 text-sm text-default-600">{outputTokens.toLocaleString()}</td>
                            <td className="px-3 py-4 text-sm font-medium">{totalTokens.toLocaleString()}</td>
                            <td className="px-3 py-4 text-sm text-default-600">{Number(item.request_count) || 0}</td>
                            <td className="px-3 py-4 text-sm font-mono text-default-600">${inferenceCost.toFixed(6)}</td>
                            <td className="px-3 py-4 text-sm font-mono text-default-600">${infrastructureCost.toFixed(6)}</td>
                            <td className="px-3 py-4 text-sm font-mono font-semibold text-success">${totalCost.toFixed(6)}</td>
                            <td className="px-3 py-4 text-sm">
                              {usagePercentage !== null ? (
                                <Chip size="sm" color={getUsageColor(usagePercentage)} variant="flat">
                                  {usagePercentage.toFixed(1)}%
                                </Chip>
                              ) : (
                                <span className="text-muted">No Limit</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Cost Summary */}
                <div className="rounded-xl bg-success-soft p-6">
                  <h3 className="font-semibold mb-4">💰 Cost Summary</h3>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <p className="text-sm text-muted">Inference Cost</p>
                      <p className="text-2xl font-bold font-mono">
                        ${tokenUsage.filter(item => item.aggregation_key?.startsWith('tenant:')).reduce((sum, item) => {
                          const inputTokens = Number(item.input_tokens) || 0;
                          const outputTokens = Number(item.output_tokens) || 0;
                          return sum + (Number(item.total_cost) || ((inputTokens * 0.003 / 1000) + (outputTokens * 0.015 / 1000)));
                        }, 0).toFixed(6)}
                      </p>
                    </div>
                    <div>
                      <p className="text-sm text-muted">Infrastructure Cost</p>
                      <p className="text-2xl font-bold font-mono">
                        ${infrastructureCosts.reduce((sum, item) => sum + (Number(item.infrastructure_cost) || 0), 0).toFixed(6)}
                      </p>
                    </div>
                    <div>
                      <p className="text-sm text-muted">Total Cost (All Tenants)</p>
                      <p className="text-3xl font-bold font-mono text-success">
                        ${(tokenUsage.filter(item => item.aggregation_key?.startsWith('tenant:')).reduce((sum, item) => {
                          const inputTokens = Number(item.input_tokens) || 0;
                          const outputTokens = Number(item.output_tokens) || 0;
                          return sum + (Number(item.total_cost) || ((inputTokens * 0.003 / 1000) + (outputTokens * 0.015 / 1000)));
                        }, 0) + infrastructureCosts.reduce((sum, item) => sum + (Number(item.infrastructure_cost) || 0), 0)).toFixed(6)}
                      </p>
                    </div>
                  </div>
                  <div className="mt-4 pt-4 border-t border-success/20">
                    <p className="text-sm text-muted">Pricing</p>
                    <p className="text-sm font-mono">Input: $0.003/1K tokens | Output: $0.015/1K tokens</p>
                  </div>
                </div>

                {/* Cost Chart */}
                <div className="rounded-xl bg-surface-secondary p-6">
                  <h3 className="font-semibold mb-4">📊 Total Cost per Tenant</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart
                      data={tokenUsage.filter(item => item.aggregation_key?.startsWith('tenant:')).map(item => {
                        const inputTokens = Number(item.input_tokens) || 0;
                        const outputTokens = Number(item.output_tokens) || 0;
                        const inferenceCost = Number(item.total_cost) || ((inputTokens * 0.003 / 1000) + (outputTokens * 0.015 / 1000));
                        const infraCostData = infrastructureCosts.find(ic => ic.tenant_id === item.tenant_id);
                        const infraCost = infraCostData ? Number(infraCostData.infrastructure_cost) || 0 : 0;
                        const totalCost = inferenceCost + infraCost;
                        return { 
                          tenant: item.tenant_id, 
                          totalCost: parseFloat(totalCost.toFixed(6)),
                          inferenceCost: parseFloat(inferenceCost.toFixed(6)),
                          infraCost: parseFloat(infraCost.toFixed(6)),
                          requests: Number(item.request_count) || 0 
                        };
                      }).sort((a, b) => b.totalCost - a.totalCost)}
                      margin={{ top: 20, right: 30, left: 20, bottom: 60 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="tenant" angle={-45} textAnchor="end" height={80} style={{ fontSize: '12px' }} />
                      <YAxis label={{ value: 'Cost ($)', angle: -90, position: 'insideLeft' }} style={{ fontSize: '12px' }} />
                      <Tooltip 
                        content={({ active, payload, label }) => {
                          if (active && payload && payload.length) {
                            const data = payload[0].payload;
                            return (
                              <div className="bg-surface border border-divider rounded-lg p-3 shadow-lg">
                                <p className="font-semibold mb-2">{label}</p>
                                <p className="text-sm font-mono">Inference: ${data.inferenceCost}</p>
                                <p className="text-sm font-mono">Infrastructure: ${data.infraCost}</p>
                                <p className="text-sm font-mono font-semibold text-success">Total: ${data.totalCost}</p>
                              </div>
                            );
                          }
                          return null;
                        }}
                      />
                      <Legend />
                      <Bar dataKey="totalCost" name="Total Cost" fill="var(--color-accent)">
                        {tokenUsage.filter(item => item.aggregation_key?.startsWith('tenant:')).map((_, index) => (
                          <Cell key={`cell-${index}`} fill={`hsl(${250 + index * 30}, 70%, 60%)`} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </>
            )}
          </Card.Content>
        </Card>

        {/* Footer */}
        <footer className="text-center py-6 text-sm text-muted">
          Powered by AWS Bedrock Agent Core
        </footer>
      </main>

      {/* Deploy Agent Modal */}
      <Modal.Backdrop isOpen={isModalOpen} onOpenChange={setIsModalOpen}>
        <Modal.Container size="lg">
          <Modal.Dialog>
            <Modal.CloseTrigger />
            <Modal.Header>
              <Modal.Heading>Deploy New Agent</Modal.Heading>
            </Modal.Header>
            <Modal.Body className="space-y-4">
              <TextField className="w-full" onChange={setTenantId}>
                <Label>Tenant ID</Label>
                <Input placeholder="e.g., tenant-123" value={tenantId} disabled={deployLoading} />
              </TextField>

              {/* Token Limit for New Tenants */}
              {tenantExists === false && (
                <div className="space-y-2">
                  <TextField 
                    className="w-full" 
                    onChange={(val) => {
                      setTokenLimit(val);
                      if (val) {
                        const validation = validateTokenLimit(val);
                        setTokenLimitError(validation.error);
                      } else {
                        setTokenLimitError('');
                      }
                    }}
                    isInvalid={!!tokenLimitError}
                  >
                    <Label>Token Limit (Required for New Tenant)</Label>
                    <Input 
                      type="number" 
                      placeholder="e.g., 100000" 
                      value={tokenLimit} 
                      disabled={deployLoading}
                      min="1"
                    />
                    <Description>Maximum total tokens (input + output) allowed for this tenant</Description>
                  </TextField>
                  {tokenLimitError && (
                    <p className="text-sm text-danger">{tokenLimitError}</p>
                  )}
                </div>
              )}
              
              {tenantExists === true && (
                <div className="p-3 rounded-lg bg-accent-soft text-sm">
                  ℹ️ This tenant already exists. Token limit was set during initial creation.
                </div>
              )}

              <Button variant="secondary" onPress={() => setShowAdvancedConfig(!showAdvancedConfig)}>
                {showAdvancedConfig ? '▼ Hide' : '▶ Show'} Advanced Configuration
              </Button>

              {showAdvancedConfig && (
                <div className="space-y-4 rounded-lg bg-surface-secondary p-4">
                  <Select
                    className="w-full"
                    value={agentConfig.modelId}
                    onChange={(key) => setAgentConfig({ ...agentConfig, modelId: key })}
                  >
                    <Label>Model ID</Label>
                    <Select.Trigger className="modal-select-trigger">
                      <Select.Value />
                      <Select.Indicator />
                    </Select.Trigger>
                    <Select.Popover>
                      <ListBox>
                        <ListBox.Item id="global.anthropic.claude-opus-4-5-20251101-v1:0" textValue="Claude Opus 4.5">Claude Opus 4.5<ListBox.ItemIndicator /></ListBox.Item>
                        <ListBox.Item id="global.anthropic.claude-sonnet-4-5-20250929-v1:0" textValue="Claude Sonnet 4.5">Claude Sonnet 4.5<ListBox.ItemIndicator /></ListBox.Item>
                        <ListBox.Item id="global.anthropic.claude-haiku-4-5-20251001-v1:0" textValue="Claude Haiku 4.5">Claude Haiku 4.5<ListBox.ItemIndicator /></ListBox.Item>
                      </ListBox>
                    </Select.Popover>
                  </Select>

                  <TextField className="w-full" onChange={(val) => setAgentConfig({ ...agentConfig, systemPrompt: val })}>
                    <Label>System Prompt</Label>
                    <TextArea placeholder="You are a helpful AI assistant." rows={3} value={agentConfig.systemPrompt} disabled={deployLoading} />
                  </TextField>

                  <Checkbox isSelected={useCustomTemplate} onChange={setUseCustomTemplate} isDisabled={deployLoading} className="modal-checkbox">
                    <Checkbox.Control className="modal-checkbox-control"><Checkbox.Indicator /></Checkbox.Control>
                    <Label>Use Custom Template from GitHub</Label>
                  </Checkbox>

                  {useCustomTemplate && (
                    <div className="space-y-4 rounded-lg bg-surface p-4">
                      <TextField className="w-full" onChange={(val) => { setTemplateConfig({ ...templateConfig, repo: val }); setToolsRepo(val); }}>
                        <Label>GitHub Repository (owner/repo)</Label>
                        <Input placeholder="e.g., your-org/agent-templates" value={templateConfig.repo} disabled={deployLoading} />
                      </TextField>

                      <TextField className="w-full" onChange={(val) => setTemplateConfig({ ...templateConfig, path: val })}>
                        <Label>File Path</Label>
                        <Input placeholder="e.g., templates/main.py" value={templateConfig.path} disabled={deployLoading} />
                      </TextField>

                      <TextField className="w-full" onChange={(val) => setTemplateConfig({ ...templateConfig, branch: val })}>
                        <Label>Branch</Label>
                        <Input placeholder="main" value={templateConfig.branch} disabled={deployLoading} />
                      </TextField>

                      <TextField className="w-full" onChange={(val) => setTemplateConfig({ ...templateConfig, token: val })}>
                        <Label>GitHub Token (optional)</Label>
                        <Input type="password" placeholder="ghp_xxxxxxxxxxxx" value={templateConfig.token} disabled={deployLoading} />
                        <Description>Leave empty for public repositories</Description>
                      </TextField>

                      {/* Tools Section */}
                      <div className="border-t border-border pt-4 mt-4">
                        <h4 className="font-semibold mb-3">🛠️ Select Tools for Agent</h4>
                        <Button variant="secondary" onPress={fetchToolCatalog} isDisabled={!toolsRepo || loadingTools || deployLoading} isPending={loadingTools}>
                          {({ isPending }) => isPending ? <><Spinner size="sm" color="current" /> Loading...</> : 'Load Available Tools'}
                        </Button>

                        {availableTools.length > 0 && (
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
                            {availableTools.map((tool) => {
                              const isSelected = selectedTools.some(t => t.id === tool.id);
                              return (
                                <div
                                  key={tool.id}
                                  className={`relative p-4 rounded-lg border-2 cursor-pointer transition-colors ${isSelected ? 'border-accent bg-accent-soft' : 'border-border hover:border-accent'}`}
                                  onClick={() => !deployLoading && toggleToolSelection(tool)}
                                >
                                  <div className="flex gap-3">
                                    <span className="text-2xl">🔧</span>
                                    <div className="flex-1">
                                      <p className="font-medium">{tool.name}</p>
                                      <p className="text-sm text-muted">{tool.description}</p>
                                      <p className="text-xs text-muted mt-1">{tool.category}</p>
                                    </div>
                                  </div>
                                  {isSelected && <div className="absolute -top-2 -right-2 bg-accent text-white w-6 h-6 rounded-full flex items-center justify-center text-sm">✓</div>}
                                </div>
                              );
                            })}
                          </div>
                        )}

                        {selectedTools.length > 0 && (
                          <div className="mt-4 p-4 rounded-lg bg-success-soft">
                            <p className="font-medium mb-2">Selected Tools ({selectedTools.length}):</p>
                            <div className="flex flex-wrap gap-2">
                              {selectedTools.map(tool => (
                                <Chip key={tool.id} color="success">🔧 {tool.name}</Chip>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {deploymentStatus && (
                <div className={`p-4 rounded-lg ${deploymentStatus.includes('Error') ? 'bg-danger-soft' : 'bg-success-soft'}`}>
                  {deploymentStatus}
                </div>
              )}

              {deployedAgent && (
                <div className="p-4 rounded-lg bg-surface-secondary">
                  <h3 className="font-semibold mb-2">Deployed Agent Details</h3>
                  <p className="text-sm"><span className="font-medium">Tenant ID:</span> {deployedAgent.tenantId}</p>
                  {deployedAgent.status === 'deploying' ? (
                    <div className="mt-2">
                      <p className="text-sm flex items-center gap-2"><Spinner size="sm" /> Deploying in background...</p>
                      <p className="text-xs text-muted mt-1">Agent details will be available once deployment completes</p>
                    </div>
                  ) : (
                    <>
                      <p className="text-sm"><span className="font-medium">Agent Name:</span> {deployedAgent.agentName || 'N/A'}</p>
                      <p className="text-sm"><span className="font-medium">Agent ID:</span> {deployedAgent.agentRuntimeId || 'N/A'}</p>
                      <p className="text-sm"><span className="font-medium">Endpoint:</span> <code className="text-xs bg-surface-tertiary px-2 py-1 rounded">{deployedAgent.agentEndpointUrl || 'N/A'}</code></p>
                      {deployedAgent.deployedAt && <p className="text-sm"><span className="font-medium">Deployed At:</span> {new Date(deployedAgent.deployedAt).toLocaleString()}</p>}
                    </>
                  )}
                </div>
              )}
            </Modal.Body>
            <Modal.Footer>
              <Button variant="secondary" slot="close" isDisabled={deployLoading}>Cancel</Button>
              <Button onPress={deployAgent} isDisabled={deployLoading} isPending={deployLoading} variant="primary">
                {({ isPending }) => isPending ? <><Spinner size="sm" color="current" /> Deploying...</> : 'Deploy Agent'}
              </Button>
            </Modal.Footer>
          </Modal.Dialog>
        </Modal.Container>
      </Modal.Backdrop>
    </div>
  );
}

export default App;
