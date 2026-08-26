/** The only part of the transcript that re-renders while assistant prose streams. */
import { useEffect, useRef, useSyncExternalStore } from 'react';
import type { StreamedTextStore } from '../lib/streamedText';
import { Markdown } from './Markdown';

export interface StreamingMarkdownProps {
  store: StreamedTextStore;
}

export function StreamingMarkdown({ store }: StreamingMarkdownProps) {
  const text = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot);
  const prose = useRef<HTMLDivElement>(null);

  // Transcript auto-scroll previously depended on replacing the full `turns` array for every text
  // chunk. The streaming subtree now owns that small concern, too, without waking the old turns.
  useEffect(() => {
    if (text) prose.current?.scrollIntoView({ block: 'end' });
  }, [text]);

  if (!text) return null;

  return (
    <div ref={prose}>
      <Markdown className="prose" text={text} />
    </div>
  );
}
