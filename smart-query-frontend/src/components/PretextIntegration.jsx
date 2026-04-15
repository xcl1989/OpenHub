import React, { useMemo, useRef, useEffect, useState, memo } from 'react';
import { measureTextSync } from '../hooks/usePretextMeasure';

const MESSAGE_FONT = '15px Inter, -apple-system, BlinkMacSystemFont, sans-serif';
const LINE_HEIGHT = 24;
const BASE_PADDING = 28;
const REASONING_OVERHEAD = 80;
const TIMESTAMP_OVERHEAD = 50;
const TOOLS_OVERHEAD = 150;
const IMAGES_OVERHEAD_PER_ROW = 116;

export const PretextMessageItem = memo(({
  message,
  containerWidth,
  children,
  className = '',
  style = {},
}) => {
  const itemRef = useRef(null);
  const [isMeasured, setIsMeasured] = useState(false);
  const [actualHeight, setActualHeight] = useState(0);

  const estimatedHeight = useMemo(() => {
    const availableWidth = Math.min(containerWidth * 0.85, 600) - BASE_PADDING * 2;
    let height = BASE_PADDING * 2;

    if (message.reasoning) {
      const { height: rh } = measureTextSync(
        message.reasoning,
        availableWidth - 20,
        MESSAGE_FONT,
        LINE_HEIGHT
      );
      height += rh + REASONING_OVERHEAD;
    }

    if (message.content) {
      const { height: ch } = measureTextSync(
        message.content,
        availableWidth,
        MESSAGE_FONT,
        LINE_HEIGHT
      );
      height += ch;
    }

    if (message.images && message.images.length > 0) {
      const rows = Math.ceil(message.images.length / 3);
      height += rows * IMAGES_OVERHEAD_PER_ROW + 16;
    }

    if (message.tools && Object.keys(message.tools).length > 0) {
      height += TOOLS_OVERHEAD;
    }

    height += TIMESTAMP_OVERHEAD;

    return Math.max(height, 80);
  }, [
    message.content,
    message.reasoning,
    message.images,
    message.tools,
    containerWidth,
  ]);

  useEffect(() => {
    if (!itemRef.current) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const height = entry.contentRect.height;
        if (height > 0) {
          setActualHeight(height);
          setIsMeasured(true);
        }
      }
    });

    observer.observe(itemRef.current);
    return () => observer.disconnect();
  }, []);

  const minHeight = isMeasured ? actualHeight : estimatedHeight;

  return (
    <div
      ref={itemRef}
      className={className}
      style={{
        ...style,
        minHeight: `${minHeight}px`,
        transition: isMeasured ? 'min-height 0.15s ease-out' : 'none',
      }}
    >
      {children}
    </div>
  );
});

export const PretextBubbleWidth = memo(({
  message,
  maxWidth = 600,
  minWidth = 200,
  children,
  style = {},
}) => {
  const bubbleRef = useRef(null);
  const [width, setWidth] = useState(minWidth);

  useEffect(() => {
    if (!message.content || !bubbleRef.current) return;

    const text = message.content;
    const charWidth = 8.5;
    const padding = 50;
    const estimatedWidth = Math.min(
      Math.max(text.length * charWidth + padding, minWidth),
      maxWidth * 0.85
    );

    setWidth(estimatedWidth);

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const w = entry.contentRect.width;
        if (w > 50) {
          setWidth(Math.min(w, maxWidth * 0.85));
        }
      }
    });

    observer.observe(bubbleRef.current);
    return () => observer.disconnect();
  }, [message.content, maxWidth, minWidth]);

  return (
    <div ref={bubbleRef} style={{ ...style, width }}>
      {children}
    </div>
  );
});

export function useMessageHeight(message, containerWidth) {
  return useMemo(() => {
    const availableWidth = Math.min(containerWidth * 0.85, 600) - BASE_PADDING * 2;
    let height = BASE_PADDING * 2;

    if (message.reasoning) {
      const { height: rh } = measureTextSync(
        message.reasoning,
        availableWidth - 20,
        MESSAGE_FONT,
        LINE_HEIGHT
      );
      height += rh + REASONING_OVERHEAD;
    }

    if (message.content) {
      const { height: ch } = measureTextSync(
        message.content,
        availableWidth,
        MESSAGE_FONT,
        LINE_HEIGHT
      );
      height += ch;
    }

    if (message.images && message.images.length > 0) {
      const rows = Math.ceil(message.images.length / 3);
      height += rows * IMAGES_OVERHEAD_PER_ROW + 16;
    }

    if (message.tools && Object.keys(message.tools).length > 0) {
      height += TOOLS_OVERHEAD;
    }

    height += TIMESTAMP_OVERHEAD;

    return { estimatedHeight: Math.max(height, 80), contentWidth: availableWidth };
  }, [message, containerWidth]);
}

export function useDynamicBubbleWidth(message, maxWidth = 600, minWidth = 200) {
  return useMemo(() => {
    if (!message.content) return { width: minWidth };

    const text = message.content;
    const charWidth = 8.5;
    const padding = 50;
    
    const { lineCount } = measureTextSync(
      text,
      maxWidth - padding,
      MESSAGE_FONT,
      LINE_HEIGHT
    );

    const estimatedWidth = Math.min(
      Math.max(text.length * charWidth + padding, minWidth),
      maxWidth * 0.85
    );

    return { width: estimatedWidth, lineCount };
  }, [message.content, maxWidth, minWidth]);
}
