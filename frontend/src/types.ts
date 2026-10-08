// Shapes returned by the API (see backend/app/api/schemas.py).

export interface Citation {
  n: number; // the number used in the answer, as in [n]
  title: string;
  source: string; // file, e.g. "data/corpus/pricing_and_plans_2026.pdf"
  citation: string; // e.g. "Tally Pricing and Plans 2026 › 4. SLA credits (p. 1)"
  content: string; // the passage itself
}

export interface Step {
  node: string; // router | retrieve | grade | rewrite | generate | respond | tools
  label: string; // human-readable summary, e.g. "Searched for '…': 6 results"
  route?: string;
  tool_calls?: { name: string; args: Record<string, unknown> }[];
}

export interface ChatResult {
  conversation_id: string;
  answer: string;
  citations: Citation[];
  route: string;
  queries: string[];
}

export interface ServerMessage {
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
}

export interface DocumentInfo {
  id: number;
  title: string;
  source: string;
  format: string | null;
  pages: number | null;
  chunks: number;
  ingested_at: string | null;
}

export interface UploadResult {
  filename: string;
  status: "added" | "updated" | "unchanged" | "failed";
  chunks: number;
  error: string | null;
}

export interface Health {
  status: string;
  documents: number;
  chunks: number;
  models: { chat: string; fast: string; embedding: string };
}

// UI-side shapes.

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  steps: Step[]; // only for answers produced in this browser session
  status: "streaming" | "done" | "error";
  error?: string;
  durationMs?: number;
}

export interface ConversationSummary {
  id: string;
  title: string;
  updatedAt: number;
}
