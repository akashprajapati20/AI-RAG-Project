import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { DocumentInfo, UploadResult } from "../types";

const ACCEPT = ".pdf,.md,.markdown,.txt";

/** List the knowledge base, upload files (ingested right away) and delete documents. */
export function DocumentsPanel({ onClose, onChanged }: { onClose: () => void; onChanged: () => void }) {
  const [documents, setDocuments] = useState<DocumentInfo[] | null>(null);
  const [results, setResults] = useState<UploadResult[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try {
      setDocuments(await api.documents());
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [refresh, onClose]);

  async function upload(files: File[]) {
    if (!files.length) return;
    setUploading(true);
    setError(null);
    try {
      setResults(await api.upload(files));
      await refresh();
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUploading(false);
    }
  }

  async function remove(doc: DocumentInfo) {
    const note = doc.source.startsWith("data/uploads/")
      ? ""
      : "\n\nIts file stays in data/corpus, so re-running the ingest script would add it back.";
    if (!window.confirm(`Delete "${doc.title}" and its ${doc.chunks} chunks?${note}`)) return;
    try {
      await api.deleteDocument(doc.id);
      await refresh();
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="overlay" onClick={onClose}>
      <section className="docs-panel" role="dialog" aria-label="Documents" onClick={(e) => e.stopPropagation()}>
        <header>
          <h2>Documents {documents && <span className="count">{documents.length}</span>}</h2>
          <button className="icon-button" onClick={onClose} aria-label="Close documents">
            ×
          </button>
        </header>

        <div
          className={`dropzone ${dragging ? "dragging" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            void upload([...e.dataTransfer.files]);
          }}
          onClick={() => input.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
        >
          {uploading ? (
            <span>
              <span className="spinner" aria-hidden /> Uploading and indexing…
            </span>
          ) : (
            <span>
              Drop PDF, Markdown or text files here, or <u>browse</u>
            </span>
          )}
          <input
            ref={input}
            type="file"
            accept={ACCEPT}
            multiple
            hidden
            onChange={(e) => {
              void upload([...(e.target.files ?? [])]);
              e.target.value = "";
            }}
          />
        </div>

        {results.length > 0 && (
          <ul className="upload-results">
            {results.map((r) => (
              <li key={r.filename} className={r.status === "failed" ? "failed" : "ok"}>
                <strong>{r.filename}</strong> — {r.status === "failed" ? r.error : `${r.status}, ${r.chunks} ${r.chunks === 1 ? "chunk" : "chunks"}`}
              </li>
            ))}
          </ul>
        )}
        {error && <div className="error">{error}</div>}

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th>Type</th>
                <th className="num">Pages</th>
                <th className="num">Chunks</th>
                <th>Indexed</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {documents?.map((doc) => (
                <tr key={doc.id}>
                  <td>
                    <div className="doc-title">{doc.title}</div>
                    <div className="doc-source">{doc.source}</div>
                  </td>
                  <td>
                    <span className="badge">{doc.format ?? "?"}</span>
                  </td>
                  <td className="num">{doc.pages ?? "–"}</td>
                  <td className="num">{doc.chunks}</td>
                  <td className="muted">{doc.ingested_at ? new Date(doc.ingested_at).toLocaleDateString() : "–"}</td>
                  <td>
                    <button className="icon-button" onClick={() => void remove(doc)} aria-label={`Delete ${doc.title}`}>
                      ×
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {documents === null && !error && <p className="muted small">Loading…</p>}
        </div>
      </section>
    </div>
  );
}
