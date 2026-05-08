import { useState, useEffect, useRef, useCallback } from 'react';
import { Drawer, Card, Tag, Space, Spin, Empty, Typography, Button, Select, Collapse } from 'antd';
import {
  TeamOutlined, RobotOutlined, ClockCircleOutlined,
  CheckCircleOutlined, CloseCircleOutlined, LoadingOutlined,
  SyncOutlined, ThunderboltOutlined,
} from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import { teamService } from '../services/api';

const { Text, Paragraph } = Typography;

const STATUS_CONFIG = {
  pending: { color: 'default', icon: <ClockCircleOutlined />, label: '等待中' },
  accepted: { color: 'processing', icon: <SyncOutlined spin />, label: '已接受' },
  processing: { color: 'processing', icon: <LoadingOutlined />, label: '处理中' },
  completed: { color: 'success', icon: <CheckCircleOutlined />, label: '已完成' },
  failed: { color: 'error', icon: <CloseCircleOutlined />, label: '失败' },
  timeout: { color: 'warning', icon: <ClockCircleOutlined />, label: '超时' },
  rejected: { color: 'error', icon: <CloseCircleOutlined />, label: '已拒绝' },
  running: { color: 'processing', icon: <LoadingOutlined />, label: '运行中' },
};

function formatDuration(start, end) {
  if (!start) return '';
  const s = new Date(start);
  const e = end ? new Date(end) : new Date();
  const diff = Math.max(0, Math.floor((e - s) / 1000));
  if (diff < 60) return `${diff}s`;
  const m = Math.floor(diff / 60);
  const sec = diff % 60;
  return `${m}m ${sec}s`;
}

function formatTime(dt) {
  if (!dt) return '';
  const d = new Date(dt);
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`;
}

function ExecutionStatusTag({ status }) {
  const cfg = STATUS_CONFIG[status] || { color: 'default', icon: null, label: status };
  return <Tag color={cfg.color} icon={cfg.icon}>{cfg.label}</Tag>;
}

function MemberTaskCard({ task }) {
  const [expanded, setExpanded] = useState(false);
  const cfg = STATUS_CONFIG[task.status] || { color: 'default', icon: null, label: task.status };
  const duration = formatDuration(task.started_at || task.accepted_at, task.completed_at);

  const resultText = task.output_data?.result || task.error_message || '';
  const hasResult = resultText && (task.status === 'completed' || task.status === 'failed');

  return (
    <Card
      size="small"
      style={{
        marginBottom: 8,
        borderLeft: `3px solid ${task.status === 'completed' ? '#52c41a' : task.status === 'failed' ? '#ff4d4f' : task.status === 'processing' ? '#1890ff' : '#d9d9d9'}`,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Space>
          <RobotOutlined style={{ color: '#666' }} />
          <Text strong>{task.entity_name || task.to_entity_id}</Text>
          <ExecutionStatusTag status={task.status} />
        </Space>
        {duration && <Text type="secondary" style={{ fontSize: 11 }}>{duration}</Text>}
      </div>
      {task.task_title && (
        <div style={{ marginTop: 4 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>{task.task_title}</Text>
        </div>
      )}
      {(task.started_at || task.accepted_at) && (
        <div style={{ marginTop: 2 }}>
          <Text type="secondary" style={{ fontSize: 11 }}>
            {formatTime(task.started_at || task.accepted_at)}
            {task.completed_at ? ` → ${formatTime(task.completed_at)}` : ' → ...'}
          </Text>
        </div>
      )}
      {task.status === 'processing' && (
        <div style={{ marginTop: 4 }}>
          <Text type="secondary" style={{ fontSize: 11 }}>
            <LoadingOutlined spin /> 执行中 {formatDuration(task.started_at || task.accepted_at)}
          </Text>
        </div>
      )}
      {hasResult && (
        <div style={{ marginTop: 6 }}>
          <Button
            type="link"
            size="small"
            style={{ padding: 0, fontSize: 12 }}
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? '收起' : '查看结果'}
          </Button>
          {expanded && (
            <div
              style={{
                marginTop: 6,
                maxHeight: 200,
                overflow: 'auto',
                padding: 8,
                background: task.status === 'completed' ? '#f6ffed' : '#fff2f0',
                border: `1px solid ${task.status === 'completed' ? '#b7eb8f' : '#ffccc7'}`,
                borderRadius: 6,
                fontSize: 12,
                lineHeight: 1.6,
              }}
            >
              <ReactMarkdown>{resultText}</ReactMarkdown>
            </div>
          )}
        </div>
      )}
      {task.status === 'failed' && task.error_message && !expanded && (
        <div style={{ marginTop: 4 }}>
          <Text type="danger" style={{ fontSize: 11 }}>{task.error_message?.slice(0, 100)}</Text>
        </div>
      )}
    </Card>
  );
}

function ExecutionCard({ execution, memberTasks, expanded, onToggle }) {
  const isRunning = execution.status === 'running';
  const completedCount = memberTasks.filter(t => t.status === 'completed').length;
  const failedCount = memberTasks.filter(t => t.status === 'failed').length;
  const totalCount = memberTasks.length;
  const duration = formatDuration(execution.created_at, execution.completed_at);

  return (
    <Card
      size="small"
      style={{
        marginBottom: 12,
        borderLeft: `3px solid ${isRunning ? '#1890ff' : execution.status === 'completed' ? '#52c41a' : '#ff4d4f'}`,
      }}
    >
      <div
        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }}
        onClick={onToggle}
      >
        <Space>
          <ExecutionStatusTag status={execution.status} />
          <Text strong style={{ maxWidth: 300 }} ellipsis>
            {execution.task_description?.slice(0, 60) || '无描述'}
          </Text>
        </Space>
        <Space>
          {isRunning && <SyncOutlined spin style={{ color: '#1890ff' }} />}
          {duration && <Text type="secondary" style={{ fontSize: 11 }}>{duration}</Text>}
          {totalCount > 0 && (
            <Text type="secondary" style={{ fontSize: 11 }}>
              {completedCount}/{totalCount} 完成
              {failedCount > 0 && <Text type="danger"> ({failedCount} 失败)</Text>}
            </Text>
          )}
          <Text type="secondary" style={{ fontSize: 11 }}>{formatTime(execution.created_at)}</Text>
        </Space>
      </div>

      {expanded && (
        <div style={{ marginTop: 12 }}>
          <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 8 }}>
            {execution.task_description}
          </Paragraph>
          {memberTasks.length > 0 ? (
            memberTasks.map(t => <MemberTaskCard key={t.task_id} task={t} />)
          ) : (
            <div style={{ textAlign: 'center', padding: '12px 0' }}>
              {isRunning ? (
                <Space><Spin size="small" /><Text type="secondary">编排者正在拆解任务...</Text></Space>
              ) : (
                <Text type="secondary">无成员任务</Text>
              )}
            </div>
          )}
          {execution.result && execution.status === 'completed' && (
            <Card
              size="small"
              title={<Text style={{ fontSize: 12 }}>编排者汇总结果</Text>}
              style={{ marginTop: 8, background: '#fafafa' }}
            >
              <div style={{ maxHeight: 300, overflow: 'auto', fontSize: 12, lineHeight: 1.6 }}>
                <ReactMarkdown>{execution.result}</ReactMarkdown>
              </div>
            </Card>
          )}
          {execution.error_message && execution.status === 'failed' && (
            <Card size="small" style={{ marginTop: 8, background: '#fff2f0', border: '1px solid #ffccc7' }}>
              <Text type="danger" style={{ fontSize: 12 }}>{execution.error_message}</Text>
            </Card>
          )}
        </div>
      )}
    </Card>
  );
}

export default function TeamExecutionDrawer({ open, onClose, isMobile, focusExecId }) {
  const [executions, setExecutions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [expandedId, setExpandedId] = useState(null);
  const [memberTasksMap, setMemberTasksMap] = useState({});
  const pollRef = useRef(null);

  const fetchExecutions = useCallback(async () => {
    try {
      const res = await teamService.listExecutions({ limit: 30 });
      if (res.ok) {
        setExecutions(res.executions);
      }
    } catch {}
  }, []);

  const fetchMemberTasks = useCallback(async (execId) => {
    try {
      const res = await teamService.getExecution(execId);
      if (res.ok) {
        setMemberTasksMap(prev => ({ ...prev, [execId]: res.members || [] }));
        return res.execution;
      }
    } catch {}
    return null;
  }, []);

  const refreshExpanded = useCallback(async () => {
    if (expandedId) {
      const exec = await fetchMemberTasks(expandedId);
      if (exec && exec.status !== 'running') {
        if (pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      }
    }
    await fetchExecutions();
  }, [expandedId, fetchMemberTasks, fetchExecutions]);

  useEffect(() => {
    if (open) {
      setLoading(true);
      fetchExecutions().finally(() => setLoading(false));
    } else {
      setExpandedId(null);
      setMemberTasksMap({});
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    }
  }, [open, fetchExecutions]);

  useEffect(() => {
    if (focusExecId && open) {
      setExpandedId(focusExecId);
      fetchMemberTasks(focusExecId);
    }
  }, [focusExecId, open, fetchMemberTasks]);

  useEffect(() => {
    if (expandedId) {
      const exec = executions.find(e => e.id === expandedId);
      if (exec?.status === 'running') {
        if (pollRef.current) clearInterval(pollRef.current);
        pollRef.current = setInterval(refreshExpanded, 3000);
      }
    }
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [expandedId, executions, refreshExpanded]);

  const handleToggle = async (execId) => {
    if (expandedId === execId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(execId);
    await fetchMemberTasks(execId);
  };

  const runningCount = executions.filter(e => e.status === 'running').length;

  return (
    <Drawer
      title={
        <Space>
          <TeamOutlined />
          <span>团队执行状态</span>
          {runningCount > 0 && <Tag color="processing">{runningCount} 运行中</Tag>}
        </Space>
      }
      placement="right"
      width={isMobile ? '100%' : 800}
      open={open}
      onClose={onClose}
      mask={false}
      extra={
        <Button
          size="small"
          icon={<SyncOutlined />}
          onClick={() => { fetchExecutions(); if (expandedId) fetchMemberTasks(expandedId); }}
        >
          刷新
        </Button>
      }
    >
      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <Spin size="large" />
        </div>
      ) : executions.length === 0 ? (
        <Empty description="暂无团队执行记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        executions.map(exec => (
          <ExecutionCard
            key={exec.id}
            execution={exec}
            memberTasks={memberTasksMap[exec.id] || []}
            expanded={expandedId === exec.id}
            onToggle={() => handleToggle(exec.id)}
          />
        ))
      )}
    </Drawer>
  );
}
