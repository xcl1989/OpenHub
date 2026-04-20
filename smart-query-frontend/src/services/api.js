import axios from 'axios';

// 从环境变量读取 API 地址，开发环境使用 /api 代理
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
  maxContentLength: 50 * 1024 * 1024,
  maxBodyLength: 50 * 1024 * 1024,
  headers: {
    'Content-Type': 'application/json',
  },
});

// token 管理
let authToken = localStorage.getItem('auth_token');

export const setAuthToken = (token) => {
  authToken = token;
  if (token) {
    localStorage.setItem('auth_token', token);
  } else {
    localStorage.removeItem('auth_token');
  }
};

export const getAuthToken = () => localStorage.getItem('auth_token') || authToken;

export const clearAuthToken = () => {
  authToken = null;
  localStorage.removeItem('auth_token');
};

// 请求拦截器，自动添加 token
apiClient.interceptors.request.use(
  (config) => {
    const token = getAuthToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// 响应拦截器，处理 401 错误
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      clearAuthToken();
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const authService = {
  login: async (username, password) => {
    const response = await apiClient.post('/auth/login', { username, password });
    if (response.data.success && response.data.token) {
      setAuthToken(response.data.token);
    }
    return response.data;
  },

  logout: async () => {
    try {
      await apiClient.post('/auth/logout');
    } finally {
      clearAuthToken();
    }
  },

  getMe: async () => {
    const response = await apiClient.get('/auth/me');
    return response.data;
  },
};

export const queryDataService = {
  health: async () => {
    const response = await apiClient.get('/health');
    return response.data;
  },

  queryData: async (question, conversationId = '') => {
    const response = await apiClient.post('/query', {
      question,
      conversation_id: conversationId,
    });
    return response.data;
  },

  queryDataStream: async (question, conversationId = '', onChunk, onEnd, onError, images = null, agent = 'build', model = null, signal = null) => {
    const MAX_RETRIES = 2;

    const doStream = async (retryCount = 0) => {
      try {
        const token = getAuthToken();
        const requestBody = {
          question,
          conversation_id: conversationId,
          agent,
        };

        if (model) {
          requestBody.model = model;
        }

        if (images && images.length > 0) {
          requestBody.images = images.map(img => ({
            base64: img.base64,
            filename: img.name
          }));
        }

        const response = await fetch(`${API_BASE_URL}/query/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify(requestBody),
          signal,
        });

        if (!response.ok) {
          if (response.status === 401) {
            clearAuthToken();
            window.location.href = '/login';
            return;
          }
          if (response.status === 403) {
            try {
              const errorData = await response.json();
              throw new Error(errorData.detail || '模型调用次数已达上限，请更换模型或联系管理员');
            } catch (e) {
              throw new Error('模型调用次数已达上限，请更换模型或联系管理员');
            }
          }
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let sessionId = null;
        let hasError = false;
        let lastEventType = null;

        while (true) {
          if (signal?.aborted) break;
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop();

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));

                if (data.payload && data.payload.type) {
                  const payloadData = {
                    type: data.payload.type,
                    ...data.payload.properties
                  };
                  lastEventType = data.payload.type;
                  onChunk?.(payloadData);
                } else {
                  if (data.type === 'session' && data.conversation_id) {
                    sessionId = data.conversation_id;
                  }
                  if (data.type === 'error') {
                    hasError = true;
                    onError?.(new Error(data.error));
                  }
                  lastEventType = data.type;
                  onChunk?.(data);
                }

                if (data.done && data.type === 'error') {
                  break;
                }
              } catch (e) {
                console.warn('Failed to parse SSE data:', e, line);
              }
            }
          }
        }

        if (signal?.aborted) {
          onEnd?.(sessionId || conversationId);
          return;
        }

        if (buffer.trim()) {
          const remainingLines = buffer.split('\n');
          for (const line of remainingLines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                if (data.payload && data.payload.type) {
                  lastEventType = data.payload.type;
                  onChunk?.({ type: data.payload.type, ...data.payload.properties });
                } else {
                  if (data.type === 'session' && data.conversation_id) sessionId = data.conversation_id;
                  if (data.type === 'error') { hasError = true; onError?.(new Error(data.error)); }
                  lastEventType = data.type;
                  onChunk?.(data);
                }
              } catch (e) {
                console.warn('Failed to parse SSE data:', e, line);
              }
            }
          }
        }

        if (hasError) return;

        const terminalEvents = ['session_idle', 'message_complete'];
        if (!terminalEvents.includes(lastEventType) && retryCount < MAX_RETRIES) {
          await new Promise(r => setTimeout(r, 2000));
          if (signal?.aborted) {
            onEnd?.(sessionId || conversationId);
            return;
          }
          return doStream(retryCount + 1);
        }

        onEnd?.(sessionId || conversationId);
      } catch (error) {
        if (error.name === 'AbortError') {
          onEnd?.(conversationId);
          return;
        }
        onError?.(error);
      }
    };

    return doStream(0);
  },

  getSessions: async (page = 1, pageSize = 10) => {
    const response = await apiClient.get(`/sessions?page=${page}&page_size=${pageSize}`);
    return response.data;
  },

  getMessages: async (sessionId) => {
    const response = await apiClient.get(`/sessions/${sessionId}/messages`);
    return response.data;
  },

  questionReply: async (questionId, answers) => {
    const response = await apiClient.post(`/question/${questionId}/reply`, { answers });
    return response.data;
  },

  archiveSession: async (sessionId) => {
    const response = await apiClient.post('/session/archive', { session_id: sessionId });
    return response.data;
  },

  undoLastTurn: async (sessionId) => {
    const response = await apiClient.delete(`/sessions/${sessionId}/messages/last-turn`);
    return response.data;
  },

  retryStream: async (sessionId, onChunk, onEnd, onError, signal = null) => {
    try {
      const token = getAuthToken();
      const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/retry`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Accept': 'text/event-stream',
        },
        signal,
      });

      if (!response.ok) {
        if (response.status === 401) {
          clearAuthToken();
          window.location.href = '/login';
          return;
        }
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let lastEventType = null;
      let hasError = false;

      while (true) {
        if (signal?.aborted) break;
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.payload && data.payload.type) {
                lastEventType = data.payload.type;
                onChunk?.({ type: data.payload.type, ...data.payload.properties });
              } else {
                if (data.type === 'error') { hasError = true; onError?.(new Error(data.error)); }
                lastEventType = data.type;
                onChunk?.(data);
              }
              if (data.done && data.type === 'error') break;
            } catch (e) {
              console.warn('Failed to parse SSE data:', e, line);
            }
          }
        }
      }

      if (signal?.aborted) { onEnd?.(sessionId); return; }
      if (hasError) return;
      onEnd?.(sessionId);
    } catch (error) {
      if (error.name === 'AbortError') { onEnd?.(sessionId); return; }
      onError?.(error);
    }
  },

  reconnectStream: async (sessionId, onChunk, onEnd, onError, signal = null) => {
    try {
      const token = getAuthToken();
      const response = await fetch(`${API_BASE_URL}/query/stream/reconnect?session_id=${sessionId}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Accept': 'text/event-stream',
        },
        signal,
      });

      if (!response.ok) {
        if (response.status === 401) {
          clearAuthToken();
          window.location.href = '/login';
          return;
        }
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const contentType = response.headers.get('content-type') || '';
      if (!contentType.includes('text/event-stream')) {
        onEnd?.(sessionId);
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let hasError = false;

      while (true) {
        if (signal?.aborted) break;
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === 'error') {
                hasError = true;
                onError?.(new Error(data.error));
              }
              onChunk?.(data);
            } catch (e) {
              console.warn('Failed to parse SSE data:', e, line);
            }
          }
        }
      }

      if (buffer.trim()) {
        const remainingLines = buffer.split('\n');
        for (const line of remainingLines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === 'error') { hasError = true; onError?.(new Error(data.error)); }
              onChunk?.(data);
            } catch (e) {
              console.warn('Failed to parse SSE data:', e, line);
            }
          }
        }
      }

      if (!hasError) {
        onEnd?.(sessionId);
      }
    } catch (error) {
      if (error.name === 'AbortError') {
        onEnd?.(sessionId);
        return;
      }
      onError?.(error);
    }
  },

  fetchModels: async () => {
    const response = await apiClient.get('/models');
    return response.data;
  },

  abortQuery: async (conversationId) => {
    const response = await apiClient.post('/query/abort', {
      question: 'abort',
      conversation_id: conversationId,
    });
    return response.data;
  },

  getImage: async (imageId) => {
    console.log(`[API] 开始获取图片 ${imageId}`);
    try {
      const response = await apiClient.get(`/images/${imageId}`, {
        responseType: 'json',
      });
      console.log(`[API] 图片 ${imageId} 获取成功`, {
        id: response.data?.data?.id,
        filename: response.data?.data?.filename,
        size: response.data?.data?.size,
        base64Length: response.data?.data?.base64?.length,
      });
      return response.data;
    } catch (error) {
      console.error(`[API] 图片 ${imageId} 获取失败:`, error.message, error.code);
      throw error;
    }
  },
};

export const adminService = {
  listUsers: async () => {
    const response = await apiClient.get('/admin/users');
    return response.data;
  },
  createUser: async (data) => {
    const response = await apiClient.post('/admin/users', data);
    return response.data;
  },
  updateUser: async (userId, data) => {
    const response = await apiClient.put(`/admin/users/${userId}`, data);
    return response.data;
  },
  deleteUser: async (userId) => {
    const response = await apiClient.delete(`/admin/users/${userId}`);
    return response.data;
  },
  getAllModels: async () => {
    const response = await apiClient.get('/admin/models');
    return response.data;
  },
  getUserModels: async (userId) => {
    const response = await apiClient.get(`/admin/users/${userId}/models`);
    return response.data;
  },
  setUserModels: async (userId, models) => {
    const response = await apiClient.put(`/admin/users/${userId}/models`, { models });
    return response.data;
  },
  // OpenCode 服务商/模型管理
  getOpencodeProviders: async () => {
    const response = await apiClient.get('/admin/opencode/providers');
    return response.data;
  },
  getOpencodeProviderAuth: async () => {
    const response = await apiClient.get('/admin/opencode/provider-auth');
    return response.data;
  },
  setOpencodeProviderAuth: async (providerId, data) => {
    const response = await apiClient.put(`/admin/opencode/auth/${providerId}`, data);
    return response.data;
  },
  getOpencodeConfig: async () => {
    const response = await apiClient.get('/admin/opencode/config');
    return response.data;
  },
  updateOpencodeConfig: async (data) => {
    const response = await apiClient.patch('/admin/opencode/config', data);
    return response.data;
  },
  getOpencodeConfigProviders: async () => {
    const response = await apiClient.get('/admin/opencode/config/providers');
    return response.data;
  },
  getSystemConfig: async () => {
    const response = await apiClient.get('/admin/system-config');
    return response.data;
  },
  setSystemConfig: async (key, value) => {
    const response = await apiClient.put('/admin/system-config', { key, value });
    return response.data;
  },
  getOpencodeStatus: async () => {
    const response = await apiClient.get('/admin/opencode/status');
    return response.data;
  },
  restartOpencode: async () => {
    const response = await apiClient.post('/admin/opencode/restart');
    return response.data;
  },
  startOpencode: async () => {
    const response = await apiClient.post('/admin/opencode/start');
    return response.data;
  },
  initUserWorkspace: async (userId) => {
    const response = await apiClient.post(`/admin/users/${userId}/init-workspace`);
    return response.data;
  },
  getUsageStats: async (days = 30) => {
    const response = await apiClient.get('/admin/usage/stats', { params: { days } });
    return response.data;
  },
  getTools: async () => {
    const response = await apiClient.get('/admin/tools');
    return response.data;
  },
  updateTool: async (toolName, action) => {
    const response = await apiClient.put(`/admin/tools/${toolName}`, null, { params: { action } });
    return response.data;
  },
  getUserTools: async (userId) => {
    const response = await apiClient.get(`/admin/users/${userId}/tools`);
    return response.data;
  },
  setUserTool: async (userId, toolName, action) => {
    const response = await apiClient.put(`/admin/users/${userId}/tools/${toolName}`, null, { params: { action } });
    return response.data;
  },
  removeUserTool: async (userId, toolName) => {
    const response = await apiClient.delete(`/admin/users/${userId}/tools/${toolName}`);
    return response.data;
  },
  syncToolsConfig: async () => {
    const response = await apiClient.post('/admin/tools/sync');
    return response.data;
  },
  getSkills: async () => {
    const response = await apiClient.get('/admin/skills');
    return response.data;
  },
  updateSkill: async (skillName, enabled) => {
    const response = await apiClient.put(`/admin/skills/${skillName}`, null, { params: { enabled } });
    return response.data;
  },
  getUserSkills: async (userId) => {
    const response = await apiClient.get(`/admin/users/${userId}/skills`);
    return response.data;
  },
  setUserSkill: async (userId, skillName, action) => {
    const response = await apiClient.put(`/admin/users/${userId}/skills/${skillName}`, null, { params: { action } });
    return response.data;
  },
  removeUserSkill: async (userId, skillName) => {
    const response = await apiClient.delete(`/admin/users/${userId}/skills/${skillName}`);
    return response.data;
  },
  syncSkills: async () => {
    const response = await apiClient.post('/admin/skills/sync');
    return response.data;
  },
  getFailoverChains: async () => {
    const response = await apiClient.get('/admin/failover-chains');
    return response.data;
  },
  setFailoverChain: async (primaryModelId, primaryProviderId, fallbacks) => {
    const response = await apiClient.put('/admin/failover-chains', {
      primary_model_id: primaryModelId,
      primary_provider_id: primaryProviderId,
      fallbacks,
    });
    return response.data;
  },
  deleteFailoverChain: async (chainId) => {
    const response = await apiClient.delete(`/admin/failover-chains/${chainId}`);
    return response.data;
  },
};

export const fileService = {
  listFiles: async (path = '') => {
    const response = await apiClient.get('/files', { params: { path } });
    return response.data;
  },
  getFileContent: async (path) => {
    const response = await apiClient.get('/files/content', { params: { path } });
    return response.data;
  },
  getDownloadUrl: (path) => {
    const token = getAuthToken();
    return `/api/files/download?path=${encodeURIComponent(path)}&token=${token}`;
  },
  searchFiles: async (query, limit = 20) => {
    const response = await apiClient.get('/files/search', { params: { query, limit } });
    return response.data;
  },
};

export const diffService = {
  getSessionDiff: async (sessionId) => {
    const response = await apiClient.get(`/sessions/${sessionId}/diff`);
    return response.data;
  },
};

export const skillService = {
  getSkills: async () => {
    const response = await apiClient.get('/skills');
    return response.data;
  },
  updateSkill: async (skillName, enabled) => {
    const response = await apiClient.put(`/skills/${skillName}`, null, { params: { enabled } });
    return response.data;
  },
  syncSkills: async () => {
    const response = await apiClient.post('/skills/sync');
    return response.data;
  },
};

export const notificationService = {
  getUnread: async () => {
    const response = await apiClient.get('/notifications', { params: { unread: 'true' } });
    return response.data;
  },
  getAll: async () => {
    const response = await apiClient.get('/notifications');
    return response.data;
  },
  markRead: async (id) => {
    const response = await apiClient.post(`/notifications/${id}/read`);
    return response.data;
  },
};

export const taskService = {
  getTasks: async () => {
    const response = await apiClient.get('/tasks');
    return response.data;
  },
  updateTask: async (taskId, data) => {
    const response = await apiClient.put(`/tasks/${taskId}`, data);
    return response.data;
  },
  toggleTask: async (taskId) => {
    const response = await apiClient.post(`/tasks/${taskId}/toggle`);
    return response.data;
  },
  runTask: async (taskId) => {
    const response = await apiClient.post(`/tasks/${taskId}/run`);
    return response.data;
  },
};

export const memoryService = {
  getMemory: async () => {
    const response = await apiClient.get('/memory');
    return response.data;
  },
};

export const snapshotService = {
  list: async (page = 1, pageSize = 20, sessionId = null) => {
    const params = { page, page_size: pageSize };
    if (sessionId) params.session_id = sessionId;
    const response = await apiClient.get('/snapshots', { params });
    return response.data;
  },
  getDetail: async (commitHash) => {
    const response = await apiClient.get(`/snapshots/${commitHash}`);
    return response.data;
  },
  getFile: async (commitHash, path) => {
    const response = await apiClient.get(`/snapshots/${commitHash}/file`, { params: { path } });
    return response.data;
  },
  restoreAll: async (commitHash) => {
    const response = await apiClient.post(`/snapshots/${commitHash}/restore`);
    return response.data;
  },
  restoreFile: async (commitHash, path) => {
    const response = await apiClient.post(`/snapshots/${commitHash}/restore-file`, { path });
    return response.data;
  },
  getDiff: async (commitHash) => {
    const response = await apiClient.get(`/snapshots/${commitHash}/diff`);
    return response.data;
  },
};

export default apiClient;
