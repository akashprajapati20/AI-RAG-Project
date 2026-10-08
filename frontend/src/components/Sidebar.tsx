import type { ConversationSummary, Health } from "../types";

export function Sidebar({ conversations, currentId, health, healthError, open, onNew, onOpen, onDelete, onDocuments, onClose }: {
  conversations: ConversationSummary[];
  currentId: string | null;
  health: Health | null;
  healthError: string | null;
  open: boolean;
  onNew: () => void;
  onOpen: (id: string) => void;
  onDelete: (id: string) => void;
  onDocuments: () => void;
  onClose: () => void;
}) {
  return (
    <>
      {open && <div className="scrim" onClick={onClose} />}
      <nav className={`sidebar ${open ? "open" : ""}`}>
        <div className="brand">
          <span className="logo">B</span>
          <div>
            <strong>Brindlewave</strong>
            <span>Knowledge assistant</span>
          </div>
        </div>

        <button className="new-chat" onClick={onNew}>
          + New chat
        </button>

        <div className="conversations">
          {conversations.length === 0 && <p className="muted small">Your conversations appear here.</p>}
          {conversations.map((c) => (
            <div key={c.id} className={`conversation ${c.id === currentId ? "active" : ""}`}>
              <button className="conversation-open" onClick={() => onOpen(c.id)} title={c.title}>
                <span className="conversation-title">{c.title}</span>
                <span className="conversation-time">{relativeTime(c.updatedAt)}</span>
              </button>
              <button className="icon-button" onClick={() => onDelete(c.id)} aria-label={`Delete "${c.title}"`}>
                ×
              </button>
            </div>
          ))}
        </div>

        <div className="sidebar-footer">
          <button className="documents-button" onClick={onDocuments}>
            Documents
            {health && <span className="count">{health.documents}</span>}
          </button>
          <div className="status small" title={health ? `Embeddings: ${health.models.embedding}` : undefined}>
            <span className={`dot ${health ? "ok" : healthError ? "bad" : ""}`} />
            {health
              ? `${health.models.chat} · ${health.chunks} chunks`
              : healthError
                ? "API unreachable — is the backend running?"
                : "Connecting…"}
          </div>
        </div>
      </nav>
    </>
  );
}

function relativeTime(timestamp: number): string {
  const minutes = Math.round((Date.now() - timestamp) / 60_000);
  if (minutes < 1) return "now";
  if (minutes < 60) return `${minutes}m`;
  if (minutes < 60 * 24) return `${Math.round(minutes / 60)}h`;
  return new Date(timestamp).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
