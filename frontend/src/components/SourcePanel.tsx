import { useEffect } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Citation } from "../types";

/** The passage behind a citation, so a reader can check the answer against its source. */
export function SourcePanel({ citation, onClose }: { citation: Citation; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Markdown sources render as Markdown; PDF/text passages keep their line breaks (table rows).
  const isMarkdown = /\.(md|markdown)$/i.test(citation.source);

  return (
    <aside className="source-panel" aria-label="Source passage">
      <header>
        <span className="cite static large">{citation.n}</span>
        <h2>{citation.title}</h2>
        <button className="icon-button" onClick={onClose} aria-label="Close source">
          ×
        </button>
      </header>
      <p className="source-where">{citation.citation}</p>
      <p className="source-file">{citation.source}</p>
      <div className={`passage ${isMarkdown ? "" : "plain"}`}>
        {isMarkdown ? <Markdown remarkPlugins={[remarkGfm]}>{citation.content}</Markdown> : citation.content}
      </div>
    </aside>
  );
}
