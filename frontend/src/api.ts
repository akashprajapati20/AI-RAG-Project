import { SSEParser } from "./sse";
import type { ChatResult, DocumentInfo, Health, ServerMessage, Step, UploadResult } from "./types";

const API_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init);
  if (!response.ok) throw new Error(await errorMessage(response));
  return (response.status === 204 ? undefined : await response.json()) as T;
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    return typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
  } catch {
    return `${response.status} ${response.statusText}`;
  }
}

export const api = {
  health: () => request<Health>("/health"),
  conversation: (id: string) =>
    request<{ conversation_id: string; messages: ServerMessage[] }>(`/conversations/${encodeURIComponent(id)}`),
  deleteConversation: (id: string) => request<void>(`/conversations/${encodeURIComponent(id)}`, { method: "DELETE" }),
  documents: () => request<DocumentInfo[]>("/documents"),
  upload: (files: File[]) => {
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    return request<UploadResult[]>("/documents", { method: "POST", body: form });
  },
  deleteDocument: (id: number) => request<void>(`/documents/${id}`, { method: "DELETE" }),
};

export interface StreamHandlers {
  onMeta: (conversationId: string) => void;
  onStep: (step: Step) => void;
  onToken: (text: string) => void;
  onAnswer: (result: ChatResult) => void;
  onError: (message: string) => void;
}

/** POST /chat/stream and dispatch its Server-Sent Events until the stream ends. */
export async function streamChat(
  message: string,
  conversationId: string | null,
  handlers: StreamHandlers,
  signal: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_URL}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_id: conversationId }),
    signal,
  });
  if (!response.ok || !response.body) throw new Error(await errorMessage(response));

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  const parser = new SSEParser();
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    for (const { event, data } of parser.push(value)) {
      const payload = JSON.parse(data);
      if (event === "meta") handlers.onMeta(payload.conversation_id);
      else if (event === "step") handlers.onStep(payload);
      else if (event === "token") handlers.onToken(payload.text);
      else if (event === "answer") handlers.onAnswer(payload);
      else if (event === "error") handlers.onError(payload.message);
    }
  }
}
