import React, { useState, useRef, useEffect, useCallback } from 'react';
import { 
  Card, 
  Input, 
  Button, 
  Spin, 
  Alert as AntAlert, 
  Typography, 
  Space, 
  Tag, 
  Avatar, 
  Collapse,
  message as AntMessage,
  Form,
  Radio,
  Upload,
  Image,
  Modal,
  Tooltip
} from 'antd';
import { 
  SendOutlined, 
  UserOutlined, 
  DeleteOutlined, 
  CheckCircleOutlined, 
  LoadingOutlined,
  QuestionCircleOutlined,
  BarChartOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  LinkOutlined,
  CloseOutlined,
  LogoutOutlined,
  PlusOutlined,
  HistoryOutlined,
  SettingOutlined,
  FolderOpenOutlined,
  ThunderboltOutlined,
  ClockCircleOutlined,
  BookOutlined,
  RollbackOutlined,
  RobotOutlined,
  TeamOutlined
} from '@ant-design/icons';
import { queryDataService, authService, clearAuthToken, diffService } from '../services/api';
import { useNavigate } from 'react-router-dom';
import MarkdownRenderer from '../components/MarkdownRenderer';
import ChatInput from '../components/ChatInput';
import HistoryDrawer from '../components/HistoryDrawer';
import ToolCall from '../components/ToolCall';
import FileManager from '../components/FileManager';
import UserSkillManager from '../components/UserSkillManager';
import TaskManager from '../components/TaskManager';
import NotificationBell from '../components/NotificationBell';
import MemoryViewer from '../components/MemoryViewer';
import KnowledgeManager from '../components/KnowledgeManager';
import GitTimeMachine from '../components/GitTimeMachine';
import SmartEntityManager from '../components/SmartEntityManager';
import SmartEntityTaskCenter from '../components/SmartEntityTaskCenter';
import TodoFloatPanel from '../components/TodoFloatPanel';
import { usePretextMeasure } from '../hooks/usePretextMeasure';
import { PretextMessageItem, PretextBubbleWidth, useDynamicBubbleWidth } from '../components/PretextIntegration';
import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';
import QuestionForm from '../components/QuestionForm';
import QuestionFormInline from '../components/QuestionFormInline';
import UserMessage from '../components/UserMessage';
import AssistantMessage from '../components/AssistantMessage';

const { TextArea } = Input;
const { Title, Text } = Typography;

// API 基础 URL
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api';

const SmartQueryPage = () => {
  const navigate = useNavigate();
  const [isAdmin, setIsAdmin] = useState(false);
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState([]);
  const [conversationId, setConversationId] = useState('');
  const [error, setError] = useState(null);
  const [streamingMessageId, setStreamingMessageId] = useState(null);
  const [idleState, setIdleState] = useState(false);
  const [questionAnswers, setQuestionAnswers] = useState({});
  const [selectedImages, setSelectedImages] = useState([]);
  const [messageTimings, setMessageTimings] = useState({});
  const currentAssistantMessageIdRef = useRef(null);
  const messagesEndRef = useRef(null);
  const abortControllerRef = useRef(null);
  const pendingQuestionIdRef = useRef(null);
  const fileInputRef = useRef(null);
  const queryStartTimeRef = useRef(null);
  const sendingRef = useRef(false)
  const messagesContainerRef = useRef(null);
  const [containerWidth, setContainerWidth] = useState(800);
  const [isMobile, setIsMobile] = useState(false);
  
  const { measureText, clearMeasurementCache } = usePretextMeasure(containerWidth);
  
  // 历史会话相关状态
  const [historySessions, setHistorySessions] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [historyDrawerVisible, setHistoryDrawerVisible] = useState(false);
  const [fileManagerVisible, setFileManagerVisible] = useState(false);
  const [skillManagerVisible, setSkillManagerVisible] = useState(false);
  const [taskManagerVisible, setTaskManagerVisible] = useState(false);
  const [memoryViewerVisible, setMemoryViewerVisible] = useState(false);
  const [knowledgeManagerVisible, setKnowledgeManagerVisible] = useState(false);
  const [smartEntityManagerVisible, setSmartEntityManagerVisible] = useState(false);
  const [smartEntityTaskCenterVisible, setSmartEntityTaskCenterVisible] = useState(false);
  const [timeMachineVisible, setTimeMachineVisible] = useState(false);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyHasMore, setHistoryHasMore] = useState(true);
  const [loadingMoreHistory, setLoadingMoreHistory] = useState(false);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [archiveModalVisible, setArchiveModalVisible] = useState(false);
  const [sessionToArchive, setSessionToArchive] = useState(null);
  const [archiving, setArchiving] = useState(false);
  const [currentTodos, setCurrentTodos] = useState(null);
  const [todoPanelVisible, setTodoPanelVisible] = useState(false);

  useEffect(() => {
    authService.getMe()
      .then((result) => setIsAdmin(result.data?.is_admin || false))
      .catch(() => setIsAdmin(false));
  }, []);

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // 异步加载图片 base64 数据
  const loadImageBase64 = async (messages) => {
    console.log('[图片懒加载] 输入消息:', messages);
    
    // 收集所有需要加载的图片，使用 imageId 作为唯一标识
    const imagesToLoad = [];
    messages.forEach((msg, msgIndex) => {
      if (msg.imageMetas && Array.isArray(msg.imageMetas) && msg.imageMetas.length > 0) {
        msg.imageMetas.forEach((meta, imgIndex) => {
          imagesToLoad.push({ 
            msgIndex, 
            imgIndex, 
            meta, 
            messageId: msg.id,
            imageId: `${msg.id}-${imgIndex}` // 唯一标识
          });
        });
      }
    });
    
    if (imagesToLoad.length === 0) {
      console.log('[图片懒加载] 没有需要加载的图片');
      return;
    }
    
    console.log(`[图片懒加载] 准备加载 ${imagesToLoad.length} 张图片`, imagesToLoad);
    
    // 第一步：先将所有图片标记为加载中，使用 imageMetas 的顺序
    setMessages(prev => {
      console.log('[图片懒加载] 之前的 messages:', prev);
      const updated = prev.map(msg => {
        if (msg.imageMetas && msg.imageMetas.length > 0) {
          const newImages = msg.imageMetas.map((meta, idx) => ({
            id: meta.id,
            loading: true, // 标记为加载中
            filename: meta.filename,
            imageIndex: idx, // 保存索引用于后续更新
          }));
          console.log(`[图片懒加载] 消息 ${msg.id} 初始化图片:`, newImages);
          return { ...msg, images: newImages };
        }
        return msg;
      });
      console.log('[图片懒加载] 初始化后的 messages:', updated);
      return updated;
    });
    
    // 并发加载图片，限制并发数为 3
    const CONCURRENCY_LIMIT = 3;
    for (let i = 0; i < imagesToLoad.length; i += CONCURRENCY_LIMIT) {
      const batch = imagesToLoad.slice(i, i + CONCURRENCY_LIMIT);
      const promises = batch.map(async ({ imgIndex, meta, messageId }) => {
        try {
          console.log(`[图片懒加载] 加载图片 ${meta.id} (${meta.filename})`);
          const result = await queryDataService.getImage(meta.id);
          console.log(`[图片懒加载] 图片 ${meta.id} 返回结果:`, result);
          if (result.success && result.data) {
            // 更新消息中的图片数据，使用 imgIndex 精确定位
            setMessages(prev => {
              console.log('[图片懒加载] 更新前 messages:', prev);
              const updated = prev.map((msg) => {
                if (msg.id === messageId && msg.images && msg.images.length > imgIndex) {
                  const newImages = [...msg.images];
                  newImages[imgIndex] = {
                    id: meta.id,
                    base64: result.data.base64,
                    name: result.data.filename,
                    type: result.data.mime_type,
                    loading: false, // 加载完成
                    imageIndex: imgIndex,
                  };
                  console.log(`[图片懒加载] 消息 ${msg.id} 图片 ${imgIndex} 更新为:`, newImages[imgIndex]);
                  return { ...msg, images: newImages };
                }
                return msg;
              });
              console.log('[图片懒加载] 更新后 messages:', updated);
              return updated;
            });
          }
        } catch (err) {
          console.error(`[图片懒加载] 加载图片 ${meta.id} 失败:`, err);
          // 加载失败也标记为不加载了
          setMessages(prev => prev.map((msg) => {
            if (msg.id === messageId && msg.images && msg.images.length > imgIndex) {
              const newImages = [...msg.images];
              newImages[imgIndex] = {
                ...newImages[imgIndex],
                loading: false,
                error: true,
              };
              return { ...msg, images: newImages };
            }
            return msg;
          }));
        }
      });
      
      await Promise.all(promises);
      console.log(`[图片懒加载] 批次 ${Math.floor(i / CONCURRENCY_LIMIT) + 1} 完成`);
    }
    
    console.log('[图片懒加载] 全部完成');
  };

  // 格式化耗时（毫秒转为时分秒）
  const formatDuration = (ms) => {
    if (ms < 1000) {
      return `${ms}ms`;
    }
    
    const totalSeconds = Math.floor(ms / 1000);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    
    if (hours > 0) {
      return `${hours}分${minutes}秒`;
    } else if (minutes > 0) {
      return `${minutes}分${seconds}秒`;
    } else {
      return `${seconds}秒`;
    }
  };

  const prevMessageCountRef = useRef(0);

  useEffect(() => {
    const count = messages.length;
    const newUserMsg = count > prevMessageCountRef.current && messages[messages.length - 1]?.type === 'user';
    prevMessageCountRef.current = count;

    if (loading || newUserMsg) {
      messagesEndRef.current?.scrollIntoView({ behavior: loading ? 'instant' : 'smooth' });
    }
  }, [messages, loading]);

  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setContainerWidth(entry.contentRect.width);
      }
    });

    resizeObserver.observe(container);
    return () => resizeObserver.disconnect();
  }, []);

  // 页面关闭时关闭 SSE 连接
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        console.log('[Cleanup] Aborted SSE connection');
      }
    };
  }, []);

  // 加载历史会话列表
  useEffect(() => {
    loadHistorySessions();
  }, []);

  const handleImageUpload = (files) => {
    const fileArray = Array.from(files);
    let processedCount = 0;
    const validImages = [];
    
    for (const file of fileArray) {
      // 检查数量限制
      if (selectedImages.length + validImages.length >= 5) {
        AntMessage.warning('最多只能上传 5 张图片');
        break;
      }
      
      // 检查是否为图片
      const isImage = file.type.startsWith('image/');
      if (!isImage) {
        AntMessage.error(`"${file.name}" 不是图片文件`);
        continue;
      }
      
      // 检查大小限制 (5MB)
      const isLt5M = file.size / 1024 / 1024 < 5;
      if (!isLt5M) {
        AntMessage.error(`"${file.name}" 超过 5MB`);
        continue;
      }
      
      // 转换为 base64
      const reader = new FileReader();
      reader.onload = (e) => {
        const result = e.target.result;
        const base64 = result.includes(',') ? result.split(',')[1] : result;
        
        validImages.push({
          file,
          base64,
          name: file.name,
          type: file.type,
        });
        
        processedCount++;
        // 当所有文件都处理完时更新状态
        if (processedCount === fileArray.length && validImages.length > 0) {
          setSelectedImages(prev => [...prev, ...validImages]);
        }
      };
      reader.onerror = () => {
        AntMessage.error(`"${file.name}" 读取失败`);
        processedCount++;
      };
      reader.readAsDataURL(file);
    }
    
    // 清空 input，允许重复选择同一文件
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleRemoveImage = (index) => {
    setSelectedImages(prev => prev.filter((_, i) => i !== index));
  };

  const handleHistoryScroll = (e) => {
    const { scrollTop, scrollHeight, clientHeight } = e.target;
    // 距离底部 50px 时加载更多
    if (scrollHeight - scrollTop - clientHeight < 50 && !loadingMoreHistory && historyHasMore) {
      loadHistorySessions(false, true);
    }
  };

  const loadHistorySessions = async (refresh = false, append = false) => {
    const pageToLoad = append ? historyPage + 1 : 1;
    
    if (refresh || !append) {
      setLoadingHistory(true);
    } else {
      setLoadingMoreHistory(true);
    }
    
    try {
      const result = await queryDataService.getSessions(pageToLoad, 10);
      if (result.success && result.data) {
        if (append) {
          // 追加数据
          setHistorySessions(prev => [...prev, ...result.data]);
        } else {
          // 刷新数据
          setHistorySessions(result.data);
        }
        
        // 更新分页状态
        setHistoryPage(pageToLoad);
        setHistoryHasMore(result.pagination?.has_more || false);
        setHistoryTotal(result.pagination?.total || 0);
        
        return true;
      }
      return false;
    } catch (err) {
      console.error('Failed to load history:', err);
      return false;
    } finally {
      if (refresh || !append) {
        setLoadingHistory(false);
      } else {
        setLoadingMoreHistory(false);
      }
    }
  };

  const loadSessionMessages = async (sessionId) => {
    // 如果点击的历史会话与当前会话相同，直接返回，避免重复获取
    if (sessionId === conversationId) {
      console.log('[loadSessionMessages] Same session, skip loading: ' + sessionId);
      setHistoryDrawerVisible(false);
      return;
    }

    // 关闭当前已存在的 SSE 连接，防止历史对话收到切换前未完成的消息
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      console.log('[loadSessionMessages] Aborted previous SSE connection');
    }
    
    // 重置加载状态和空闲状态
    setLoading(false);
    setIdleState(false);
    setStreamingMessageId(null);
    setCurrentTodos(null);
    setTodoPanelVisible(false);

    try {
      const result = await queryDataService.getMessages(sessionId);
      if (result.success && result.data) {
        const formattedMessages = result.data.map((msg, index) => {
          const formattedMsg = {
            id: `hist_${index}`,
            type: msg.role === 'user' ? 'user' : 'assistant',
            content: msg.content,
            timestamp: new Date(msg.created_at),
            agent: msg.agent,
            streaming: false,
          };

          if (msg.role === 'user' && msg.model) {
            try {
              formattedMsg.model = typeof msg.model === 'string' ? JSON.parse(msg.model) : msg.model;
            } catch {
              formattedMsg.model = msg.model;
            }
          }
          
          // 保存图片元数据，不加载 base64
          if (msg.images && msg.images.length > 0) {
            formattedMsg.imageMetas = msg.images;
            formattedMsg.images = []; // 初始化为空数组
          }
          
          // 从 metadata 中读取 reasoning
          if (msg.metadata && msg.metadata.reasoning) {
            formattedMsg.reasoning = msg.metadata.reasoning;
          }
          
          // 处理 metadata 中的工具信息
          if (msg.metadata && msg.metadata.tools) {
            formattedMsg.tools = {};
            Object.entries(msg.metadata.tools).forEach(([key, tool]) => {
              formattedMsg.tools[key] = {
                tool: tool.tool,
                state: tool.state,
                input: tool.input,
                output: tool.output,
                questionId: tool.input?.questions ? (tool.call_id || key) : null,
                questions: tool.input?.questions || [],
              };
            });
          }
          
          return formattedMsg;
        });
        setMessages(formattedMessages);
        setConversationId(sessionId);
        setHistoryDrawerVisible(false);
        setIdleState(true);
        AntMessage.success('已加载历史对话');

        setTimeout(() => {
          messagesEndRef.current?.scrollIntoView({ behavior: 'instant' });
        }, 100);

        // 从历史记录中提取每个 agent 最后使用的 model
        const lastModelByAgent = {};
        for (const msg of result.data) {
          if (msg.role === 'user' && msg.model && msg.agent) {
            try {
              const modelObj = typeof msg.model === 'string' ? JSON.parse(msg.model) : msg.model;
              if (modelObj && modelObj.modelID && modelObj.providerID) {
                lastModelByAgent[msg.agent] = modelObj;
              }
            } catch {}
          }
        }
        if (Object.keys(lastModelByAgent).length === 1) {
          const m = lastModelByAgent[Object.keys(lastModelByAgent)[0]];
          lastModelByAgent.build = m;
          lastModelByAgent.plan = m;
        }
        if (Object.keys(lastModelByAgent).length > 0) {
          lastModelRef.current = {
            build: lastModelByAgent.build || lastModelRef.current.build,
            plan: lastModelByAgent.plan || lastModelRef.current.plan,
          };
          setCurrentModel(lastModelRef.current[currentAgent] || null);
        }
        
        // 为历史消息设置模拟耗时数据（每个助手消息随机 1-5 秒）
        const timings = {};
        formattedMessages.forEach((msg, index) => {
          if (msg.type === 'assistant') {
            // 使用时间戳差值计算实际耗时，如果没有下一条消息则使用默认值
            const nextMsg = formattedMessages[index + 1];
            if (nextMsg) {
              timings[msg.id] = nextMsg.timestamp.getTime() - msg.timestamp.getTime();
            } else {
              // 最后一条消息，使用默认值 3 秒
              timings[msg.id] = 3000;
            }
          }
        });
        setMessageTimings(timings);
        
        // 第二步：异步加载图片 base64（延迟加载）
        loadImageBase64(formattedMessages);

        if (result.is_processing) {
          setLoading(true);
          const lastAssistantMsg = [...formattedMessages].reverse().find(m => m.type === 'assistant');
          const reconnectMsgId = Date.now().toString();
          currentAssistantMessageIdRef.current = reconnectMsgId;

          if (lastAssistantMsg) {
            setMessages((prev) => [
              ...prev,
              {
                id: reconnectMsgId,
                type: 'assistant',
                content: '',
                reasoning: '',
                timestamp: new Date(),
                streaming: true,
              },
            ]);
          }

          if (!abortControllerRef.current) {
            abortControllerRef.current = new AbortController();
          }

          queryDataService.reconnectStream(
            sessionId,
            (data) => {
              if (data.type === 'session' || data.type === 'session_reconnected') return;

              if (data.type === 'message_start') {
                const newMsgId = Date.now().toString();
                currentAssistantMessageIdRef.current = newMsgId;
                setMessages((prev) => [
                  ...prev,
                  { id: newMsgId, type: 'assistant', content: '', reasoning: '', timestamp: new Date(), streaming: true },
                ]);
              }

              if (data.type === 'message_complete') {
                const msgId = currentAssistantMessageIdRef.current;
                setMessages((prev) => {
                  const idx = prev.findIndex(m => m.id === msgId);
                  if (idx === -1) return prev;
                  const next = [...prev];
                  next[idx] = { ...next[idx], streaming: false };
                  return next;
                });
              }

              if (data.type === 'reasoning') {
                const msgId = currentAssistantMessageIdRef.current;
                setMessages((prev) => {
                  const idx = prev.findIndex(m => m.id === msgId);
                  if (idx === -1) return prev;
                  const next = [...prev];
                  next[idx] = { ...next[idx], reasoning: (next[idx].reasoning || '') + (data.content || '') };
                  return next;
                });
              }

              if (data.type === 'text') {
                const msgId = currentAssistantMessageIdRef.current;
                setMessages((prev) => {
                  const idx = prev.findIndex(m => m.id === msgId);
                  if (idx === -1) return prev;
                  const next = [...prev];
                  next[idx] = { ...next[idx], content: (next[idx].content || '') + (data.content || '') };
                  return next;
                });
              }

              if (data.type === 'tool') {
                const msgId = currentAssistantMessageIdRef.current;
                const toolKey = `${msgId}_${data.call_id || data.tool}`;

                if (data.tool === 'todowrite' && data.input && data.input.todos) {
                  setCurrentTodos(data.input.todos);
                  setTodoPanelVisible((prev) => {
                    if (!prev && data.input.todos && data.input.todos.length > 0) {
                      return true;
                    }
                    return prev;
                  });
                }

                setMessages((prev) => {
                  const idx = prev.findIndex(m => m.id === msgId);
                  if (idx === -1) return prev;
                  const next = [...prev];
                  next[idx] = { ...next[idx], tools: { ...(next[idx].tools || {}), [toolKey]: { tool: data.tool, state: data.state, input: data.input, output: data.output, questionId: data.call_id || null } } };
                  return next;
                });
              }

              if (data.type === 'session_idle') {
                setLoading(false);
                setIdleState(true);
              }
            },
            () => {
              setLoading(false);
              setIdleState(true);
            },
            () => {
              setLoading(false);
            },
            abortControllerRef.current.signal
          );
        }
      }
    } catch (err) {
      console.error('Failed to load session messages:', err);
      AntMessage.error('加载历史对话失败');
    }
  };

  const handleNewConversation = () => {
    if (conversationId) {
      setMessages([]);
      setConversationId('');
      setError(null);
      setCurrentTodos(null);
      setTodoPanelVisible(false);
      AntMessage.success('已新建对话');
    }
  };

  const [exportModalVisible, setExportModalVisible] = useState(false);
  const [currentAgent, setCurrentAgent] = useState('build');
  const [currentModel, setCurrentModel] = useState(null);
  const lastModelRef = useRef({ build: null, plan: null });

  const handleAgentChange = (agent) => {
    lastModelRef.current[currentAgent] = currentModel;
    setCurrentAgent(agent);
    setCurrentModel(lastModelRef.current[agent]);
  };

  const handleExportClick = () => {
    if (messages.length === 0) {
      AntMessage.warning('没有可导出的内容');
      return;
    }
    setExportModalVisible(true);
  };

  const handleExportConfirm = (mode) => {
    setExportModalVisible(false);
    handleExportToPDF(mode);
  };

  const handleExportToPDF = async (mode = 'full') => {
    if (messages.length === 0) {
      AntMessage.warning('没有可导出的内容');
      return;
    }

    const loadingKey = 'export';
    AntMessage.loading({ content: '正在生成 PDF 文档...', key: loadingKey, duration: 0 });

    try {
      // 创建临时容器来渲染对话内容
      const tempContainer = document.createElement('div');
      tempContainer.style.cssText = `
        position: absolute;
        left: -9999px;
        top: 0;
        width: 794px; /* A4 纸宽度 @ 96dpi */
        background: #f5f7fa;
        padding: 30px 40px;
        font-family: Arial, "Microsoft YaHei", sans-serif;
      `;

      // 标题
      const titleHtml = `
        <div style="text-align: center; margin-bottom: 30px; page-break-after: avoid;">
          <h1 style="color: #1890ff; font-size: 24px; margin: 0 0 10px 0; page-break-after: avoid;">对话记录</h1>
          <div style="display: flex; justify-content: space-between; background: #f9fafb; padding: 12px; border-radius: 8px; border: 1px solid #e5e7eb; margin-top: 15px; page-break-inside: avoid;">
            <span style="color: #6b7280; font-size: 11px;">
              <strong>会话 ID:</strong> ${conversationId || '新建对话'}
            </span>
            <span style="color: #6b7280; font-size: 11px;">
              <strong>导出时间:</strong> ${new Date().toLocaleString('zh-CN')}
            </span>
          </div>
        </div>
      `;

      // 消息列表
      let messagesHtml = '';
      
      for (const message of messages) {
        // 精简版：只显示用户问题和助手回复，跳过工具调用消息
        if (mode === 'simple' && message.type !== 'user' && (!message.content || message.content.trim() === '')) {
          continue;
        }

        // 精简版：跳过纯工具调用的消息
        if (mode === 'simple' && message.type === 'assistant' && message.tools && Object.keys(message.tools).length > 0 && !message.content) {
          continue;
        }

        const isUser = message.type === 'user';
        const timeStr = message.timestamp.toLocaleString('zh-CN', { 
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit'
        });

        const avatar = isUser ? '👤' : '🤖';
        const bubbleBg = isUser ? '#1890ff' : '#ffffff';
        const bubbleColor = isUser ? '#ffffff' : '#1f2937';
        const bubbleBorder = isUser ? 'none' : '1px solid #e5e7eb';
        const align = isUser ? 'flex-end' : 'flex-start';

        // 过滤内容
        const content = filterContent(message.content, message.reasoning);
        
        // 简单 markdown 转 HTML
        const contentHtml = simpleMarkdownToHtml(content || '');
        
        // 精简版：不显示分析过程和工具调用
        const reasoningHtml = (mode === 'full' && message.reasoning) 
          ? `<div style="margin-top: 12px; padding: 10px; background: #eff6ff; border-left: 3px solid #1890ff; border-radius: 4px;">
              <div style="font-size: 11px; color: #1890ff; font-weight: 600; margin-bottom: 4px;">💡 分析过程</div>
              <div style="font-size: 12px; color: #374151; white-space: pre-wrap;">${message.reasoning}</div>
             </div>`
          : '';

        // 图片 HTML（完整版才显示）
        const imagesHtml = (mode === 'full' && message.images && message.images.length > 0)
          ? `<div style="margin-top: 12px; display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px;">
              ${message.images.map((img, idx) => {
                const imgSrc = img.base64 && img.type 
                  ? `data:${img.type};base64,${img.base64}`
                  : '';
                return `<div style="border-radius: 8px; overflow: hidden; border: 2px solid #e5e7eb;">
                  ${imgSrc ? `<img src="${imgSrc}" alt="${img.name || 'image'}" style="width: 100%; height: auto; display: block;" />` : '<div style="padding: 40px; text-align: center; color: #9ca3af;">加载中...</div>'}
                </div>`;
              }).join('')}
             </div>`
          : '';

        // 图片提示（精简版显示）
        const imageHint = (mode === 'simple' && message.images && message.images.length > 0)
          ? `<div style="font-size: 11px; color: #9ca3af; margin-top: 8px;">📷 ${message.images.length} 张图片</div>`
          : '';

        // 工具调用（仅完整版显示）
        const toolsHtml = (mode === 'full' && message.tools && Object.keys(message.tools).length > 0)
          ? `<div style="margin-top: 12px; padding: 10px; background: #f9fafb; border-radius: 4px;">
              <div style="font-size: 11px; color: #722ed1; font-weight: 600; margin-bottom: 6px;">🔧 工具调用</div>
              ${Object.entries(message.tools).map(([key, tool]) => {
                const stateColor = tool.state === 'completed' ? '#059669' : 
                                   tool.state === 'error' ? '#dc2626' : '#2563eb';
                const stateIcon = tool.state === 'completed' ? '✅' : 
                                  tool.state === 'error' ? '❌' : '⏳';
                return `<div style="font-size: 10px; color: #374151; margin-bottom: 4px; padding-left: 12px;">
                  ${stateIcon} ${tool.tool} <span style="color: ${stateColor};">(${tool.state || 'pending'})</span>
                </div>`;
              }).join('')}
             </div>`
          : '';

        messagesHtml += `
          <div style="margin-bottom: 24px; page-break-inside: avoid; break-inside: avoid;">
            <div style="font-size: 10px; color: #9ca3af; margin-bottom: 6px; page-break-after: avoid;">${timeStr}</div>
            <div style="display: flex; align-items: flex-start; gap: 8px; justify-content: ${align};">
              <div style="font-size: 24px; min-width: 32px; text-align: center; page-break-inside: avoid;">${avatar}</div>
              <div style="max-width: 70%; background: ${bubbleBg}; color: ${bubbleColor}; 
                  padding: 10px 14px; border-radius: 12px; 
                  border-top-${isUser ? 'right' : 'left'}-radius: 4px;
                  box-shadow: 0 1px 4px rgba(0,0,0,0.06); ${bubbleBorder};
                  page-break-inside: avoid; break-inside: avoid;">
                <div style="font-size: 10px; font-weight: 600; margin-bottom: 4px; opacity: 0.9; page-break-after: avoid;">
                  ${isUser ? '用户' : '助手'}
                </div>
                <div style="font-size: 12px; line-height: 1.5;">
                  ${reasoningHtml}
                  ${contentHtml}
                </div>
                ${imagesHtml}
                ${imageHint}
                ${toolsHtml}
              </div>
            </div>
          </div>
        `;
      }

      tempContainer.innerHTML = titleHtml + messagesHtml;
      document.body.appendChild(tempContainer);

      // 等待渲染
      await new Promise(resolve => setTimeout(resolve, 500));

      // 转换为 canvas（提高质量）
      const canvas = await html2canvas(tempContainer, {
        scale: 3,
        useCORS: true,
        logging: false,
        backgroundColor: '#f5f7fa',
        windowWidth: 794,
        imageTimeout: 15000,
        removeContainer: false,
        allowTaint: false,
        ignoreElements: (element) => {
          // 忽略不需要渲染的元素
          return false;
        },
        // 确保完整渲染，避免截断
        onclone: (clonedDoc) => {
          // 移除所有可能导致分页截断的样式
          const clonedContainer = clonedDoc.querySelector('div[style*="position: absolute"]');
          if (clonedContainer) {
            clonedContainer.style.pageBreakAfter = 'auto';
          }
        }
      });

      // 移除临时容器
      document.body.removeChild(tempContainer);

      // 创建 PDF - 使用 JPEG 高质量压缩
      const imgData = canvas.toDataURL('image/jpeg', 0.95); // 提高到 0.95 质量
      const pdf = new jsPDF({
        orientation: 'portrait',
        unit: 'mm',
        format: 'a4',
        compress: true
      });

      const pdfWidth = 210;
      const pdfHeight = 297;
      const imgWidth = pdfWidth;
      const imgHeight = (canvas.height * imgWidth) / canvas.width;

      let heightLeft = imgHeight;
      let position = 0;
      let page = 0;

      // 第一页
      pdf.addImage(imgData, 'JPEG', 0, position, imgWidth, imgHeight, undefined, 'FAST');
      heightLeft -= pdfHeight;

      // 多页支持 - 优化分页位置，避免截断文字
      while (heightLeft >= 0) {
        position = heightLeft - imgHeight;
        
        // 如果还有内容，添加新页面
        if (heightLeft > 0) {
          pdf.addPage();
          page++;
          pdf.addImage(imgData, 'JPEG', 0, position, imgWidth, imgHeight, undefined, 'FAST');
          heightLeft -= pdfHeight;
        } else {
          break;
        }
      }

      // 保存文件
      const modeSuffix = mode === 'full' ? '完整版' : '精简版';
      const fileName = `对话记录_${conversationId || '新建'}_${modeSuffix}_${Date.now()}.pdf`;
      pdf.save(fileName);

      AntMessage.success({ content: 'PDF 导出成功!', key: loadingKey, duration: 3 });
    } catch (error) {
      console.error('导出失败:', error);
      AntMessage.error({ 
        content: `导出失败：${error.message}`, 
        key: loadingKey, 
        duration: 5 
      });
    }
  };

  // 简单 markdown 转 HTML 函数（用于 PDF 导出）
  const simpleMarkdownToHtml = (markdown) => {
    if (!markdown) return '';
    
    let html = markdown;
    
    // 处理表格（必须在处理 | 之前先处理表格）
    const tableRegex = /(\|.+\|\n)(\|[\s\-:|]+\|\n)((?:\|.+\|\n?)+)/g;
    html = html.replace(tableRegex, (match, headerRow, separatorRow, bodyRows) => {
      // 解析表头
      const headers = headerRow.split('|').filter(cell => cell.trim()).map(h => h.trim());
      // 解析对齐方式
      const separators = separatorRow.split('|').filter(s => s.trim());
      const aligns = separators.map(s => {
        const trim = s.trim();
        if (trim.startsWith(':') && trim.endsWith(':')) return 'center';
        if (trim.endsWith(':')) return 'right';
        return 'left';
      });
      // 解析表体
      const rows = bodyRows.trim().split('\n').filter(row => row.trim()).map(row => 
        row.split('|').filter(cell => cell.trim()).map(c => c.trim())
      );
      
      // 生成表格 HTML
      let tableHtml = '<table style="width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 11px;">';
      // 表头
      tableHtml += '<thead><tr style="background: #f3f4f6;">';
      headers.forEach((h, i) => {
        const align = aligns[i] || 'left';
        tableHtml += `<th style="border: 1px solid #d1d5db; padding: 8px 10px; text-align: ${align}; font-weight: 600; color: #1f2937;">${h}</th>`;
      });
      tableHtml += '</tr></thead>';
      // 表体
      tableHtml += '<tbody>';
      rows.forEach((row, idx) => {
        const bg = idx % 2 === 0 ? '#ffffff' : '#f9fafb';
        tableHtml += `<tr style="background: ${bg};">`;
        row.forEach((cell, i) => {
          const align = aligns[i] || 'left';
          tableHtml += `<td style="border: 1px solid #e5e7eb; padding: 8px 10px; text-align: ${align}; color: #374151;">${cell}</td>`;
        });
        tableHtml += '</tr>';
      });
      tableHtml += '</tbody></table>';
      return tableHtml;
    });
    
    // 处理标题
    html = html.replace(/^### (.*$)/gim, '<div style="font-size: 13px; font-weight: 600; color: #374151; margin: 10px 0 6px;">$1</div>');
    html = html.replace(/^## (.*$)/gim, '<div style="font-size: 15px; font-weight: 600; color: #1f2937; margin: 12px 0 8px;">$1</div>');
    html = html.replace(/^# (.*$)/gim, '<div style="font-size: 17px; font-weight: 600; color: #1f2937; margin: 14px 0 10px;">$1</div>');
    
    // 处理粗体
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong style="font-weight: 600;">$1</strong>');
    
    // 处理斜体
    html = html.replace(/\*(.*?)\*/g, '<em style="font-style: italic;">$1</em>');
    
    // 处理行内代码
    html = html.replace(/`(.*?)`/g, '<code style="background: #f3f4f6; padding: 2px 6px; border-radius: 4px; font-size: 11px; color: #dc2626; font-family: monospace;">$1</code>');
    
    // 处理列表项
    html = html.replace(/^[\-\*] (.*$)/gim, '<div style="padding-left: 16px; position: relative; margin: 4px 0;">• $1</div>');
    
    // 处理编号列表
    html = html.replace(/^\d+\. (.*$)/gim, '<div style="padding-left: 16px; margin: 4px 0;">$1</div>');
    
    // 处理引用
    html = html.replace(/^> (.*$)/gim, '<div style="border-left: 3px solid #1890ff; padding-left: 12px; margin: 8px 0; color: #6b7280; font-style: italic;">$1</div>');
    
    // 处理链接
    html = html.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" style="color: #1890ff; text-decoration: underline;">$1</a>');
    
    // 处理换行
    html = html.replace(/\n/g, '<br/>');
    
    return html;
  };

  const handleArchiveClick = (sessionId) => {
    setSessionToArchive(sessionId);
    setArchiveModalVisible(true);
  };

  const handleArchiveConfirm = async () => {
    if (!sessionToArchive) return;
    
    setArchiving(true);
    try {
      await queryDataService.archiveSession(sessionToArchive);
      AntMessage.success('会话已归档');
      setArchiveModalVisible(false);
      setSessionToArchive(null);
      loadHistorySessions();
    } catch (err) {
      console.error('Failed to archive session:', err);
      AntMessage.error(`归档失败：${err.message}`);
    } finally {
      setArchiving(false);
    }
  };

  const handleArchiveCancel = () => {
    setArchiveModalVisible(false);
    setSessionToArchive(null);
  };

  const handleLogout = () => {
    clearAuthToken();
    window.location.href = '/login';
  };

  const sendMessage = async (text) => {
    if (!text || !text.trim()) return;
    setQuestion('');
    await handleSend(text);
  };

  const handleSend = async (overrideQuestion) => {
    console.log('[handleSend] called, sendingRef:', sendingRef.current, 'loading:', loading);
    if (sendingRef.current) {
      console.log('[handleSend] blocked by sendingRef guard');
      return;
    }
    const rawQ = overrideQuestion !== undefined ? overrideQuestion : question;
    // 确保 q 是字符串
    let q;
    if (typeof rawQ === 'string') {
      q = rawQ;
    } else if (typeof rawQ === 'object' && rawQ !== null) {
      console.error('question is object:', rawQ);
      q = String(rawQ || '');
    } else {
      q = String(rawQ || '');
    }
    
    if (!q.trim() && selectedImages.length === 0) return;

    sendingRef.current = true;

    // 检查模型余量
    if (currentModel && currentModel.monthlyLimit > 0 && (currentModel.currentUsage || 0) >= currentModel.monthlyLimit) {
      AntMessage.warning(`模型 ${currentModel.modelID || ''} 本月调用次数已达上限 (${currentModel.monthlyLimit}/${currentModel.monthlyLimit})，请更换模型或联系管理员`);
      sendingRef.current = false;
      return;
    }

    const turnId = `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;

    const userMessage = {
      id: Date.now().toString(),
      type: 'user',
      content: q,
      images: selectedImages.length > 0 ? [...selectedImages] : null,
      timestamp: new Date(),
      agent: currentAgent,
      model: currentModel,
      turnId,
    };

    lastModelRef.current[currentAgent] = currentModel;

    setMessages((prev) => [...prev, userMessage]);
    
    const currentImages = [...selectedImages];
    if (overrideQuestion === undefined) setQuestion('');
    setSelectedImages([]);
    setLoading(true);
    setError(null);
    setIdleState(false);
    setCurrentTodos(null);
    setTodoPanelVisible(false);

    queryStartTimeRef.current = Date.now();

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    const newAssistantMessageId = (Date.now() + 1).toString();
    currentAssistantMessageIdRef.current = newAssistantMessageId;
    setStreamingMessageId(newAssistantMessageId);

    setMessages((prev) => [
      ...prev,
      {
        id: newAssistantMessageId,
        type: 'assistant',
        content: '',
        reasoning: '',
        timestamp: new Date(),
        streaming: true,
        turnId,
      },
    ]);

    try {
      await queryDataService.queryDataStream(
        q || (currentImages.length > 0 ? '请分析这些图片' : ''),
        conversationId,
        (data) => {
          if (data.type === 'session' && data.conversation_id && !conversationId) {
            setConversationId(data.conversation_id);
          }
          if (data.type === 'session' && data.agent) {
            setCurrentAgent(data.agent);
          }
          
          if (data.type === 'message_start') {
            const newMessageId = (Date.now()).toString();
            currentAssistantMessageIdRef.current = newMessageId;
            setMessages((prev) => [
              ...prev,
              {
                id: newMessageId,
                type: 'assistant',
                content: '',
                reasoning: '',
                timestamp: new Date(),
                streaming: true,
              },
            ]);
          }
          
          if (data.type === 'message_complete') {
            const msgId = currentAssistantMessageIdRef.current;
            // 计算耗时
            const duration = queryStartTimeRef.current ? Date.now() - queryStartTimeRef.current : 0;
            setMessageTimings((prev) => ({ ...prev, [msgId]: duration }));
            
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === msgId
                  ? { ...msg, streaming: false }
                  : msg
              )
            );
          }
          
          // 不处理 session_idle，保持连接不断
          
          if (data.type === 'reasoning') {
            const msgId = currentAssistantMessageIdRef.current;
            setMessages((prev) => {
              const idx = prev.findIndex(m => m.id === msgId);
              if (idx === -1) return prev;
              const next = [...prev];
              next[idx] = { ...next[idx], reasoning: (next[idx].reasoning || '') + (data.content || ''), streaming: true };
              return next;
            });
          }
          
          if (data.type === 'text') {
            const msgId = currentAssistantMessageIdRef.current;
            setMessages((prev) => {
              const idx = prev.findIndex(m => m.id === msgId);
              if (idx === -1) return prev;
              const next = [...prev];
              next[idx] = { ...next[idx], content: (next[idx].content || '') + (data.content || ''), streaming: true };
              return next;
            });
          }
          
          if (data.type === 'tool') {
            const msgId = currentAssistantMessageIdRef.current;
            const toolKey = `${msgId}_${data.call_id || data.part_id || data.tool}`;

            if (data.tool === 'todowrite' && data.input && data.input.todos) {
              setCurrentTodos(data.input.todos);
              setTodoPanelVisible((prev) => {
                if (!prev && data.input.todos && data.input.todos.length > 0) {
                  return true;
                }
                return prev;
              });
            }

            // 如果没有 pendingQuestionId，但 input 中有 questions，使用 call_id 作为 questionId
            const questionId = pendingQuestionIdRef.current || data.call_id || null;

            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === msgId
                  ? {
                      ...msg,
                      tools: {
                        ...(msg.tools || {}),
                        [toolKey]: {
                          tool: data.tool,
                          state: data.state,
                          input: data.input,
                          output: data.output,
                          questionId: questionId,
                        }
                      }
                    }
                  : msg
              )
            );
          }
          
          if (data.type === 'complete') {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === currentAssistantMessageIdRef.current
                  ? { ...msg, streaming: false }
                  : msg
              )
            );
          }
          
          if (data.type === 'question.asked') {
            const realId = data.id;
            pendingQuestionIdRef.current = realId;
            console.log('[question.asked] questionId:', realId);

            setMessages(prev => prev.map(msg => {
              if (msg.tools) {
                let updated = false;
                const newTools = {};
                for (const [key, tool] of Object.entries(msg.tools)) {
                  if (tool.tool === 'question' && (tool.state === 'running' || !tool.state)) {
                    newTools[key] = { ...tool, questionId: realId };
                    updated = true;
                  } else {
                    newTools[key] = tool;
                  }
                }
                return updated ? { ...msg, tools: newTools } : msg;
              }
              return msg;
            }));
          }

          if (data.type === 'model_failover') {
            const orig = data.original_model?.modelID || '';
            const fb = data.fallback_model?.modelID || '';
            AntMessage.info({ content: `模型 ${orig} 不可用，已切换至 ${fb}`, duration: 5 });
            if (data.fallback_model) {
              setCurrentModel(prev => ({ ...prev, modelID: fb, providerID: data.fallback_model.providerID }));
            }
          }
        },
        (finalConversationId) => {
          if (finalConversationId && !conversationId) {
            setConversationId(finalConversationId);
          }
          setLoading(false);
          setIdleState(true);
          sendingRef.current = false;
          if (currentModel && currentModel.monthlyLimit > 0) {
            const updated = { ...currentModel, currentUsage: (currentModel.currentUsage || 0) + 1 };
            setCurrentModel(updated);
            lastModelRef.current[currentAgent] = updated;
          }
        },
        (err) => {
          setError(err.message || '查询失败，请稍后重试');
          setLoading(false);
          sendingRef.current = false;
        },
        currentImages.length > 0 ? currentImages.map(img => ({ base64: img.base64, name: img.name })) : null,
        currentAgent,
        currentModel,
        abortControllerRef.current.signal
      );
    } catch (err) {
      setError(err.message || '查询失败，请稍后重试');
      setLoading(false);
      sendingRef.current = false;
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleUndo = async () => {
    if (!conversationId) return;
    try {
      const result = await queryDataService.undoLastTurn(conversationId);
      if (result.success) {
        const lastUserIdx = [...messages].reverse().findIndex(m => m.type === 'user');
        if (lastUserIdx !== -1) {
          const cutIdx = messages.length - lastUserIdx;
          setMessages(prev => prev.slice(0, cutIdx - 1));
        }
        if (result.deleted_user_content) {
          setQuestion(result.deleted_user_content);
        }
        AntMessage.success('已撤销');
      }
    } catch (err) {
      AntMessage.error(err.response?.data?.detail || '撤销失败');
    }
  };

  const handleRetry = async () => {
    if (!conversationId || loading) return;
    const lastUserIdx = [...messages].reverse().findIndex(m => m.type === 'user');
    if (lastUserIdx === -1) return;

    setMessages(prev => {
      const cutIdx = prev.length - lastUserIdx;
      return prev.slice(0, cutIdx);
    });
    setLoading(true);
    setIdleState(false);
    setStreamingMessageId(null);

    const retryMsgId = (Date.now() + 1).toString();
    currentAssistantMessageIdRef.current = retryMsgId;

    setMessages(prev => [
      ...prev,
      {
        id: retryMsgId,
        type: 'assistant',
        content: '',
        reasoning: '',
        timestamp: new Date(),
        streaming: true,
      },
    ]);

    try {
      await queryDataService.retryStream(
        conversationId,
        (data) => {
          if (data.type === 'text') {
            const msgId = currentAssistantMessageIdRef.current;
            setMessages(prev => {
              const idx = prev.findIndex(m => m.id === msgId);
              if (idx === -1) return prev;
              const next = [...prev];
              next[idx] = { ...next[idx], content: (next[idx].content || '') + (data.content || ''), streaming: true };
              return next;
            });
          }
          if (data.type === 'reasoning') {
            const msgId = currentAssistantMessageIdRef.current;
            setMessages(prev => {
              const idx = prev.findIndex(m => m.id === msgId);
              if (idx === -1) return prev;
              const next = [...prev];
              next[idx] = { ...next[idx], reasoning: (next[idx].reasoning || '') + (data.content || ''), streaming: true };
              return next;
            });
          }
          if (data.type === 'tool') {
            const msgId = currentAssistantMessageIdRef.current;
            const toolKey = `${msgId}_${data.call_id || data.part_id || data.tool}`;
            setMessages(prev =>
              prev.map(msg =>
                msg.id === msgId
                  ? {
                      ...msg,
                      tools: {
                        ...(msg.tools || {}),
                        [toolKey]: {
                          tool: data.tool,
                          state: data.state,
                          input: data.input,
                          output: data.output,
                        }
                      }
                    }
                  : msg
              )
            );
          }
          if (data.type === 'message_start') {
            const newMessageId = (Date.now()).toString();
            currentAssistantMessageIdRef.current = newMessageId;
            setMessages(prev => [
              ...prev,
              { id: newMessageId, type: 'assistant', content: '', reasoning: '', timestamp: new Date(), streaming: true },
            ]);
          }
          if (data.type === 'message_complete') {
            const msgId = currentAssistantMessageIdRef.current;
            setMessages(prev => prev.map(msg => msg.id === msgId ? { ...msg, streaming: false } : msg));
          }
          if (data.type === 'model_failover') {
            const fb = data.fallback_model?.modelID || '';
            AntMessage.info({ content: `模型不可用，已切换至 ${fb}`, duration: 5 });
          }
        },
        () => {
          setLoading(false);
          setIdleState(true);
        },
        (err) => {
          setError(err.message || '重试失败');
          setLoading(false);
          setIdleState(true);
        },
        abortControllerRef.current?.signal
      );
    } catch (err) {
      setError(err.message || '重试失败');
      setLoading(false);
      setIdleState(true);
    }
  };

  const handleAbort = async () => {
    try {
      if (conversationId) {
        await queryDataService.abortQuery(conversationId);
      }
    } catch (e) {
      console.error('Abort failed:', e);
    }
    setLoading(false);
    setIdleState(true);
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  };

  // handleClear 已废弃，使用 handleNewConversation

  const handleQuestionSubmit = async (answers, toolKey) => {
    console.log('[handleQuestionSubmit] toolKey:', toolKey);
    
    // 从对应 message 的 tools 中获取 questionId
    let questionId = null;
    
    for (const msg of messages) {
      if (msg.tools && msg.tools[toolKey]) {
        questionId = msg.tools[toolKey].questionId;
        console.log('[handleQuestionSubmit] Found questionId:', questionId);
        break;
      }
    }
    
    if (!questionId) {
      AntMessage.error('无法获取问题 ID，请刷新页面重试');
      console.error('[handleQuestionSubmit] No questionId found for toolKey:', toolKey);
      return;
    }
    
    return await handleQuestionSubmitWithId(questionId, answers, toolKey);
  };
  
  const handleQuestionSubmitWithId = async (questionId, answers, toolKey) => {
    console.log('Submitting with questionId:', questionId);
    
    // 1. 从对应的 tool 中获取问题列表
    let questions = [];
    for (const msg of messages) {
      if (msg.tools && msg.tools[toolKey]) {
        const tool = msg.tools[toolKey];
        questions = tool.input?.questions || tool.questions || [];
        break;
      }
    }
    
    // 2. 将答案格式化为 API 需要的格式：[[value1], [value2], ...]
    const formattedAnswers = questions.map((q) => {
      const key = q.header || `question_${questions.indexOf(q)}`;
      const value = answers[key] || '';
      return [value];
    });
    
    console.log('Formatted answers for API:', formattedAnswers);
    
    setLoading(true);
    setError(null);
    
    try {
      // 3. 调用 question/reply API
      const response = await queryDataService.questionReply(questionId, formattedAnswers);
      
      // 4. 检查是否是本地 questionId，如果是，将答案作为用户消息发送
      if (response.data?.is_local_question && response.data?.answer_text) {
        // 将答案作为用户消息发送到当前会话
        await sendMessage(response.data.answer_text);
      } else {
        // 5. 更新工具状态为 completed（关闭表单）
        setMessages((prev) =>
          prev.map((msg) =>
            msg.tools && msg.tools[toolKey]
              ? {
                  ...msg,
                  tools: {
                    ...msg.tools,
                    [toolKey]: {
                      ...msg.tools[toolKey],
                      state: 'completed',
                      output: JSON.stringify({ answers }, null, 2)
                    }
                  }
                }
              : msg
          )
        );
        
        AntMessage.success('答案已提交');
      }
    } catch (err) {
      console.error('Failed to submit answers:', err);
      AntMessage.error('提交失败：' + (err.message || '未知错误'));
      setError(err.message || '提交失败');
    } finally {
      setLoading(false);
    }
  };

  const filterContent = (content, reasoning) => {
    if (!reasoning || !content) return content;
    
    const reasoningTrimmed = reasoning.trim();
    const contentStart = content.slice(0, reasoningTrimmed.length);
    
    if (contentStart.trim() === reasoningTrimmed) {
      return content.slice(reasoningTrimmed.length).trimStart();
    }
    
    const lines = content.split('\n');
    let skipLines = 0;
    
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].trim() === reasoningTrimmed || 
          (i > 0 && lines.slice(0, i + 1).join('\n').trim() === reasoningTrimmed)) {
        skipLines = i + 1;
        break;
      }
    }
    
    if (skipLines > 0) {
      return lines.slice(skipLines).join('\n').trimStart();
    }
    
    return content;
  };

  const exampleQuestions = [
    { icon: <FileTextOutlined />, text: '帮我解释这段代码的逻辑', color: '#1890ff' },
    { icon: <QuestionCircleOutlined />, text: '如何优化这个 Python 脚本的性能？', color: '#52c41a' },
    { icon: <BarChartOutlined />, text: '用 Python 写一个快速排序算法', color: '#722ed1' },
    { icon: <LinkOutlined />, text: '帮我翻译这段技术文档为英文', color: '#fa8c16' },
    { icon: <DeleteOutlined />, text: '这段 React 代码有什么问题？', color: '#eb2f96' },
  ];

  return (
    <div
      className="smart-query-container"
      style={{
        maxWidth: 1200,
        margin: '0 auto',
        padding: '16px',
        height: '100vh',
        boxSizing: 'border-box',
        background: '#f5f7fa',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden'
      }}
    >
      {/* 历史会话 Drawer */}
      <HistoryDrawer
        open={historyDrawerVisible}
        onClose={() => setHistoryDrawerVisible(false)}
        sessions={historySessions}
        loading={loadingHistory}
        total={historyTotal}
        selectedSessionId={conversationId}
        onSessionClick={loadSessionMessages}
        onArchiveClick={handleArchiveClick}
        onNewConversation={() => {
          handleNewConversation();
          setHistoryDrawerVisible(false);
        }}
        onRefresh={async () => {
          await loadHistorySessions(true);
          AntMessage.success('已刷新');
        }}
        onScroll={handleHistoryScroll}
        newConversationDisabled={!!conversationId && messages.length === 0}
      />

      <FileManager
        open={fileManagerVisible}
        onClose={() => setFileManagerVisible(false)}
      />

      <UserSkillManager
        open={skillManagerVisible}
        onClose={() => setSkillManagerVisible(false)}
        isMobile={isMobile}
      />

      <TaskManager
        open={taskManagerVisible}
        onClose={() => setTaskManagerVisible(false)}
        isMobile={isMobile}
      />

      <MemoryViewer
        open={memoryViewerVisible}
        onClose={() => setMemoryViewerVisible(false)}
        isMobile={isMobile}
      />

      <KnowledgeManager
        open={knowledgeManagerVisible}
        onClose={() => setKnowledgeManagerVisible(false)}
        isMobile={isMobile}
      />

      <GitTimeMachine
        open={timeMachineVisible}
        onClose={() => setTimeMachineVisible(false)}
        isMobile={isMobile}
        currentSessionId={conversationId}
      />

      <SmartEntityManager
        open={smartEntityManagerVisible}
        onClose={() => setSmartEntityManagerVisible(false)}
        isMobile={isMobile}
      />

      <SmartEntityTaskCenter
        open={smartEntityTaskCenterVisible}
        onClose={() => setSmartEntityTaskCenterVisible(false)}
        isMobile={isMobile}
      />

      {/* 归档确认 Modal */}
      <Modal
        title="确认归档"
        open={archiveModalVisible}
        onOk={handleArchiveConfirm}
        onCancel={handleArchiveCancel}
        okText="确认归档"
        cancelText="取消"
        confirmLoading={archiving}
        okButtonProps={{ danger: true }}
      >
        <p>确定要归档此会话吗？</p>
        <p style={{ color: '#6b7280', fontSize: 13, marginTop: 8 }}>
          归档后的会话将从历史列表中隐藏。
        </p>
      </Modal>

      {/* 导出模式选择 Modal */}
      <Modal
        title="选择导出模式"
        open={exportModalVisible}
        onCancel={() => setExportModalVisible(false)}
        footer={null}
        width={450}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div
            onClick={() => handleExportConfirm('full')}
            style={{
              padding: '16px',
              border: '2px solid #1890ff',
              borderRadius: '8px',
              background: '#f0f9ff',
              cursor: 'pointer',
              transition: 'all 0.2s'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#e6f7ff';
              e.currentTarget.style.transform = 'translateY(-2px)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = '#f0f9ff';
              e.currentTarget.style.transform = 'translateY(0)';
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
              <div style={{ 
                width: 32, 
                height: 32, 
                borderRadius: '50%', 
                background: '#1890ff', 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center',
                fontSize: 18
              }}>
                📄
              </div>
              <div>
                <div style={{ fontWeight: 600, fontSize: 15, color: '#1f2937' }}>完整对话导出</div>
                <div style={{ fontSize: 12, color: '#6b7280' }}>包含所有内容：问题、回答、分析过程、工具调用</div>
              </div>
            </div>
            <div style={{ 
              display: 'flex', 
              gap: 6, 
              flexWrap: 'wrap',
              marginTop: 12 
            }}>
              <Tag color="blue">完整记录</Tag>
              <Tag color="blue">分析过程</Tag>
              <Tag color="blue">工具调用</Tag>
              <Tag color="blue">详细耗时</Tag>
            </div>
          </div>

          <div
            onClick={() => handleExportConfirm('simple')}
            style={{
              padding: '16px',
              border: '2px solid #10b981',
              borderRadius: '8px',
              background: '#ecfdf5',
              cursor: 'pointer',
              transition: 'all 0.2s'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#d1fae5';
              e.currentTarget.style.transform = 'translateY(-2px)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = '#ecfdf5';
              e.currentTarget.style.transform = 'translateY(0)';
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
              <div style={{ 
                width: 32, 
                height: 32, 
                borderRadius: '50%', 
                background: '#10b981', 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center',
                fontSize: 18
              }}>
                📝
              </div>
              <div>
                <div style={{ fontWeight: 600, fontSize: 15, color: '#1f2937' }}>精简版导出</div>
                <div style={{ fontSize: 12, color: '#6b7280' }}>只保留问题和结论，删除中间过程</div>
              </div>
            </div>
            <div style={{ 
              display: 'flex', 
              gap: 6, 
              flexWrap: 'wrap',
              marginTop: 12 
            }}>
              <Tag color="green">问题</Tag>
              <Tag color="green">结论</Tag>
              <Tag color="default" style={{ opacity: 0.5 }}>无工具调用</Tag>
              <Tag color="default" style={{ opacity: 0.5 }}>无分析过程</Tag>
            </div>
          </div>
        </div>
      </Modal>

      {/* Header - Row 1: Title + User Actions */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 8,
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, overflow: 'hidden' }}>
          <Title
            level={4}
            className="smart-query-title"
            style={{ margin: 0, color: '#1f2937', flexShrink: 0 }}
          >
            OpenHub 平台
          </Title>
          {conversationId && (
            <Tag style={{
              fontSize: 10,
              background: '#f0f5ff',
              color: '#1890ff',
              border: '1px solid #91d5ff',
              borderRadius: 4,
              padding: '1px 6px',
              fontWeight: 500,
              flexShrink: 0,
              maxWidth: isMobile ? 60 : 'none',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap'
            }}>
              {conversationId.slice(-6)}
            </Tag>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {isAdmin && (
            <Button
              icon={<SettingOutlined />}
              onClick={() => navigate('/admin')}
              size="small"
              style={{ color: '#7c3aed' }}
              title="管理后台"
            >
              <span className="header-btn-text">管理后台</span>
            </Button>
          )}
          <Button
            icon={<LogoutOutlined />}
            onClick={handleLogout}
            size="small"
            style={{ color: '#6b7280' }}
            title="退出"
          >
            <span className="header-btn-text">退出</span>
          </Button>
        </div>
      </div>

      {/* Header - Row 2: Toolbar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 4,
        padding: '8px 12px',
        background: '#fafbfc',
        borderRadius: 8,
        border: '1px solid #f0f0f0',
        marginBottom: 12,
        flexShrink: 0,
      }}>
        <Button
          icon={<HistoryOutlined />}
          onClick={() => {
            setTaskManagerVisible(false);
            setTimeMachineVisible(false);
            setSmartEntityManagerVisible(false);
            setHistoryDrawerVisible(true);
          }}
          size="small"
          type="text"
          title="历史记录"
        >
          <span className="toolbar-btn-text">历史记录</span>
        </Button>
        <Button
          icon={<FolderOpenOutlined />}
          onClick={() => {
            setSkillManagerVisible(false);
            setTaskManagerVisible(false);
            setTimeMachineVisible(false);
            setSmartEntityManagerVisible(false);
            setFileManagerVisible(true);
          }}
          size="small"
          type="text"
          title="文件管理"
        >
          <span className="toolbar-btn-text">文件管理</span>
        </Button>
        <Button
          icon={<ThunderboltOutlined />}
          onClick={() => {
            setFileManagerVisible(false);
            setTaskManagerVisible(false);
            setMemoryViewerVisible(false);
            setTimeMachineVisible(false);
            setSmartEntityManagerVisible(false);
            setKnowledgeManagerVisible(false);
            setSkillManagerVisible(true);
          }}
          size="small"
          type="text"
          title="技能管理"
        >
          <span className="toolbar-btn-text">技能管理</span>
        </Button>
        <Button
          icon={<ClockCircleOutlined />}
          onClick={() => {
            setSkillManagerVisible(false);
            setTimeMachineVisible(false);
            setSmartEntityManagerVisible(false);
            setKnowledgeManagerVisible(false);
            setTaskManagerVisible(true);
          }}
          size="small"
          type="text"
          title="任务管理"
        >
          <span className="toolbar-btn-text">任务管理</span>
        </Button>
        <Button
          icon={<BookOutlined />}
          onClick={() => {
            setSkillManagerVisible(false);
            setTaskManagerVisible(false);
            setTimeMachineVisible(false);
            setSmartEntityManagerVisible(false);
            setKnowledgeManagerVisible(false);
            setMemoryViewerVisible(true);
          }}
          size="small"
          type="text"
          title="记忆"
        >
          <span className="toolbar-btn-text">记忆</span>
        </Button>
        <Button
          icon={<DatabaseOutlined />}
          onClick={() => {
            setSkillManagerVisible(false);
            setTaskManagerVisible(false);
            setTimeMachineVisible(false);
            setSmartEntityManagerVisible(false);
            setMemoryViewerVisible(false);
            setKnowledgeManagerVisible(true);
          }}
          size="small"
          type="text"
          title="知识库"
        >
          <span className="toolbar-btn-text">知识库</span>
        </Button>
        <Button
          icon={<RollbackOutlined />}
          onClick={() => {
            setFileManagerVisible(false);
            setSkillManagerVisible(false);
            setTaskManagerVisible(false);
            setMemoryViewerVisible(false);
            setSmartEntityManagerVisible(false);
            setSmartEntityTaskCenterVisible(false);
            setKnowledgeManagerVisible(false);
            setTimeMachineVisible(true);
          }}
          size="small"
          type="text"
          title="时光机"
        >
          <span className="toolbar-btn-text">时光机</span>
        </Button>
        <Button
          icon={<RobotOutlined />}
          onClick={() => {
            setSkillManagerVisible(false);
            setTaskManagerVisible(false);
            setMemoryViewerVisible(false);
            setTimeMachineVisible(false);
            setSmartEntityTaskCenterVisible(false);
            setSmartEntityTaskCenterVisible(false);
            setSmartEntityManagerVisible(false);
            setKnowledgeManagerVisible(false);
            setSmartEntityManagerVisible(true);
          }}
          size="small"
          type="text"
          title="智能体"
        >
          <span className="toolbar-btn-text">智能体</span>
        </Button>
        <Button
          icon={<TeamOutlined />}
          onClick={() => {
            setSkillManagerVisible(false);
            setTaskManagerVisible(false);
            setMemoryViewerVisible(false);
            setTimeMachineVisible(false);
            setSmartEntityManagerVisible(false);
            setKnowledgeManagerVisible(false);
            setSmartEntityTaskCenterVisible(true);
          }}
          size="small"
          type="text"
          title="协作任务"
        >
          <span className="toolbar-btn-text">协作任务</span>
        </Button>
        <NotificationBell />
      </div>

      {/* Main Card */}
      <Card 
        style={{ 
          flex: 1,
          borderRadius: 12,
          border: '1px solid #e5e7eb',
          boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden'
        }}
        styles={{ body: { padding: 0, display: 'flex', flexDirection: 'column', height: '100%' } }}
      >
        {/* Messages Area */}
        <div
          style={{
            flex: 1,
            display: 'flex',
            overflow: 'hidden',
            position: 'relative',
          }}
        >
          <div
            ref={messagesContainerRef}
            className="messages-area"
            style={{
              flex: 1,
              overflowY: 'auto',
              overflowX: 'hidden',
              padding: '12px',
              background: '#ffffff',
              WebkitOverflowScrolling: 'touch'
            }}
          >
            {messages.length === 0 ? (
              <div style={{
                textAlign: 'center',
                padding: '40px 16px',
                color: '#6b7280'
              }}>
                <div style={{
                  width: 64,
                  height: 64,
                  margin: '0 auto 20px',
                  background: '#f3f4f6',
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  <QuestionCircleOutlined style={{ fontSize: 32, color: '#9ca3af' }} />
                </div>
                <Title level={4} style={{ color: '#1f2937', margin: '0 0 12px', fontSize: '18px' }}>
                  开始对话
                </Title>
                <Text type="secondary" style={{ display: 'block', marginBottom: 24, fontSize: '13px' }}>
                  试试以下示例，或直接输入您的指令
                </Text>

                <div style={{
                  display: 'flex',
                  gap: 8,
                  justifyContent: 'center',
                  flexWrap: 'wrap',
                  width: '100%'
                }}>
                  {exampleQuestions.map((item, index) => (
                    <Button
                      key={index}
                      icon={item.icon}
                      onClick={() => sendMessage(item.text)}
                      size="small"
                      style={{
                        height: 'auto',
                        padding: '8px 16px',
                        borderRadius: 8,
                        border: '1px solid #e5e7eb',
                        background: '#ffffff',
                        color: '#374151',
                        textAlign: 'left',
                        transition: 'all 0.2s',
                        fontSize: '12px',
                        maxWidth: '100%'
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.borderColor = item.color;
                        e.currentTarget.style.color = item.color;
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = '#e5e7eb';
                        e.currentTarget.style.color = '#374151';
                      }}
                    >
                      {item.text}
                    </Button>
                  ))}
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {(() => {
                  const lastAssistantMessageId = [...messages].reverse().find(m => m.type === 'assistant')?.id;

                  return messages.map((message) => {
                    return message.type === 'user' ? (
                      <UserMessage key={message.id} message={message} />
                    ) : (
                      <AssistantMessage
                        key={message.id}
                        message={message}
                        filterContent={filterContent}
                        messageTimings={messageTimings}
                        handleQuestionSubmit={handleQuestionSubmit}
                        pendingQuestionIdRef={pendingQuestionIdRef}
                        formatDuration={formatDuration}
                        idleState={idleState}
                        lastAssistantMessageId={lastAssistantMessageId}
                        onUndo={handleUndo}
                        onRetry={handleRetry}
                      />
                    );
                  });
                })()}

                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          <TodoFloatPanel
            todos={currentTodos}
            visible={todoPanelVisible}
            onClose={() => setTodoPanelVisible(false)}
          />
        </div>

        {/* Input Area */}
        <ChatInput
          question={question}
          setQuestion={setQuestion}
          loading={loading}
          idleState={idleState}
          selectedImages={selectedImages}
          handleImageUpload={handleImageUpload}
          handleRemoveImage={handleRemoveImage}
          handleSend={handleSend}
          handleAbort={handleAbort}
          handleKeyPress={handleKeyPress}
          handleNewConversation={handleNewConversation}
          handleExportClick={handleExportClick}
          agent={currentAgent}
          setAgent={handleAgentChange}
          model={currentModel}
          setModel={setCurrentModel}
          conversationId={conversationId}
          messages={messages}
          fileInputRef={fileInputRef}
          currentTodos={currentTodos}
          todoPanelVisible={todoPanelVisible}
          onToggleTodoPanel={() => setTodoPanelVisible((v) => !v)}
        />
      </Card>



      {error && (
        <AntAlert
          message="查询失败"
          description={error}
          type="error"
          showIcon
          closable
          style={{
            marginBottom: 16,
            borderRadius: 8,
            position: 'fixed',
            bottom: 80,
            left: 16,
            right: 16,
            maxWidth: 1200,
            margin: '0 auto',
            zIndex: 100,
          }}
        />
      )}

      <style>{`
        @keyframes fadeIn {
          from {
            opacity: 0;
            transform: translateY(10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        /* 全局滚动控制 - 防止移动端弹性滚动传递到页面 */
        html, body {
          margin: 0 !important;
          padding: 0 !important;
          height: 100%;
          overscroll-behavior: none;
          touch-action: manipulation;
        }

        /* 桌面端样式优化 */
        @media (min-width: 769px) {
          .message-space {
            max-width: 700px !important;
          }
          
          .message-bubble {
            max-width: 600px !important;
            width: auto !important;
            display: inline-block !important;
          }
          
          /* 桌面端：头像和气泡左右排列 */
          .ant-space-horizontal {
            display: inline-flex !important;
            flex-direction: row !important;
            align-items: flex-start !important;
            max-width: 700px !important;
          }
          
          /* 助手消息：头像在左，气泡在右 */
          .message-item-assistant .ant-space-horizontal {
            flex-direction: row !important;
          }
          
          /* 用户消息：气泡在左，头像在右 */
          .message-item-user .ant-space-horizontal {
            flex-direction: row !important;
          }
          
          .message-item-user .ant-space-item:first-child {
            order: 1 !important;
          }
          
          .message-item-user .ant-space-item:last-child {
            order: 2 !important;
          }
          
          .ant-space-item {
            width: auto !important;
            max-width: 600px !important;
          }
          
          .markdown-content table {
            font-size: 14px;
          }
          
          .markdown-content h1 {
            font-size: 24px;
          }
          
          .markdown-content h2 {
            font-size: 20px;
          }
          
          .markdown-content h3 {
            font-size: 16px;
          }
        }
        
        /* 移动端样式 */
        @media (max-width: 768px) {
          .message-space {
            max-width: min(92vw, 600px) !important;
          }
          
          /* 移动端：头像和气泡上下排列 */
          .ant-space-horizontal {
            display: flex !important;
            flex-direction: column !important;
            align-items: flex-start !important;
            width: 100% !important;
          }
          
          /* 移动端：用户消息头像在气泡上方 */
          .message-item-user .ant-space-horizontal {
            align-items: flex-end !important;
          }
          
          .ant-space-item {
            width: 100% !important;
          }
          
          .message-bubble {
            max-width: 100% !important;
            word-break: break-word !important;
          }
          
          /* 移动端头像和气泡上下排列 - 助手消息 */
          .message-item-assistant .message-space {
            display: flex !important;
            flex-direction: column !important;
            align-items: flex-start !important;
            width: 100% !important;
            max-width: 100% !important;
          }
          
          .message-item-assistant .message-space .ant-avatar {
            order: 1;
            margin-bottom: 6px !important;
            margin-right: 0 !important;
          }
          
          .message-item-assistant .message-space .message-bubble {
            order: 2;
            width: auto !important;
            max-width: calc(100vw - 80px) !important;
          }
          
          /* 移动端头像和气泡上下排列 - 用户消息 */
          .message-item-user .message-space {
            display: flex !important;
            flex-direction: column !important;
            align-items: flex-end !important;
            width: 100% !important;
            max-width: 100% !important;
          }
          
          .message-item-user .message-space .message-bubble {
            order: 1;
            margin-bottom: 6px !important;
            width: auto !important;
            max-width: calc(100vw - 80px) !important;
          }
          
          .message-item-user .message-space .ant-avatar {
            order: 2;
            margin-left: auto !important;
            display: block !important;
          }
          
          /* 防止内容溢出 */
          .message-bubble .ant-card-body {
            overflow-wrap: break-word !important;
            word-wrap: break-word !important;
            padding: 10px 12px !important;
          }
          
          .markdown-content {
            max-width: 100%;
            overflow-wrap: break-word;
            word-wrap: break-word;
            line-height: 1.6;
          }
          
          .markdown-content table {
            font-size: 12px;
            overflow-x: auto;
            display: block;
            max-width: 100%;
          }
          
          .markdown-content h1 {
            font-size: 18px;
          }
          
          .markdown-content h2 {
            font-size: 16px;
          }
          
          .markdown-content h3 {
            font-size: 14px;
          }
          
          .markdown-content p,
          .markdown-content li {
            font-size: 13px !important;
            line-height: 1.5 !important;
          }
          
          .markdown-content pre {
            font-size: 11px !important;
            padding: 8px !important;
          }
        }
        
        .markdown-content p {
          margin: 12px 0;
          line-height: 1.8;
        }
        
        .markdown-content p:first-child {
          margin-top: 0;
        }
        
        .markdown-content p:last-child {
          margin-bottom: 0;
        }

        .markdown-content h1,
        .markdown-content h2,
        .markdown-content h3 {
          margin: 24px 0 12px;
          font-weight: 600;
          line-height: 1.4;
        }

        .markdown-content h1 { font-size: 24px; color: #1f2937; }
        .markdown-content h2 { font-size: 20px; color: #1f2937; }
        .markdown-content h3 { font-size: 16px; color: #374151; }

        .markdown-content ul,
        .markdown-content ol {
          margin: 12px 0;
          padding-left: 24px;
        }

        .markdown-content li {
          margin: 8px 0;
          line-height: 1.7;
        }

        .markdown-content code {
          background: #f3f4f6;
          padding: 3px 8px;
          border-radius: 4px;
          font-size: 0.9em;
          color: #dc2626;
          font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
        }

        .markdown-content pre {
          background: #1f2937;
          color: #f9fafb;
          padding: 16px;
          border-radius: 8px;
          overflow: auto;
          margin: 16px 0;
          font-size: 13px;
          line-height: 1.6;
          font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
        }

        .markdown-content pre code {
          background: transparent;
          color: inherit;
          padding: 0;
        }

        .markdown-content blockquote {
          border-left: 4px solid #3b82f6;
          margin: 16px 0;
          padding: 12px 16px;
          background: #f9fafb;
          border-radius: 0 8px 8px 0;
          color: #374151;
        }

        .markdown-content table {
          width: 100%;
          border-collapse: collapse;
          margin: 16px 0;
          font-size: 14px;
        }

        .markdown-content th {
          background: #f9fafb;
          border: 1px solid #e5e7eb;
          padding: 10px 14px;
          font-weight: 600;
          text-align: left;
          color: #1f2937;
        }

        .markdown-content td {
          border: 1px solid #e5e7eb;
          padding: 10px 14px;
          color: #374151;
        }

        .markdown-content tr:nth-child(even) {
          background: #f9fafb;
        }

        .markdown-content a {
          color: #2563eb;
          text-decoration: none;
          border-bottom: 1px solid transparent;
          transition: border-color 0.2s;
        }

        .markdown-content a:hover {
          border-bottom-color: #2563eb;
        }
        
        /* 移动端优化 */
        @media (max-width: 768px) {
          html, body {
            height: 100%;
            overscroll-behavior: none;
            touch-action: manipulation;
            overflow: hidden;
            width: 100%;
          }

          .smart-query-container {
            padding: 4px !important;
            padding-bottom: calc(4px + env(safe-area-inset-bottom)) !important;
            height: 100svh !important;
            overscroll-behavior: none;
            touch-action: manipulation;
            overflow: hidden;
            max-width: 100vw !important;
            box-sizing: border-box !important;
          }

          .smart-query-container > * {
            min-width: 0 !important;
            max-width: 100% !important;
          }

          .smart-query-container .ant-card {
            max-width: 100% !important;
            overflow: hidden !important;
          }

          .smart-query-container .ant-card-body {
            max-width: 100% !important;
            overflow: hidden !important;
          }

          .smart-query-header {
            margin-bottom: 12px !important;
          }

          .smart-query-title {
            font-size: 18px !important;
          }

          .smart-query-subtitle {
            font-size: 11px !important;
          }

          .messages-area {
            padding: 8px !important;
            touch-action: manipulation;
            -webkit-overflow-scrolling: touch;
            overflow-x: hidden !important;
            overflow-y: auto !important;
          }

          .message-bubble {
            font-size: 13px !important;
            max-width: calc(100vw - 16px) !important;
            overflow-wrap: break-word !important;
            word-break: break-word !important;
          }
          
          .message-bubble .ant-card-body {
            padding: 8px 10px !important;
          }
          
          .input-area {
            padding: 8px 10px !important;
            padding-bottom: calc(8px + env(safe-area-inset-bottom)) !important;
            max-width: 100% !important;
            overflow: hidden !important;
            box-sizing: border-box !important;
          }

          .input-area > * {
            max-width: 100% !important;
            overflow: hidden !important;
          }
          
          .markdown-content h1 {
            font-size: 16px !important;
          }
          
          .markdown-content h2 {
            font-size: 15px !important;
          }
          
          .markdown-content h3 {
            font-size: 14px !important;
          }
          
          .markdown-content p,
          .markdown-content li {
            font-size: 13px !important;
            line-height: 1.5 !important;
          }
          
          .markdown-content pre {
            font-size: 11px !important;
            padding: 8px !important;
          }

          /* 移动端隐藏工具栏按钮文字 */
          .toolbar-btn-text {
            display: none !important;
          }

          /* 移动端隐藏Header按钮文字 */
          .header-btn-text {
            display: none !important;
          }

          /* 强制按钮水平排列 */
          .ant-btn {
            display: inline-flex !important;
            flex-direction: row !important;
            align-items: center !important;
            white-space: nowrap !important;
          }
        }
        
        /* 小屏幕手机优化 */
        @media (max-width: 375px) {
          .smart-query-title {
            font-size: 17px !important;
          }
          
          .messages-area {
            padding: 6px !important;
          }
          
          .message-bubble .ant-card-body {
            padding: 6px 8px !important;
          }
          
          .markdown-content {
            font-size: 12px !important;
          }
        }
        
        /* 导出按钮移动端适配 */
        @media (max-width: 768px) {
          .export-doc-button {
            bottom: 70px !important;
            right: 16px !important;
            height: 40px !important;
            padding: 0 16px !important;
            font-size: 13px !important;
          }
        }
      `}</style>
    </div>
  );
};

export default SmartQueryPage;
