import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { ChatView } from "./components/ChatView";
import { DocumentsPanel } from "./components/DocumentsPanel";
import { Sidebar } from "./components/Sidebar";
import { SourcePanel } from "./components/SourcePanel";
import { loadConversations, saveConversations, upsertConversation } from "./conversations";
import type { Citation, ConversationSummary, Health } from "./types";
import { useChat } from "./useChat";

export default function App() {
  const chat = useChat();
  const [conversations, setConversations] = useState<ConversationSummary[]>(loadConversations);
  const [source, setSource] = useState<Citation | null>(null);
  const [showDocuments, setShowDocuments] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  // True while a saved conversation loads (initially, if the URL names one), so the empty
  // state doesn't flash before its messages arrive.
  const [opening, setOpening] = useState(() => location.hash.length > 1);

  useEffect(() => saveConversations(conversations), [conversations]);

  const refreshHealth = useCallback(() => {
    api.health().then(
      (h) => {
        setHealth(h);
        setHealthError(null);
      },
      (e: Error) => setHealthError(e.message),
    );
  }, []);
  useEffect(refreshHealth, [refreshHealth]);

  const openConversation = useCallback(
    async (id: string) => {
      setSource(null);
      setSidebarOpen(false);
      setOpening(true);
      try {
        await chat.open(id);
        history.replaceState(null, "", `#${id}`);
      } catch {
        // e.g. deleted on the server: forget it here too
        setConversations((list) => list.filter((c) => c.id !== id));
        history.replaceState(null, "", location.pathname);
        setNotice("That conversation no longer exists.");
      } finally {
        setOpening(false);
      }
    },
    [chat.open],
  );

  // The URL holds the open conversation (#id), so a reload restores it.
  useEffect(() => {
    const id = location.hash.slice(1);
    if (id) void openConversation(id);
  }, []); // once, on first load

  function send(text: string) {
    setNotice(null);
    void chat.send(text, (id) => {
      setConversations((list) =>
        upsertConversation(list, { id, title: list.find((c) => c.id === id)?.title ?? text.slice(0, 80), updatedAt: Date.now() }),
      );
      history.replaceState(null, "", `#${id}`);
    });
  }

  function newChat() {
    chat.reset();
    setSource(null);
    setSidebarOpen(false);
    history.replaceState(null, "", location.pathname);
  }

  async function deleteConversation(id: string) {
    const title = conversations.find((c) => c.id === id)?.title ?? "this conversation";
    if (!window.confirm(`Delete "${title}"?`)) return;
    await api.deleteConversation(id).catch(() => undefined); // already gone is fine
    setConversations((list) => list.filter((c) => c.id !== id));
    if (id === chat.conversationId) newChat();
  }

  return (
    <div className={`app ${source ? "with-source" : ""}`}>
      <Sidebar
        conversations={conversations}
        currentId={chat.conversationId}
        health={health}
        healthError={healthError}
        open={sidebarOpen}
        onNew={newChat}
        onOpen={(id) => void openConversation(id)}
        onDelete={(id) => void deleteConversation(id)}
        onDocuments={() => setShowDocuments(true)}
        onClose={() => setSidebarOpen(false)}
      />
      <main className="main">
        <header className="topbar">
          <button className="icon-button menu" onClick={() => setSidebarOpen(true)} aria-label="Open menu">
            ☰
          </button>
          <span className="topbar-title">{conversations.find((c) => c.id === chat.conversationId)?.title ?? "New chat"}</span>
        </header>
        {notice && <div className="notice">{notice}</div>}
        <ChatView messages={chat.messages} busy={chat.busy} loading={opening} onSend={send} onStop={chat.stop} onCite={setSource} />
      </main>
      {source && <SourcePanel citation={source} onClose={() => setSource(null)} />}
      {showDocuments && <DocumentsPanel onClose={() => setShowDocuments(false)} onChanged={refreshHealth} />}
    </div>
  );
}
