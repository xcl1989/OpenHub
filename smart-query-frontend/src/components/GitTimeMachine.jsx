import React, { useState, useEffect } from 'react';
import { Drawer, Tabs, Spin, message, Space, Tag, Button, Popconfirm, Modal, Typography, Tooltip } from 'antd';
import { HistoryOutlined, FileOutlined, UndoOutlined } from '@ant-design/icons';
import { snapshotService } from '../services/api';

const { Text } = Typography;

function GitTimeMachine({ open, onClose, isMobile, currentSessionId }) {
  const width = isMobile ? '100%' : 720;
  const [loading, setLoading] = useState(false);
  const [snapshots, setSnapshots] = useState([]);
  const [detailVisible, setDetailVisible] = useState(false);
  const [detailData, setDetailData] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('all');
  const [fileModalVisible, setFileModalVisible] = useState(false);
  const [fileContent, setFileContent] = useState('');
  const [filePath, setFilePath] = useState('');

  useEffect(() => {
    if (open) {
      fetchSnapshots();
    }
  }, [open, activeTab, currentSessionId]);

  const fetchSnapshots = async () => {
    setLoading(true);
    try {
      const sessionId = activeTab === 'session' ? currentSessionId : null;
      if (activeTab === 'session' && !currentSessionId) {
        setSnapshots([]);
        setLoading(false);
        return;
      }
      const result = await snapshotService.list(1, 50, sessionId);
      setSnapshots(result.snapshots || []);
    } catch {
      message.error('获取快照列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleViewDetail = async (commitHash) => {
    setDetailLoading(true);
    setDetailVisible(true);
    try {
      const result = await snapshotService.getDetail(commitHash);
      setDetailData(result);
    } catch {
      message.error('获取快照详情失败');
    } finally {
      setDetailLoading(false);
    }
  };

  const handleViewFile = async (commitHash, path) => {
    try {
      const result = await snapshotService.getFile(commitHash, path);
      setFileContent(result.content);
      setFilePath(result.path);
      setFileModalVisible(true);
    } catch {
      message.error('获取文件内容失败');
    }
  };

  const handleUndoAll = async (commitHash) => {
    try {
      const result = await snapshotService.restoreAll(commitHash);
      if (result.ok) {
        message.success(result.message || '已撤销修改');
        fetchSnapshots();
      }
    } catch (err) {
      const detail = err?.response?.data?.detail;
      message.error(detail || '撤销失败');
    }
  };

  const handleUndoFile = async (commitHash, path) => {
    try {
      const result = await snapshotService.restoreFile(commitHash, path);
      if (result.ok) {
        message.success(result.message || `已撤销 ${path} 的修改`);
        fetchSnapshots();
      }
    } catch (err) {
      const detail = err?.response?.data?.detail;
      message.error(detail || '撤销文件失败');
    }
  };

  const formatTime = (ts) => {
    if (!ts) return '';
    return ts.replace('T', ' ').substring(0, 19);
  };

  const renderSnapshotItem = (snap) => {
    const isAutoRestore = snap.is_auto_restore;
    const canRestore = snap.can_restore !== false;
    const msgLines = (snap.commit_message || '').split('\n');
    const title = msgLines[0] || '快照';
    const diffFiles = snap.diff_summary || [];

    const undoButton = canRestore ? (
      <Popconfirm
        title="确认撤销此修改？"
        description="文件将恢复到该修改之前的状态，当前状态会先自动保存"
        onConfirm={(e) => {
          e?.stopPropagation();
          handleUndoAll(snap.commit_hash);
        }}
        onCancel={(e) => e?.stopPropagation()}
        okText="撤销"
        cancelText="取消"
      >
        <Button
          type="link"
          size="small"
          icon={<UndoOutlined />}
          onClick={(e) => e.stopPropagation()}
        >
          撤销此修改
        </Button>
      </Popconfirm>
    ) : (
      <Tooltip title="初始快照，无法撤销">
        <Button
          type="link"
          size="small"
          icon={<UndoOutlined />}
          disabled
          onClick={(e) => e.stopPropagation()}
        >
          撤销此修改
        </Button>
      </Tooltip>
    );

    return (
      <div
        key={snap.commit_hash}
        style={{
          padding: '12px 16px',
          borderBottom: '1px solid #f0f0f0',
          cursor: 'pointer',
        }}
        onClick={() => handleViewDetail(snap.commit_hash)}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {formatTime(snap.created_at)}
          </Text>
          {isAutoRestore && <Tag color="blue" style={{ fontSize: 11 }}>自动恢复</Tag>}
        </div>
        <div style={{ marginBottom: 6, fontSize: 14 }}>
          {title.length > 80 ? title.substring(0, 80) + '...' : title}
        </div>
        {diffFiles.length > 0 && (
          <div style={{ fontSize: 12, color: '#666' }}>
            修改 {diffFiles.length} 个文件：
            {diffFiles.slice(0, 3).map((f, i) => (
              <span key={i} style={{ marginLeft: 4 }}>
                {f.path.split('/').pop()}
                <span style={{ color: '#52c41a' }}>+{f.added}</span>
                <span style={{ color: '#ff4d4f' }}>-{f.removed}</span>
              </span>
            ))}
            {diffFiles.length > 3 && <span style={{ marginLeft: 4 }}>...</span>}
          </div>
        )}
        <div style={{ marginTop: 6 }}>
          {undoButton}
        </div>
      </div>
    );
  };

  const renderDetailModal = () => {
    const canRestore = detailData?.can_restore !== false;

    return (
      <Modal
        title={detailData ? `快照 ${detailData.commit_hash?.substring(0, 8)}` : '快照详情'}
        open={detailVisible}
        onCancel={() => { setDetailVisible(false); setDetailData(null); }}
        footer={null}
        width={700}
      >
        {detailLoading ? (
          <Spin style={{ display: 'block', margin: '40px auto' }} />
        ) : detailData ? (
          <div>
            <div style={{ marginBottom: 12 }}>
              <Text type="secondary">{formatTime(detailData.created_at)}</Text>
              {detailData.session_title && (
                <Text style={{ marginLeft: 12 }}>会话：{detailData.session_title}</Text>
              )}
            </div>
            <div style={{ marginBottom: 16, padding: 12, background: '#f5f5f5', borderRadius: 6 }}>
              <Text>{detailData.full_message || detailData.commit_message}</Text>
            </div>
            {(detailData.diff || []).length > 0 ? (
              <div>
                <Text strong style={{ marginBottom: 8, display: 'block' }}>文件变更：</Text>
                {(detailData.diff || []).map((f, i) => (
                  <div
                    key={i}
                    style={{
                      display: 'flex', alignItems: 'center', padding: '6px 0',
                      borderBottom: '1px solid #f5f5f5',
                    }}
                  >
                    <FileOutlined style={{ marginRight: 8, color: '#1890ff' }} />
                    <span style={{ flex: 1, fontFamily: 'monospace', fontSize: 13 }}>{f.path}</span>
                    <Tag color="green" style={{ marginLeft: 8 }}>+{f.added}</Tag>
                    <Tag color="red">-{f.removed}</Tag>
                    <Button
                      type="link"
                      size="small"
                      onClick={() => handleViewFile(detailData.commit_hash, f.path)}
                    >
                      查看
                    </Button>
                    {canRestore ? (
                      <Popconfirm
                        title={`确认撤销 ${f.path} 的修改？`}
                        onConfirm={() => handleUndoFile(detailData.commit_hash, f.path)}
                        okText="撤销"
                        cancelText="取消"
                      >
                        <Button type="link" size="small" danger>撤销此文件</Button>
                      </Popconfirm>
                    ) : (
                      <Tooltip title="初始快照，无法撤销">
                        <Button type="link" size="small" disabled>撤销此文件</Button>
                      </Tooltip>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <Text type="secondary">无文件变更记录</Text>
            )}
          </div>
        ) : null}
      </Modal>
    );
  };

  const tabItems = [
    {
      key: 'all',
      label: '全部快照',
      children: (
        <div>
          {loading ? (
            <Spin style={{ display: 'block', margin: '40px auto' }} />
          ) : snapshots.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
              暂无快照记录
            </div>
          ) : (
            snapshots.map(renderSnapshotItem)
          )}
        </div>
      ),
    },
    {
      key: 'session',
      label: '当前会话',
      children: (
        <div>
          {loading ? (
            <Spin style={{ display: 'block', margin: '40px auto' }} />
          ) : snapshots.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
              当前会话暂无快照
            </div>
          ) : (
            snapshots.map(renderSnapshotItem)
          )}
        </div>
      ),
    },
  ];

  return (
    <>
      <Drawer
        title={
          <Space>
            <HistoryOutlined />
            <span>时光机</span>
          </Space>
        }
        placement="right"
        width={width}
        onClose={onClose}
        open={open}
        mask={false}
      >
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={tabItems}
        />
        <div style={{ marginTop: 16, padding: '12px', background: '#f5f5f5', borderRadius: 6 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            每次对话结束后自动保存快照。点击「撤销此修改」可将文件恢复到该修改之前的状态，当前状态会先自动保存。
          </Text>
        </div>
      </Drawer>

      {renderDetailModal()}

      <Modal
        title={filePath}
        open={fileModalVisible}
        onCancel={() => setFileModalVisible(false)}
        footer={null}
        width={700}
      >
        <pre style={{
          background: '#282c34', color: '#abb2bf', padding: 16,
          borderRadius: 6, overflow: 'auto', maxHeight: 500, fontSize: 13,
        }}>
          {fileContent}
        </pre>
      </Modal>
    </>
  );
}

export default GitTimeMachine;
