import React, { useState } from 'react';
import { Drawer, Button, Empty, Spin, Tag, Typography, Space, message } from 'antd';
import { SwapOutlined, FileAddOutlined, DeleteOutlined, EditOutlined } from '@ant-design/icons';
import { diffService } from '../services/api';

const { Text } = Typography;

const TYPE_CONFIG = {
  added: { color: '#52c41a', icon: <FileAddOutlined />, label: '新增' },
  removed: { color: '#ff4d4f', icon: <DeleteOutlined />, label: '删除' },
  modified: { color: '#1890ff', icon: <EditOutlined />, label: '修改' },
};

function parseDiffContent(content) {
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

function DiffViewer({ open, onClose, conversationId }) {
  const [diffs, setDiffs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState({});

  const loadDiffs = async () => {
    if (!conversationId) return;
    setLoading(true);
    try {
      const result = await diffService.getSessionDiff(conversationId);
      setDiffs(result.diffs || []);
    } catch {
      message.error('获取变更记录失败');
    } finally {
      setLoading(false);
    }
  };

  React.useEffect(() => {
    if (open && conversationId) {
      loadDiffs();
    } else {
      setDiffs([]);
      setExpanded({});
    }
  }, [open, conversationId]);

  const toggleExpand = (path) => {
    setExpanded(prev => ({ ...prev, [path]: !prev[path] }));
  };

  const LINE_STYLES = {
    added: { background: '#f6ffed', color: '#237804' },
    removed: { background: '#fff1f0', color: '#cf1322' },
    hunk: { background: '#e6f7ff', color: '#096dd9' },
    header: { background: '#fafafa', color: '#595959', fontWeight: 600 },
    context: { color: '#595959' },
  };

  return (
    <Drawer
      title="文件变更记录"
      placement="right"
      width={640}
      open={open}
      onClose={onClose}
      extra={
        <Button size="small" onClick={loadDiffs} loading={loading}>
          刷新
        </Button>
      }
    >
      {loading ? (
        <Spin />
      ) : diffs.length === 0 ? (
        <Empty description="当前会话无文件变更" />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {diffs.map((diff) => {
            const cfg = TYPE_CONFIG[diff.type] || { color: '#8c8c8c', icon: <EditOutlined />, label: diff.type };
            const isExpanded = expanded[diff.path];
            const lines = parseDiffContent(diff.content);

            return (
              <div
                key={diff.path}
                style={{
                  border: '1px solid #f0f0f0',
                  borderRadius: 8,
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    padding: '8px 12px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    background: '#fafafa',
                    cursor: 'pointer',
                  }}
                  onClick={() => toggleExpand(diff.path)}
                >
                  <Space>
                    <Tag color={cfg.color} icon={cfg.icon} style={{ margin: 0 }}>
                      {cfg.label}
                    </Tag>
                    <Text ellipsis style={{ maxWidth: 400 }}>
                      {diff.path}
                    </Text>
                  </Space>
                  <Space size={4}>
                    {diff.added > 0 && <Text style={{ color: '#52c41a', fontSize: 11 }}>+{diff.added}</Text>}
                    {diff.removed > 0 && <Text style={{ color: '#ff4d4f', fontSize: 11 }}>-{diff.removed}</Text>}
                  </Space>
                </div>

                {isExpanded && diff.content && (
                  <div style={{
                    fontFamily: 'Menlo, Monaco, "Courier New", monospace',
                    fontSize: 12,
                    lineHeight: 1.6,
                    maxHeight: 400,
                    overflow: 'auto',
                  }}>
                    {lines.map((line) => (
                      <div
                        key={line.num}
                        style={{
                          ...LINE_STYLES[line.type],
                          padding: '0 12px',
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
                )}
              </div>
            );
          })}
        </div>
      )}
    </Drawer>
  );
}

export default DiffViewer;
