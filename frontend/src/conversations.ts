import type { ConversationSummary } from "./types";

// The server stores each conversation's messages; the browser only remembers which conversations
// exist (id + title), so the sidebar can list them. Storage can be unavailable (private windows),
// so failures fall back to an empty list.
const KEY = "brindlewave.conversations";

export function loadConversations(): ConversationSummary[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "[]");
  } catch {
    return [];
  }
}

export function saveConversations(conversations: ConversationSummary[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(conversations));
  } catch {
    // not persisted; the list still works for this session
  }
}

/** Add or update a conversation and keep the list sorted newest first. */
export function upsertConversation(list: ConversationSummary[], item: ConversationSummary): ConversationSummary[] {
  return [item, ...list.filter((c) => c.id !== item.id)].sort((a, b) => b.updatedAt - a.updatedAt);
}
