import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { Box } from "@mui/material";
import "./MarkdownRenderer.css";

const MarkdownRenderer = ({ content }) => {
  return (
    <Box className="markdown-container">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw]}
        components={{
          h1: ({ node, ...props }) => <h1 className="markdown-heading1" {...props} />,
          h2: ({ node, ...props }) => <h2 className="markdown-heading2" {...props} />,
          h3: ({ node, ...props }) => <h3 className="markdown-heading3" {...props} />,
          h4: ({ node, ...props }) => <h4 className="markdown-heading4" {...props} />,
          h5: ({ node, ...props }) => <h5 className="markdown-heading5" {...props} />,
          h6: ({ node, ...props }) => <h6 className="markdown-heading6" {...props} />,
          p: ({ node, ...props }) => <p className="markdown-paragraph" {...props} />,
          a: ({ node, ...props }) => <a className="markdown-link" {...props} />,
          code: ({ node, inline, ...props }) => {
            return inline ? (
              <code className="markdown-inline-code" {...props} />
            ) : (
              <pre className="markdown-code-block">
                <code {...props} />
              </pre>
            );
          },
          ul: ({ node, ...props }) => <ul className="markdown-list markdown-unordered-list" {...props} />,
          ol: ({ node, ...props }) => <ol className="markdown-list markdown-ordered-list" {...props} />,
          li: ({ node, ...props }) => <li className="markdown-list-item" {...props} />,
          blockquote: ({ node, ...props }) => <blockquote className="markdown-blockquote" {...props} />,
          table: ({ node, ...props }) => <table className="markdown-table" {...props} />,
          th: ({ node, ...props }) => <th {...props} />,
          td: ({ node, ...props }) => <td {...props} />,
          br: () => <br />,
          hr: () => <hr className="markdown-hr" />,
          b: ({ node, ...props }) => <strong className="markdown-bold" {...props} />,
          strong: ({ node, ...props }) => <strong className="markdown-bold" {...props} />,
          i: ({ node, ...props }) => <em className="markdown-italic" {...props} />,
          em: ({ node, ...props }) => <em className="markdown-italic" {...props} />,
          u: ({ node, ...props }) => <u {...props} />,
          s: ({ node, ...props }) => <s className="markdown-strike" {...props} />,
          del: ({ node, ...props }) => <del className="markdown-strike" {...props} />,
          sup: ({ node, ...props }) => <sup className="markdown-sup" {...props} />,
          sub: ({ node, ...props }) => <sub className="markdown-sub" {...props} />,
          img: ({ node, ...props }) => <img className="markdown-image" {...props} alt={props.alt || ""} />,
        }}
      >
        {content}
      </ReactMarkdown>
    </Box>
  );
};

export default MarkdownRenderer;