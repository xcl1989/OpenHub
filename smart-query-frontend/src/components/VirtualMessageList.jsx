import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { measureTextSync, estimateMessageHeight } from '../hooks/usePretextMeasure';

const ITEM_HEIGHT_ESTIMATE = 150;
const OVERSCAN = 5;

export function VirtualMessageList({
  messages,
  containerWidth,
  renderMessage,
  onScroll,
  messagesEndRef,
  loadMore,
  hasMore,
}) {
  const containerRef = useRef(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [containerHeight, setContainerHeight] = useState(0);

  const itemHeights = useMemo(() => {
    const heights = [];
    let cumulativeHeight = 0;

    messages.forEach((message, index) => {
      const { estimatedHeight } = estimateMessageHeight(message, containerWidth);
      cumulativeHeight += estimatedHeight;
      heights.push({ index, height: estimatedHeight, offset: cumulativeHeight - estimatedHeight });
    });

    return heights;
  }, [messages, containerWidth]);

  const totalHeight = itemHeights.length > 0 
    ? itemHeights[itemHeights.length - 1].offset + itemHeights[itemHeights.length - 1].height 
    : 0;

  const visibleRange = useMemo(() => {
    if (itemHeights.length === 0) return { start: 0, end: 10 };

    let start = 0;
    let end = messages.length;

    for (let i = 0; i < itemHeights.length; i++) {
      if (itemHeights[i].offset + itemHeights[i].height > scrollTop) {
        start = Math.max(0, i - OVERSCAN);
        break;
      }
    }

    const viewportBottom = scrollTop + containerHeight;
    for (let i = 0; i < itemHeights.length; i++) {
      if (itemHeights[i].offset > viewportBottom) {
        end = Math.min(messages.length, i + OVERSCAN);
        break;
      }
    }

    return { start, end };
  }, [scrollTop, containerHeight, itemHeights, messages.length]);

  const visibleMessages = useMemo(() => {
    const { start, end } = visibleRange;
    return messages.slice(start, end).map((message, i) => ({
      message,
      index: start + i,
      style: {
        position: 'absolute',
        top: itemHeights[start + i]?.offset || 0,
        left: 0,
        right: 0,
        width: '100%',
      }
    }));
  }, [messages, visibleRange, itemHeights]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setContainerHeight(entry.contentRect.height);
      }
    });

    resizeObserver.observe(container);
    return () => resizeObserver.disconnect();
  }, []);

  const handleScroll = useCallback((e) => {
    const { scrollTop: newScrollTop, scrollHeight, clientHeight } = e.target;
    setScrollTop(newScrollTop);
    
    if (onScroll) {
      onScroll(e);
    }

    if (loadMore && hasMore && newScrollTop < 100) {
      loadMore();
    }
  }, [onScroll, loadMore, hasMore]);

  useEffect(() => {
    if (messagesEndRef?.current && messages.length > 0) {
      const container = containerRef.current;
      if (container) {
        const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 200;
        if (isNearBottom) {
          messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
        }
      }
    }
  }, [messages.length, messagesEndRef]);

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      style={{
        flex: 1,
        overflowY: 'auto',
        overflowX: 'hidden',
        position: 'relative',
        WebkitOverflowScrolling: 'touch',
      }}
    >
      <div style={{ height: totalHeight, position: 'relative', width: '100%' }}>
        {visibleMessages.map(({ message, index, style }) => (
          <div key={message.id} style={style}>
            {renderMessage(message, index)}
          </div>
        ))}
      </div>
      {messagesEndRef && <div ref={messagesEndRef} />}
    </div>
  );
}

export function DynamicBubbleWidth({ message, children, maxWidth = 600, minWidth = 200 }) {
  const bubbleRef = useRef(null);
  const [bubbleWidth, setBubbleWidth] = useState(minWidth);

  useEffect(() => {
    if (!message.content) return;

    const text = message.content;
    const charWidth = 8.5;
    const padding = 40;
    const lineHeight = 24;
    
    const { height, lineCount } = measureTextSync(text, maxWidth - padding, '15px Inter', lineHeight);
    const contentWidth = Math.min(Math.max(text.length * charWidth + padding, minWidth), maxWidth);

    setBubbleWidth(Math.min(contentWidth, maxWidth));
  }, [message.content, maxWidth, minWidth]);

  return (
    <div ref={bubbleRef} style={{ width: bubbleWidth, maxWidth }}>
      {children}
    </div>
  );
}
