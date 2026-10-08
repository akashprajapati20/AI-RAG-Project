import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Citation } from "../types";

const CITATION = /\[(\d+(?:\s*,\s*\d+)*)\]/g; // [2], [1][3], [1, 3]: same patterns the backend parses

/**
 * The answer as Markdown, with each [n] turned into a button that opens its source.
 * [n] is rewritten to a Markdown link to "#cite-n" first, so the Markdown renderer hands it to
 * our custom link component instead of us splitting the HTML ourselves.
 */
export function Answer({ text, citations, streaming, onCite }: {
  text: string;
  citations: Citation[];
  streaming: boolean;
  onCite: (citation: Citation) => void;
}) {
  const linked = text.replace(CITATION, (_, numbers: string) =>
    numbers.split(",").map((n) => `[${n.trim()}](#cite-${n.trim()})`).join(""),
  );

  return (
    <div className={`answer ${streaming ? "streaming" : ""}`}>
      <Markdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => {
            if (href?.startsWith("#cite-")) {
              const n = Number(href.slice(6));
              const citation = citations.find((c) => c.n === n);
              return (
                <button
                  className="cite"
                  disabled={!citation}
                  title={citation?.citation ?? (streaming ? "Source available when the answer finishes" : "Unknown source")}
                  onClick={() => citation && onCite(citation)}
                >
                  {n}
                </button>
              );
            }
            return (
              <a href={href} target="_blank" rel="noreferrer">
                {children}
              </a>
            );
          },
        }}
      >
        {linked}
      </Markdown>
    </div>
  );
}

export function Sources({ citations, onCite }: { citations: Citation[]; onCite: (citation: Citation) => void }) {
  return (
    <div className="sources">
      <span className="sources-label">Sources</span>
      {citations.map((c) => (
        <button key={c.n} className="source-chip" onClick={() => onCite(c)} title={c.citation}>
          <span className="cite static">{c.n}</span>
          <span className="source-chip-text">{c.citation}</span>
        </button>
      ))}
    </div>
  );
}
