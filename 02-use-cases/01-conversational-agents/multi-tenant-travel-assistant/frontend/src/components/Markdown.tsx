/**
 * Renders assistant prose as Markdown — safely.
 *
 * The model writes Markdown (`**bold**`, lists, the occasional link), and rendering it as literal
 * text is the "generic" tell we set out to remove. `react-markdown` is used rather than a regex
 * replacer because it parses to a **React element tree and escapes everything**: it never touches
 * `innerHTML`, and it renders no raw HTML (we do not add `rehype-raw`). So a hostile string in a
 * reply becomes visible text, never live markup — the same "the model authors words, not markup"
 * boundary the cards hold, kept while still formatting the words.
 *
 * `remark-gfm` adds the GitHub niceties the model actually uses: real bullet/number lists, and
 * autolinked URLs. Links open in a new tab with `rel="noreferrer"` so a model-supplied URL cannot
 * reach back into the app.
 */
import ReactMarkdown from 'react-markdown';
import remarkBreaks from 'remark-breaks';
import remarkGfm from 'remark-gfm';

export function Markdown({ text, className }: { text: string; className?: string }) {
  return (
    <div className={className ? `md ${className}` : 'md'}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkBreaks]}
        components={{
          a: ({ node: _node, ...props }) => <a {...props} target="_blank" rel="noreferrer" />,
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
