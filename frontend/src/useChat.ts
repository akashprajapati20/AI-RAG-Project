import { useCallback, useRef, useState } from "react";
import { api, streamChat } from "./api";
import type { Message } from "./types";

/** State and actions for the open conversation: send (streaming), stop, open, reset. */
export function useChat() {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [busy, setBusy] = useState(false);
  // The in-flight request. Opening another conversation clears it, which also tells the old
  // request's callbacks to stop touching the (now different) message list.
  const inflight = useRef<AbortController | null>(null);

  const patchLast = useCallback((patch: (m: Message) => Partial<Message>) => {
    setMessages((list) => {
      if (!list.length) return list;
      const last = list[list.length - 1];
      return [...list.slice(0, -1), { ...last, ...patch(last) }];
    });
  }, []);

  const send = useCallback(
    async (text: string, onConversation: (id: string) => void) => {
      inflight.current?.abort();
      const controller = new AbortController();
      inflight.current = controller;
      const patch = (fn: (m: Message) => Partial<Message>) => {
        if (inflight.current === controller) patchLast(fn);
      };
      const started = performance.now();
      const elapsed = () => performance.now() - started;
      let finished = false;

      setMessages((list) => [...list, newMessage("user", text, "done"), newMessage("assistant", "", "streaming")]);
      setBusy(true);
      try {
        await streamChat(
          text,
          conversationId,
          {
            onMeta: (id) => {
              setConversationId(id);
              onConversation(id);
            },
            onStep: (step) => patch((m) => ({ steps: [...m.steps, step] })),
            onToken: (token) => patch((m) => ({ content: m.content + token })),
            onAnswer: (result) => {
              finished = true;
              // The final answer replaces the streamed text (which can include text the model
              // wrote before deciding to call a tool).
              patch(() => ({ content: result.answer, citations: result.citations, status: "done", durationMs: elapsed() }));
            },
            onError: (message) => {
              finished = true;
              patch(() => ({ status: "error", error: message, durationMs: elapsed() }));
            },
          },
          controller.signal,
        );
        if (!finished) patch(() => ({ status: "error", error: "The connection closed before the answer arrived." }));
      } catch (e) {
        if (controller.signal.aborted) {
          patch((m) => ({ status: "done", content: m.content || "_Stopped._", durationMs: elapsed() }));
        } else {
          patch(() => ({ status: "error", error: `Couldn't reach the assistant: ${(e as Error).message}` }));
        }
      } finally {
        if (inflight.current === controller) {
          inflight.current = null;
          setBusy(false);
        }
      }
    },
    [conversationId, patchLast],
  );

  const stop = useCallback(() => inflight.current?.abort(), []);

  const cancelInflight = () => {
    const controller = inflight.current;
    inflight.current = null;
    controller?.abort();
    setBusy(false);
  };

  const open = useCallback(async (id: string) => {
    cancelInflight();
    const conversation = await api.conversation(id);
    setConversationId(id);
    setMessages(conversation.messages.map((m) => ({ ...newMessage(m.role, m.content, "done"), citations: m.citations })));
  }, []);

  const reset = useCallback(() => {
    cancelInflight();
    setConversationId(null);
    setMessages([]);
  }, []);

  return { conversationId, messages, busy, send, stop, open, reset };
}

function newMessage(role: Message["role"], content: string, status: Message["status"]): Message {
  return { id: crypto.randomUUID(), role, content, citations: [], steps: [], status };
}
