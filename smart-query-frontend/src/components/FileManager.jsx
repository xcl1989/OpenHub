import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Drawer, Table, Button, Input, Space, Breadcrumb, Spin, message, Typography, Image, Empty } from 'antd';
import {
  FolderOutlined,
  FileOutlined,
  FileTextOutlined,
  FileImageOutlined,
  DownloadOutlined,
  SearchOutlined,
  ArrowLeftOutlined,
  CloseOutlined,
} from '@ant-design/icons';
import { fileService } from '../services/api';

const { Text, Paragraph } = Typography;

const ICON_MAP = {
  directory: <FolderOutlined style={{ color: '#faad14' }} />,
  text: <FileTextOutlined style={{ color: '#1890ff' }} />,
  image: <FileImageOutlined style={{ color: '#52c41a' }} />,
  default: <FileOutlined style={{ color: '#8c8c8c' }} />,
};

function getFileIcon(record) {
  if (record.type === 'directory') return ICON_MAP.directory;
  if (record.isImage) return ICON_MAP.image;
  if (record.isText) return ICON_MAP.text;
  return ICON_MAP.default;
}

function formatSize(content) {
  if (!content) return '-';
  const bytes = new TextEncoder().encode(content).length;
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function FileManager({ open, onClose }) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [currentPath, setCurrentPath] = useState('');
  const [pathHistory, setPathHistory] = useState([]);
  const [previewContent, setPreviewContent] = useState(null);
  const [previewPath, setPreviewPath] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewType, setPreviewType] = useState('text');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [searching, setSearching] = useState(false);
  const [isMobile, setIsMobile] = useState(typeof window !== 'undefined' ? window.innerWidth < 768 : false);
  const [showPreview, setShowPreview] = useState(false);

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  useEffect(() => {
    if (open) {
      loadFiles('');
    } else {
      setPreviewContent(null);
      setSearchResults(null);
      setSearchQuery('');
      setShowPreview(false);
    }
  }, [open]);

  const loadFiles = useCallback(async (path) => {
    setLoading(true);
    try {
      const data = await fileService.listFiles(path);
      setFiles(data);
      setCurrentPath(path);
      setSearchResults(null);
      setSearchQuery('');
    } catch {
      message.error('加载文件列表失败');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleRowClick = useCallback((record) => {
    if (record.type === 'directory') {
      setPathHistory(prev => [...prev, currentPath]);
      loadFiles(record.path);
    } else {
      handlePreview(record);
    }
  }, [currentPath, loadFiles]);

  const handlePreview = useCallback(async (record) => {
    if (record.isImage) {
      setPreviewType('image');
      setPreviewPath(record.path);
      setPreviewContent(fileService.getDownloadUrl(record.path));
      if (isMobile) setShowPreview(true);
      return;
    }
    if (!record.isText) {
      message.info('该文件类型不支持预览，请直接下载');
      return;
    }
    setPreviewLoading(true);
    setPreviewPath(record.path);
    try {
      const data = await fileService.getFileContent(record.path);
      setPreviewContent(data.content);
      setPreviewType('text');
      if (isMobile) setShowPreview(true);
    } catch (err) {
      if (err.response?.status === 413) {
        message.warning('文件过大，请直接下载查看');
      } else {
        message.error('加载文件内容失败');
      }
    } finally {
      setPreviewLoading(false);
    }
  }, [isMobile]);

  const handleGoBack = useCallback(() => {
    if (pathHistory.length === 0) return;
    const prevPath = pathHistory[pathHistory.length - 1];
    setPathHistory(h => h.slice(0, -1));
    loadFiles(prevPath);
  }, [pathHistory, loadFiles]);

  const handleBreadcrumb = useCallback((index) => {
    if (index === -1) {
      setPathHistory([]);
      loadFiles('');
      return;
    }
    const parts = currentPath.split('/');
    const targetPath = parts.slice(0, index + 1).join('/');
    setPathHistory([]);
    loadFiles(targetPath);
  }, [currentPath, loadFiles]);

  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim()) {
      setSearchResults(null);
      return;
    }
    setSearching(true);
    try {
      const data = await fileService.searchFiles(searchQuery);
      setSearchResults(data);
    } catch {
      message.error('搜索失败');
    } finally {
      setSearching(false);
    }
  }, [searchQuery]);

  const pathParts = currentPath ? currentPath.split('/').filter(Boolean) : [];

  const breadcrumbs = [
    { title: <a onClick={() => handleBreadcrumb(-1)}>根目录</a> },
    ...pathParts.map((part, i) => ({
      title: <a onClick={() => handleBreadcrumb(i)}>{part}</a>,
    })),
  ];

  const displayFiles = searchResults !== null ? searchResults.map(f => ({ ...f, type: 'file' })) : files;

  const columns = useMemo(() => [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (name, record) => (
        <Space style={{ cursor: 'pointer' }}>
          {getFileIcon(record)}
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <Text strong={record.type === 'directory'} style={{ fontSize: isMobile ? 14 : 13 }}>{name}</Text>
            {isMobile && (
              <Text type="secondary" style={{ fontSize: 11 }}>{record.path}</Text>
            )}
          </div>
        </Space>
      ),
    },
    ...(!isMobile ? [{
      title: '路径',
      dataIndex: 'path',
      key: 'path',
      ellipsis: true,
      render: (path) => <Text type="secondary" style={{ fontSize: 12 }}>{path}</Text>,
    }] : []),
    {
      title: '操作',
      key: 'action',
      width: isMobile ? 50 : 80,
      render: (_, record) => {
        if (record.type === 'directory') return null;
        return (
          <Button
            type="link"
            size={isMobile ? "middle" : "small"}
            icon={<DownloadOutlined style={{ fontSize: isMobile ? 18 : 14 }} />}
            onClick={(e) => {
              e.stopPropagation();
              const url = fileService.getDownloadUrl(record.path);
              window.open(url, '_blank');
            }}
            style={{ padding: isMobile ? '4px 8px' : undefined }}
          />
        );
      },
    },
  ], [isMobile]);

  const codeStyle = {
    background: '#1e1e1e',
    color: '#d4d4d4',
    padding: 16,
    borderRadius: 8,
    fontSize: 13,
    fontFamily: 'Menlo, Monaco, "Courier New", monospace',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-all',
    maxHeight: '70vh',
    overflow: 'auto',
    margin: 0,
  };

  const handleClosePreview = useCallback(() => {
    setShowPreview(false);
  }, []);

  // Mobile preview view
  const renderMobilePreview = () => (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ 
        padding: '12px 16px', 
        borderBottom: '1px solid #f0f0f0',
        display: 'flex',
        alignItems: 'center',
        gap: 12
      }}>
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={handleClosePreview}
          size="small"
        />
        <Text ellipsis style={{ flex: 1, fontWeight: 500 }}>{previewPath.split('/').pop()}</Text>
        <Button
          size="small"
          icon={<DownloadOutlined />}
          onClick={() => window.open(fileService.getDownloadUrl(previewPath), '_blank')}
        />
      </div>
      <div style={{ flex: 1, overflow: 'auto', padding: 12 }}>
        {previewLoading ? (
          <Spin style={{ display: 'block', margin: '40px auto' }} />
        ) : previewType === 'image' ? (
          <Image src={previewContent} style={{ maxWidth: '100%' }} />
        ) : (
          <pre style={{...codeStyle, maxHeight: 'none', fontSize: 12}}>{previewContent}</pre>
        )}
      </div>
    </div>
  );

  // Mobile file list view
  const renderMobileFileList = () => (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '12px 16px', borderBottom: '1px solid #f0f0f0' }}>
        <Space style={{ width: '100%', marginBottom: 8 }}>
          <Button
            icon={<ArrowLeftOutlined />}
            disabled={pathHistory.length === 0}
            onClick={handleGoBack}
            size="small"
          />
          <Breadcrumb items={breadcrumbs} style={{ flex: 1, lineHeight: '32px' }} />
        </Space>
        <Space.Compact style={{ width: '100%' }}>
          <Input
            placeholder="搜索文件..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onPressEnter={handleSearch}
            prefix={<SearchOutlined />}
            allowClear
            onClear={() => setSearchResults(null)}
          />
          <Button type="primary" onClick={handleSearch} loading={searching}>搜索</Button>
        </Space.Compact>
      </div>
      <div
        style={{
          flex: 1,
          overflow: 'auto',
          WebkitOverflowScrolling: 'touch',
          touchAction: 'pan-y'
        }}
      >
        {loading ? (
          <div style={{ padding: 40, textAlign: 'center' }}>
            <Spin />
          </div>
        ) : displayFiles.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#999' }}>
            空目录
          </div>
        ) : (
          displayFiles.map((file) => (
            <div
              key={file.path}
              onClick={() => {
                console.log('[FileManager] 文件点击:', file.name, file.path);
                handleRowClick(file);
              }}
              onTouchStart={(e) => {
                console.log('[FileManager] 文件触摸:', file.name);
              }}
              style={{
                padding: '14px 16px',
                borderBottom: '1px solid #f0f0f0',
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                cursor: 'pointer',
                background: '#fff',
                pointerEvents: 'auto',
                WebkitTapHighlightColor: 'transparent'
              }}
            >
              {getFileIcon(file)}
              <div style={{ flex: 1, minWidth: 0 }}>
                <Text
                  strong={file.type === 'directory'}
                  style={{ fontSize: 14, display: 'block' }}
                  ellipsis={{ tooltip: file.name }}
                >
                  {file.name}
                </Text>
                <Text type="secondary" style={{ fontSize: 11 }} ellipsis={{ tooltip: file.path }}>
                  {file.path}
                </Text>
              </div>
              {file.type !== 'directory' && (
                <Button
                  type="link"
                  size="small"
                  icon={<DownloadOutlined style={{ fontSize: 18 }} />}
                  onClick={(e) => {
                    e.stopPropagation();
                    e.preventDefault();
                    console.log('[FileManager] 下载点击:', file.name);
                    window.open(fileService.getDownloadUrl(file.path), '_blank');
                  }}
                  style={{ padding: '4px 8px' }}
                />
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );

  return (
    <Drawer
      title={isMobile && showPreview ? '文件预览' : '文件管理'}
      placement="right"
      width={isMobile ? '100%' : 720}
      open={open}
      onClose={onClose}
      mask={false}
      styles={{ body: { padding: 0 } }}
    >
      {isMobile ? (
        showPreview ? renderMobilePreview() : renderMobileFileList()
      ) : (
        <>
          <div style={{ padding: '12px 16px', borderBottom: '1px solid #f0f0f0' }}>
            <Space style={{ width: '100%', marginBottom: 8 }}>
              <Button
                icon={<ArrowLeftOutlined />}
                disabled={pathHistory.length === 0}
                onClick={handleGoBack}
                size="small"
              />
              <Breadcrumb items={breadcrumbs} style={{ flex: 1, lineHeight: '32px' }} />
            </Space>
            <Space.Compact style={{ width: '100%' }}>
              <Input
                placeholder="搜索文件..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onPressEnter={handleSearch}
                prefix={<SearchOutlined />}
                allowClear
                onClear={() => setSearchResults(null)}
              />
              <Button type="primary" onClick={handleSearch} loading={searching}>搜索</Button>
            </Space.Compact>
          </div>

          <div style={{ display: 'flex', height: 'calc(100vh - 180px)' }}>
            <div style={{ flex: 1, borderRight: previewContent !== null ? '1px solid #f0f0f0' : 'none', overflow: 'auto' }}>
              <Table
                dataSource={displayFiles}
                columns={columns}
                rowKey="path"
                loading={loading}
                pagination={false}
                size="small"
                showHeader={false}
                locale={{ emptyText: <Empty description="空目录" /> }}
                style={{ cursor: 'default' }}
                onRow={(record) => ({
                  onClick: (e) => {
                    e.stopPropagation();
                    handleRowClick(record);
                  },
                  style: { cursor: 'pointer' }
                })}
              />
            </div>

            {previewContent !== null && (
              <div style={{ width: 340, overflow: 'auto', padding: 12 }}>
                <div style={{ marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Text ellipsis style={{ maxWidth: 200 }}>{previewPath.split('/').pop()}</Text>
                  <Space>
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      {previewType === 'text' && typeof previewContent === 'string' ? formatSize(previewContent) : ''}
                    </Text>
                    <Button
                      size="small"
                      icon={<DownloadOutlined />}
                      onClick={() => window.open(fileService.getDownloadUrl(previewPath), '_blank')}
                    />
                  </Space>
                </div>
                {previewLoading ? (
                  <Spin />
                ) : previewType === 'image' ? (
                  <Image src={previewContent} style={{ maxWidth: '100%' }} />
                ) : (
                  <pre style={codeStyle}>{previewContent}</pre>
                )}
              </div>
            )}
          </div>
        </>
      )}
    </Drawer>
  );
}

export default FileManager;
