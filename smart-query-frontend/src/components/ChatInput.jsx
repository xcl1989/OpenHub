import React, { useState, useEffect, useRef } from 'react';
import { Input, Button, Image, Typography, Tooltip, Segmented, Select, Space, Tag, Drawer, Radio, List } from 'antd';
import { LinkOutlined, SendOutlined, PlusOutlined, CloseOutlined, DownloadOutlined, RobotOutlined } from '@ant-design/icons';
import { queryDataService } from '../services/api';

const { TextArea } = Input;
const { Text } = Typography;

function ModelSelect({ model, setModel }) {
  const [groupedOptions, setGroupedOptions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [searchText, setSearchText] = useState('');
  const modelsMapRef = useRef({});

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    queryDataService.fetchModels()
      .then((res) => {
        if (cancelled) return;
        const result = res.data || res;
        const models = result.models || [];
        const defaultModel = result.default || null;
        const groups = {};
        const map = {};
        for (const m of models) {
          map[m.modelID] = m;
          const groupKey = m.providerID;
          if (!groups[groupKey]) {
            groups[groupKey] = {
              label: m.providerName || m.providerID,
              options: [],
            };
          }
          groups[groupKey].options.push({
            value: m.modelID,
            label: m.name || m.modelID,
          });
        }
        modelsMapRef.current = map;
        setGroupedOptions(Object.values(groups));
        if (defaultModel && !model) {
          setModel(defaultModel);
        }
      })
      .catch(() => {
        if (!cancelled) setGroupedOptions([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  const handleChange = (modelID) => {
    if (!modelID) {
      setModel(null);
      return;
    }
    const m = modelsMapRef.current[modelID];
    if (m) {
      setModel({
        modelID: m.modelID,
        providerID: m.providerID,
        currentUsage: m.currentUsage,
        monthlyLimit: m.monthlyLimit,
      });
    }
    setDrawerOpen(false);
    setSearchText('');
  };

  const handleClear = () => {
    setModel(null);
    setDrawerOpen(false);
    setSearchText('');
  };

  const selectValue = model ? (model.modelID || model) : undefined;

  const allModels = [];
  const groupMap = {};
  for (const group of groupedOptions) {
    if (!groupMap[group.label]) {
      groupMap[group.label] = group.label;
    }
    for (const opt of group.options) {
      allModels.push({
        ...opt,
        provider: group.label,
        ...modelsMapRef.current[opt.value]
      });
    }
  }

  const filteredModels = searchText
    ? allModels.filter(m =>
        (m.label || '').toLowerCase().includes(searchText.toLowerCase()) ||
        (m.provider || '').toLowerCase().includes(searchText.toLowerCase())
      )
    : allModels;

  const groupedFiltered = {};
  for (const m of filteredModels) {
    if (!groupedFiltered[m.provider]) {
      groupedFiltered[m.provider] = [];
    }
    groupedFiltered[m.provider].push(m);
  }

  if (isMobile) {
    return (
      <>
        <Button
          size="small"
          icon={<RobotOutlined />}
          onClick={() => setDrawerOpen(true)}
          style={{
            fontSize: 12,
            height: 28,
            padding: '0 8px',
            display: 'flex',
            alignItems: 'center',
            gap: 4
          }}
        >
          {model ? (
            <span style={{ maxWidth: 80, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {model.modelID}
            </span>
          ) : (
            <span>选择模型</span>
          )}
        </Button>
        <Drawer
          title={
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span>选择模型</span>
              {model && (
                <Button type="text" size="small" onClick={handleClear} style={{ color: '#ff4d4f' }}>
                  清除
                </Button>
              )}
            </div>
          }
          placement="bottom"
          onClose={() => { setDrawerOpen(false); setSearchText(''); }}
          open={drawerOpen}
          height="70vh"
          styles={{
            body: { padding: 0 },
            header: { borderBottom: '1px solid #f0f0f0', marginBottom: 0 }
          }}
        >
          <div style={{ padding: '12px 16px', borderBottom: '1px solid #f0f0f0' }}>
            <Input.Search
              placeholder="搜索模型..."
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              allowClear
              onClear={() => setSearchText('')}
              style={{ width: '100%' }}
            />
          </div>
          <div style={{ overflow: 'auto', flex: 1, padding: '8px 0' }}>
            {Object.entries(groupedFiltered).map(([provider, models]) => (
              <div key={provider}>
                <div style={{
                  padding: '8px 16px',
                  fontSize: 12,
                  color: '#666',
                  background: '#f5f5f5',
                  fontWeight: 500
                }}>
                  {provider}
                </div>
                <div style={{ width: '100%', display: 'flex', flexDirection: 'column' }}>
                  {models.map((m) => {
                    const remaining = m.monthlyLimit ? m.monthlyLimit - (m.currentUsage || 0) : null;
                    const isLimitReached = m.monthlyLimit && remaining <= 0;
                    const isSelected = selectValue === m.value;
                    const displayName = m.name || m.label || m.modelID || m.value;
                    return (
                      <div
                        key={m.value}
                        onClick={() => !isLimitReached && handleChange(m.value)}
                        style={{
                          display: 'flex',
                          alignItems: 'flex-start',
                          gap: 12,
                          padding: '14px 16px',
                          cursor: isLimitReached ? 'not-allowed' : 'pointer',
                          background: isSelected ? '#e6f7ff' : 'transparent',
                          borderBottom: '1px solid #f0f0f0',
                          opacity: isLimitReached ? 0.5 : 1
                        }}
                      >
                        <Radio
                          checked={isSelected}
                          disabled={isLimitReached}
                          style={{ marginTop: 2 }}
                        />
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, flex: 1, minWidth: 0 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{
                              fontWeight: 500,
                              color: isSelected ? '#1890ff' : '#333',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap'
                            }}>
                              {displayName}
                            </span>
                            {isLimitReached && (
                              <Tag color="red" style={{ fontSize: 10, margin: 0 }}>已达上限</Tag>
                            )}
                          </div>
                          {remaining !== null && !isLimitReached && (
                            <Text type="secondary" style={{ fontSize: 11 }}>
                              本月剩余: {remaining} / {m.monthlyLimit}
                            </Text>
                          )}
                          {remaining === null && (
                            <Text type="secondary" style={{ fontSize: 11 }}>
                              无使用限制
                            </Text>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
            {filteredModels.length === 0 && (
              <div style={{ padding: 40, textAlign: 'center', color: '#999' }}>
                未找到匹配的模型
              </div>
            )}
          </div>
        </Drawer>
      </>
    );
  }

  return (
    <Select
      value={selectValue}
      onChange={handleChange}
      placeholder="默认模型"
      loading={loading}
      allowClear
      showSearch
      optionFilterProp="label"
      size="small"
      style={{ minWidth: 140, fontSize: 12 }}
      options={groupedOptions}
      popupMatchSelectWidth={false}
    />
  );
}

export default function ChatInput({
  question,
  setQuestion,
  loading,
  idleState,
  selectedImages,
  handleImageUpload,
  handleRemoveImage,
  handleSend,
  handleAbort,
  handleKeyPress,
  handleNewConversation,
  handleExportClick,
  agent,
  setAgent,
  model,
  setModel,
  conversationId,
  messages,
  fileInputRef,
  currentTodos,
  todoPanelVisible,
  onToggleTodoPanel,
}) {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  return (
    <div className="input-area" style={{ 
      padding: '6px 12px',
      background: '#ffffff',
      borderTop: '1px solid #e5e7eb',
      borderRadius: '0 0 12px 12px',
      flexShrink: 0
    }}>
      {selectedImages.length > 0 && (
        <div style={{ 
          marginBottom: 12, 
          display: 'flex',
          gap: 8,
          flexWrap: 'wrap'
        }}>
          {selectedImages.map((img, index) => (
            <div 
              key={index}
              style={{ 
                position: 'relative',
                width: 100,
                height: 100
              }}
            >
              <Image 
                src={`data:${img.type};base64,${img.base64}`} 
                alt={img.name} 
                style={{ 
                  width: 100,
                  height: 100,
                  borderRadius: 8, 
                  border: '2px solid #e5e7eb',
                  objectFit: 'cover',
                  boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
                  cursor: 'pointer'
                }}
                preview={{
                  mask: false
                }}
              />
              <Button
                type="text"
                size="small"
                icon={<CloseOutlined />}
                onClick={() => handleRemoveImage(index)}
                style={{
                  position: 'absolute',
                  top: -6,
                  right: -6,
                  background: '#ff4d4f',
                  color: 'white',
                  borderRadius: '50%',
                  minWidth: '22px',
                  height: '22px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
                  zIndex: 1
                }}
              />
            </div>
          ))}
        </div>
      )}
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 6, gap: 8 }}>
        <Segmented
          value={agent}
          onChange={(val) => setAgent(val)}
          size="small"
          options={[
            { label: 'Build', value: 'build' },
            { label: 'Plan', value: 'plan' },
          ]}
          style={{ fontSize: 12, flexShrink: 0 }}
        />
        <ModelSelect model={model} setModel={setModel} />
        {model?.monthlyLimit !== undefined && (() => {
          const limit = model.monthlyLimit;
          const used = model.currentUsage || 0;
          const remaining = Math.max(0, limit - used);
          const color = limit === 0 ? 'green' : remaining === 0 ? 'red' : 'blue';
          const label = limit === 0 ? '不限' : `${remaining} 余量`;
          return (
            <Tag color={color} style={{ fontSize: 11 }}>
              {label}
            </Tag>
          );
        })()}
        {currentTodos && currentTodos.length > 0 && (
          <button
            onClick={onToggleTodoPanel}
            style={{
              marginLeft: 'auto',
              border: 'none',
              background: todoPanelVisible ? '#e6f7ff' : '#f5f5f5',
              color: todoPanelVisible ? '#1890ff' : '#6b7280',
              borderRadius: 6,
              padding: '4px 10px',
              fontSize: 12,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              flexShrink: 0,
              transition: 'all 0.2s',
            }}
            title="任务列表"
          >
            <span style={{ fontSize: 13 }}>📋</span>
            <span>任务</span>
          </button>
        )}
      </div>
      <div style={{ 
        display: 'flex', 
        gap: 12, 
        alignItems: 'flex-end',
        background: '#f5f7fa',
        padding: '12px',
        borderRadius: '12px',
        border: '1px solid #e5e7eb'
      }}>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          multiple
          style={{ display: 'none' }}
          onChange={(e) => {
            const files = e.target.files;
            if (files && files.length > 0) {
              handleImageUpload(files);
            }
          }}
        />
        <Button
          icon={<LinkOutlined />}
          onClick={() => fileInputRef.current?.click()}
          disabled={loading && !idleState}
          size="large"
          style={{
            border: '1px solid #d9d9d9',
            borderRadius: '8px',
            background: 'white',
            width: 40,
            height: 40,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 16,
            flexShrink: 0
          }}
          title="上传图片"
        />
        <TextArea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="输入您的问题，按 Enter 发送..."
          autoSize={{ minRows: 2, maxRows: 5 }}
          disabled={loading && !idleState}
          style={{
            fontSize: isMobile ? 16 : 13,
            background: 'transparent',
            resize: 'none',
            flex: 1,
            cursor: loading && !idleState ? 'not-allowed' : 'text',
            opacity: loading && !idleState ? 0.5 : 1,
            color: loading && !idleState ? 'rgba(0, 0, 0, 0.45)' : '#1f2937',
            padding: '8px 12px',
            borderRadius: '8px',
            border: loading && !idleState ? '1px solid #e5e7eb' : '1px solid transparent',
            transition: 'all 0.2s',
            outline: 'none'
          }}
          disabledstyle={{
            background: '#f5f5f5',
            color: 'rgba(0, 0, 0, 0.45)',
            borderColor: '#e5e7eb',
            borderWidth: '1px',
            borderStyle: 'solid'
          }}
        />
        {loading && !idleState ? (
          <Button
            danger
            size="large"
            onClick={handleAbort}
            style={{
              background: '#ff4d4f',
              border: 'none',
              borderRadius: '8px',
              padding: isMobile ? '0 10px' : '0 20px',
              height: isMobile ? 36 : 40,
              fontWeight: 500,
              flexShrink: 0,
              display: 'flex',
              alignItems: 'center',
              gap: isMobile ? 0 : 6
            }}
          >
            {isMobile ? (
              <span style={{ display: 'inline-block', width: 14, height: 14, background: '#fff', borderRadius: 2 }} />
            ) : (
              <>
                <span style={{ display: 'inline-block', width: 14, height: 14, background: '#fff', borderRadius: 2 }} />
                停止
              </>
            )}
          </Button>
        ) : (
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={() => handleSend()}
            disabled={(!question.trim() && selectedImages.length === 0) || (model?.monthlyLimit > 0 && (model?.currentUsage || 0) >= model?.monthlyLimit)}
            title={model?.monthlyLimit > 0 && (model?.currentUsage || 0) >= model?.monthlyLimit ? '模型调用次数已达上限，请更换模型或联系管理员' : ''}
            size="large"
            style={{
              background: '#1890ff',
              border: 'none',
              borderRadius: '8px',
              padding: isMobile ? '0 10px' : '0 20px',
              height: isMobile ? 36 : 40,
              fontWeight: 500,
              flexShrink: 0
            }}
          >
            {isMobile ? null : '发送'}
          </Button>
        )}
      </div>
      <div style={{
        marginTop: 10,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: 6
      }}>
        {!isMobile && (
          <Text type="secondary" style={{ fontSize: 12 }}>
            支持多轮对话，AI 会自动理解上下文
          </Text>
        )}
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {messages.length > 0 && (
            <Tooltip title="导出对话为 PDF 文档" placement="top">
              <Button
                type="primary"
                icon={<DownloadOutlined />}
                onClick={handleExportClick}
                size="small"
                style={{
                  background: '#1890ff',
                  border: 'none',
                  borderRadius: '6px',
                  fontWeight: 500,
                  boxShadow: '0 2px 4px rgba(24,144,255,0.3)'
                }}
              >
                导出 PDF
              </Button>
            </Tooltip>
          )}
          <Button
            icon={<PlusOutlined />}
            size="small"
            onClick={handleNewConversation}
            disabled={!conversationId || messages.length === 0}
            style={{
              border: '1px solid #e5e7eb',
              borderRadius: 6,
              opacity: (!conversationId || messages.length === 0) ? 0.5 : 1
            }}
          >
            新建对话
          </Button>
        </div>
      </div>
    </div>
  );
}
