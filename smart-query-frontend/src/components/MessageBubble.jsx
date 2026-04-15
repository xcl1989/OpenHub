import React, { useMemo, useRef, useEffect, useState } from 'react';
import { measureTextSync } from '../hooks/usePretextMeasure';

const MESSAGE_FONT = '15px Inter, -apple-system, BlinkMacSystemFont, sans-serif';
const LINE_HEIGHT = 24;
const PADDING_HORIZONTAL = 28;
const PADDING_VERTICAL = 24;
const REASONING_HEADER_HEIGHT = 60;
const TIMESTAMP_HEIGHT = 40;
const TOOLS_ESTIMATED_HEIGHT = 120;
const IMAGES_GRID_HEIGHT_PER_ROW = 116;

export function MessageBubble({
  message,
  maxContainerWidth = 600,
  isUser = false,
  showBubble = true,
  renderContent,
  renderReasoning,
  renderTools,
  renderTimestamp,
  renderAvatar,
}) {
  const bubbleRef = useRef(null);
  const [bubbleWidth, setBubbleWidth] = useState(0);
  const [bubbleHeight, setBubbleHeight] = useState(0);

  useEffect(() => {
    if (!bubbleRef.current) return;
    
    const updateMeasurements = () => {
      const rect = bubbleRef.current.getBoundingClientRect();
      setBubbleWidth(rect.width);
      setBubbleHeight(rect.height);
    };

    updateMeasurements();

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.borderBoxSize) {
          setBubbleWidth(entry.borderBoxSize[0].inlineSize);
          setBubbleHeight(entry.borderBoxSize[0].blockSize);
        } else {
          setBubbleWidth(entry.contentRect.width);
          setBubbleHeight(entry.contentRect.height);
        }
      }
    });

    resizeObserver.observe(bubbleRef.current);
    return () => resizeObserver.disconnect();
  }, []);

  const estimatedDimensions = useMemo(() => {
    const availableWidth = Math.min(maxContainerWidth * 0.85, 600) - PADDING_HORIZONTAL;
    
    let contentHeight = 0;
    let reasoningHeight = 0;
    let imagesHeight = 0;
    let toolsHeight = 0;

    if (message.reasoning) {
      const { height: rh } = measureTextSync(
        message.reasoning, 
        availableWidth - 20, 
        MESSAGE_FONT, 
        LINE_HEIGHT
      );
      reasoningHeight = rh + REASONING_HEADER_HEIGHT;
    }

    if (message.content) {
      const { height: ch } = measureTextSync(
        message.content,
        availableWidth,
        MESSAGE_FONT,
        LINE_HEIGHT
      );
      contentHeight = ch;
    }

    if (message.images && message.images.length > 0) {
      const rows = Math.ceil(message.images.length / 3);
      imagesHeight = rows * IMAGES_GRID_HEIGHT_PER_ROW + 16;
    }

    if (message.tools && Object.keys(message.tools).length > 0) {
      toolsHeight = TOOLS_ESTIMATED_HEIGHT;
    }

    const totalHeight = reasoningHeight + contentHeight + imagesHeight + toolsHeight + TIMESTAMP_HEIGHT;
    
    const charWidth = 8.5;
    let estimatedWidth = 0;
    if (message.content) {
      estimatedWidth = Math.min(Math.max(message.content.length * charWidth + PADDING_HORIZONTAL * 2, 200), availableWidth);
    } else {
      estimatedWidth = 200;
    }

    return {
      width: estimatedWidth,
      height: totalHeight,
      contentWidth: availableWidth,
    };
  }, [message, maxContainerWidth]);

  const bubbleStyle = isUser ? userBubbleStyle : assistantBubbleStyle;
  const maxWidth = Math.min(maxContainerWidth * 0.85, isUser ? 400 : 600);

  return (
    <div
      ref={bubbleRef}
      style={{
        ...bubbleStyle.card,
        width: bubbleWidth || estimatedDimensions.width,
        maxWidth: maxWidth,
      }}
    >
      <div style={bubbleStyle.body}>
        {message.reasoning && renderReasoning && (
          <div style={bubbleStyle.reasoning}>
            {renderReasoning()}
          </div>
        )}
        
        {message.content && (
          <div style={{
            ...bubbleStyle.content,
            width: estimatedDimensions.contentWidth,
          }}>
            {renderContent()}
          </div>
        )}

        {message.images && message.images.length > 0 && (
          <div style={bubbleStyle.images}>
            {message.images.map((img, idx) => (
              <div key={idx} style={bubbleStyle.imageItem}>
                {img.loading ? (
                  <Spin size="small" />
                ) : img.base64 ? (
                  <img 
                    src={`data:${img.type};base64,${img.base64}`}
                    alt={img.name || 'image'}
                    style={bubbleStyle.image}
                  />
                ) : (
                  <div style={bubbleStyle.imagePlaceholder}>加载中...</div>
                )}
              </div>
            ))}
          </div>
        )}

        {message.tools && renderTools && renderTools()}

        {renderTimestamp && renderTimestamp()}
      </div>
    </div>
  );
}

const baseBubbleStyle = {
  card: {
    borderRadius: 12,
    boxShadow: '0 1px 2px rgba(0,0,0,0.08)',
    border: '1px solid #e5e7eb',
    overflow: 'hidden',
  },
  body: {
    padding: '12px 14px',
  },
  reasoning: {
    marginBottom: 4,
    padding: '8px 10px',
    background: '#f9fafb',
    borderRadius: 6,
    borderLeft: '2px solid #1890ff',
  },
  content: {
    fontSize: 15,
    lineHeight: 1.6,
  },
  images: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))',
    gap: 8,
    maxWidth: '100%',
    marginBottom: 4,
  },
  imageItem: {
    width: '100%',
    aspectRatio: '1',
    borderRadius: 8,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: '#f3f4f6',
    overflow: 'hidden',
  },
  image: {
    width: '100%',
    height: '100%',
    objectFit: 'cover',
  },
  imagePlaceholder: {
    fontSize: 11,
    color: '#9ca3af',
  },
  timestamp: {
    marginTop: 8,
    paddingTop: 8,
    borderTop: '1px solid rgba(255,255,255,0.2)',
    display: 'flex',
    justifyContent: 'flex-end',
    alignItems: 'center',
    gap: 8,
    fontSize: 11,
  },
};

const userBubbleStyle = {
  card: {
    ...baseBubbleStyle.card,
    background: '#1890ff',
    color: '#fff',
    borderTopRightRadius: 4,
    border: 'none',
    boxShadow: '0 2px 8px rgba(24,144,255,0.3)',
  },
  body: {
    ...baseBubbleStyle.body,
    color: '#fff',
  },
  reasoning: {
    ...baseBubbleStyle.reasoning,
    background: 'rgba(255,255,255,0.15)',
    borderLeftColor: 'rgba(255,255,255,0.5)',
  },
  content: {
    ...baseBubbleStyle.content,
    color: '#fff',
  },
  images: baseBubbleStyle.images,
  imageItem: baseBubbleStyle.imageItem,
  image: baseBubbleStyle.image,
  imagePlaceholder: {
    ...baseBubbleStyle.imagePlaceholder,
    color: 'rgba(255,255,255,0.7)',
  },
  timestamp: {
    ...baseBubbleStyle.timestamp,
    color: 'rgba(255,255,255,0.7)',
  },
};

const assistantBubbleStyle = {
  card: {
    ...baseBubbleStyle.card,
    background: '#ffffff',
    color: '#000',
    borderTopLeftRadius: 4,
  },
  body: {
    ...baseBubbleStyle.body,
    color: '#000',
  },
  reasoning: baseBubbleStyle.reasoning,
  content: {
    ...baseBubbleStyle.content,
    color: '#1f2937',
  },
  images: baseBubbleStyle.images,
  imageItem: baseBubbleStyle.imageItem,
  image: baseBubbleStyle.image,
  imagePlaceholder: baseBubbleStyle.imagePlaceholder,
  timestamp: {
    ...baseBubbleStyle.timestamp,
    color: '#9ca3af',
  },
}

export function PretextMessageWrapper({ message, maxWidth = 600, children }) {
  const { contentWidth, estimatedHeight } = useMemo(() => {
    const text = message.content || '';
    const { height, lineCount } = measureTextSync(
      text,
      maxWidth - 40,
      MESSAGE_FONT,
      LINE_HEIGHT
    );
    return {
      contentWidth: maxWidth - 40,
      estimatedHeight: height + 80,
    };
  }, [message.content, maxWidth]);

  return (
    <div
      style={{
        width: '100%',
        minHeight: estimatedHeight,
      }}
    >
      {children}
    </div>
  );
}
