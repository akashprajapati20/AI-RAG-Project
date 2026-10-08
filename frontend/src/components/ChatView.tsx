import { useEffect, useRef, useState } from "react";
import type { Citation, Message } from "../types";
import { Answer, Sources } from "./Answer";
import { Steps } from "./Steps";

const EXAMPLES = [
  "How many PTO days can I carry over into next year?",
  "What does it mean when a tag's LED blinks amber?",
  "What would 12 sites on the Growth plan cost per year with the volume discount?",
  "What caused the March outage, and who owns the follow-ups?",
];

export function ChatView({ messages, busy, loading, onSend, onStop, onCite }: {
  messages: Message[];
  busy: boolean;
  loading: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
  onCite: (citation: Citation) => void;
}) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  return (
    <div className="chat">
      <div className="thread">
        {messages.length === 0 && loading ? (
          <p className="loading">Loading conversation…</p>
        ) : messages.length === 0 ? (
          <EmptyState onPick={onSend} />
        ) : (
          messages.map((m) => <MessageView key={m.id} message={m} onCite={onCite} />)
        )}
        <div ref={end} />
      </div>
      <Composer busy={busy} onSend={onSend} onStop={onStop} />
    </div>
  );
}

function MessageView({ message, onCite }: { message: Message; onCite: (citation: Citation) => void }) {
  if (message.role === "user") {
    return (
      <div className="msg user">
        <div className="bubble">{message.content}</div>
      </div>
    );
  }
  const streaming = message.status === "streaming";
  return (
    <div className="msg assistant">
      {message.steps.length > 0 && <Steps steps={message.steps} running={streaming} durationMs={message.durationMs} />}
      {message.content && (
        <Answer text={message.content} citations={message.citations} streaming={streaming} onCite={onCite} />
      )}
      {!message.content && streaming && message.steps.length === 0 && <p className="thinking">Connecting…</p>}
      {message.status === "error" && <div className="error">{message.error}</div>}
      {message.citations.length > 0 && <Sources citations={message.citations} onCite={onCite} />}
    </div>
  );
}

function EmptyState({ onPick }: { onPick: (text: string) => void }) {
  return (
    <div className="empty">
      <h1>Ask Brindlewave's documents</h1>
      <p>
        Answers come only from the company's internal documents (handbook, pricing, hardware manual, API docs,
        incident reports and more) and cite the passages they rely on.
      </p>
      <div className="examples">
        {EXAMPLES.map((example) => (
          <button key={example} onClick={() => onPick(example)}>
            {example}
          </button>
        ))}
      </div>
    </div>
  );
}

function Composer({ busy, onSend, onStop }: { busy: boolean; onSend: (text: string) => void; onStop: () => void }) {
  const [text, setText] = useState("");
  const submit = () => {
    const question = text.trim();
    if (!question || busy) return;
    onSend(question);
    setText("");
  };

  return (
    <form
      className="composer"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          // Enter sends, Shift+Enter adds a line; ignore Enter while an IME is composing text.
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            submit();
          }
        }}
        placeholder="Ask about Brindlewave's documents…"
        aria-label="Message"
        rows={1}
        maxLength={4000}
        autoFocus
      />
      {busy ? (
        <button type="button" className="stop" onClick={onStop}>
          Stop
        </button>
      ) : (
        <button type="submit" disabled={!text.trim()}>
          Send
        </button>
      )}
    </form>
  );
}
