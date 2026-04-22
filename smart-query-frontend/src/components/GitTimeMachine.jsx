import React, { useState, useEffect } from 'react';
import { Drawer, Tabs, Spin, message, Space, Tag, Button, Popconfirm, Modal, Typography, Tooltip } from 'antd';
import { HistoryOutlined, FileOutlined, UndoOutlined, RightOutlined, DownOutlined } from '@ant-design/icons';
import { snapshotService } from '../services/api';

const { Text } = Typography;

function parseDiffLines(content) {
  if (!content) return [];
  const lines = content.split('\n');
  return lines.map((line, i) => {
    let type = 'context';
    if (line.startsWith('+++') || line.startsWith('---')) type = 'header';
    else if (line.startsWith('+')) type = 'added';
    else if (line.startsWith('-')) type = 'removed';
    else if (line.startsWith('@@')) type = 'hunk';
    return { num: i + 1, text: line, type };
  });
}

const LINE_STYLES = {
  added: { background: '#f6ffed', color: '#237804' },
  removed: { background: '#fff1f0', color: '#cf1322' },
  hunk: { background: '#e6f7ff', color: '#096dd9' },
  header: { background: '#fafafa', color: '#595959', fontWeight: 600 },
  context: { color: '#595959' },
};

function DiffBlock({ lines, isMobile }) {
  return (
    <div style={{
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      fontSize: isMobile ? 11 : 12,
      lineHeight: 1.6,
      maxHeight: isMobile ? '60vh' : 400,
      overflow: 'auto',
      borderTop: '1px solid #f0f0f0',
    }}>
      {lines.map((line) => (
        <div
          key={line.num}
          style={{
            ...LINE_STYLES[line.type],
            padding: isMobile ? '0 8px' : '0 12px',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-all',
          }}
        >
          <span style={{ opacity: 0.4, marginRight: 8, userSelect: 'none' }}>
            {line.num}
          </span>
          {line.text}
        </div>
      ))}
    </div>
  );
}

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
  const [expandedDiffs, setExpandedDiffs] = useState({});
  const [diffCache, setDiffCache] = useState({});

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
    setExpandedDiffs({});
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

  const handleToggleDiff = async (commitHash, filePath) => {
    const key = `${commitHash}:${filePath}`;
    if (expandedDiffs[key]) {
      setExpandedDiffs(prev => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
      return;
    }

    setExpandedDiffs(prev => ({ ...prev, [key]: true }));

    if (!diffCache[key]) {
      try {
        const result = await snapshotService.getDiff(commitHash);
        setDiffCache(prev => ({ ...prev, [key]: result.diff_content || '' }));
      } catch {
        message.error('获取 diff 内容失败');
        setExpandedDiffs(prev => {
          const next = { ...prev };
          delete next[key];
          return next;
        });
      }
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

  const extractFileDiff = (rawDiff, filePath) => {
    if (!rawDiff) return '';
    const lines = rawDiff.split('\n');
    const result = [];
    let inFile = false;
    for (const line of lines) {
      if (line.startsWith('diff --git')) {
        const match = line.match(/b\/(.+)$/);
        inFile = match && match[1] === filePath;
      }
      if (inFile) result.push(line);
    }
    return result.join('\n');
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
    const commitHash = detailData?.commit_hash;

    return (
      <Modal
        title={detailData ? `快照 ${commitHash?.substring(0, 8)}` : '快照详情'}
        open={detailVisible}
        onCancel={() => { setDetailVisible(false); setDetailData(null); setExpandedDiffs({}); }}
        footer={null}
        width={isMobile ? '95vw' : 780}
        style={{ top: isMobile ? 20 : 50 }}
        bodyStyle={{ padding: isMobile ? 12 : 24, maxHeight: isMobile ? '80vh' : '70vh', overflowY: 'auto' }}
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
            {(detailData.diff_summary || detailData.diff || []).length > 0 ? (
              <div>
                <Text strong style={{ marginBottom: 8, display: 'block' }}>文件变更：</Text>
                {(detailData.diff_summary || detailData.diff || []).map((f, i) => {
                  const diffKey = `${commitHash}:${f.path}`;
                  const isExpanded = !!expandedDiffs[diffKey];
                  const rawDiff = diffCache[diffKey];
                  const fileDiff = rawDiff ? extractFileDiff(rawDiff, f.path) : '';
                  const diffLines = fileDiff ? parseDiffLines(fileDiff) : [];

                  return (
                    <div
                      key={i}
                      style={{
                        border: '1px solid #f0f0f0',
                        borderRadius: 6,
                        marginBottom: 8,
                        overflow: 'hidden',
                      }}
                    >
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          padding: '8px 12px',
                          background: '#fafafa',
                          cursor: 'pointer',
                        }}
                        onClick={() => handleToggleDiff(commitHash, f.path)}
                      >
                        {isExpanded ? <DownOutlined style={{ marginRight: 8, fontSize: 11 }} /> : <RightOutlined style={{ marginRight: 8, fontSize: 11 }} />}
                        <FileOutlined style={{ marginRight: 8, color: '#1890ff' }} />
                        <span style={{ flex: 1, fontFamily: 'monospace', fontSize: 13 }}>{f.path}</span>
                        <Tag color="green" style={{ marginLeft: 8 }}>+{f.added}</Tag>
                        <Tag color="red">-{f.removed}</Tag>
                        <span onClick={e => e.stopPropagation()}>
                          <Button
                            type="link"
                            size="small"
                            onClick={() => handleViewFile(commitHash, f.path)}
                          >
                            查看
                          </Button>
                          {canRestore ? (
                            <Popconfirm
                              title={`确认撤销 ${f.path} 的修改？`}
                              onConfirm={() => handleUndoFile(commitHash, f.path)}
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
                        </span>
                      </div>
                      {isExpanded && diffLines.length > 0 && (
                        <DiffBlock lines={diffLines} />
                      )}
                      {isExpanded && diffLines.length === 0 && rawDiff === undefined && (
                        <div style={{ padding: '12px', textAlign: 'center' }}>
                          <Spin size="small" />
                        </div>
                      )}
                    </div>
                  );
                })}
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
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <HistoryOutlined />
            <span>时光机</span>
          </div>
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
            每次对话结束后自动保存快照。点击快照查看详情，点击文件名展开行级 diff，点击「撤销此修改」可恢复到修改前状态。
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
