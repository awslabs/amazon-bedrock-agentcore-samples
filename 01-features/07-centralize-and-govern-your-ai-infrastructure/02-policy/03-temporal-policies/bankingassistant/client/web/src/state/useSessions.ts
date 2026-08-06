import { useCallback, useEffect, useState } from "react";

import { api } from "../api/client";
import type {
  AppConfigDTO,
  ChatMessage,
  ProtocolVersion,
  SessionDTO,
  SessionSummary,
} from "../types";

export interface UseSessions {
  config: AppConfigDTO | null;
  sessions: SessionSummary[];
  activeId: string | null;
  activeSession: SessionDTO | null;
  sending: boolean;
  error: string | null;
  notice: string | null;
  selectSession: (id: string) => Promise<void>;
  createSession: (protocol: ProtocolVersion, policySessionId?: string) => Promise<void>;
  sendMessage: (text: string) => Promise<void>;
  clearError: () => void;
  clearNotice: () => void;
}

export function useSessions(): UseSessions {
  const [config, setConfig] = useState<AppConfigDTO | null>(null);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [activeSession, setActiveSession] = useState<SessionDTO | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const summarize = (s: SessionDTO): SessionSummary => ({
    id: s.id,
    label: s.label,
    protocol: s.protocol,
    mcpSessionId: s.mcpSessionId,
    policySessionId: s.policySessionId,
    policySessionSource: s.policySessionSource,
  });

  const upsertSummary = useCallback((s: SessionDTO) => {
    setSessions((prev) => {
      const next = prev.filter((p) => p.id !== s.id);
      return [summarize(s), ...next];
    });
  }, []);

  useEffect(() => {
    api.getConfig().then(setConfig).catch((e) => setError(String(e.message || e)));
    api.listSessions().then(setSessions).catch((e) => setError(String(e.message || e)));
  }, []);

  const selectSession = useCallback(async (id: string) => {
    setError(null);
    setActiveId(id);
    try {
      const s = await api.getSession(id);
      setActiveSession(s);
      upsertSummary(s);
    } catch (e) {
      // Sessions live in the server's memory; if it restarted, the session is
      // gone. Drop it from the sidebar with a soft note instead of a hard error.
      const msg = String((e as Error).message || e);
      if (/not found/i.test(msg)) {
        setSessions((prev) => prev.filter((p) => p.id !== id));
        if (activeId === id) {
          setActiveId(null);
          setActiveSession(null);
        }
        setNotice("That session is no longer available (the server restarted). Start a new one.");
      } else {
        setError(msg);
      }
    }
  }, [upsertSummary, activeId]);

  const createSession = useCallback(
    async (protocol: ProtocolVersion, policySessionId?: string) => {
      setError(null);
      try {
        const s = await api.createSession(protocol, policySessionId);
        upsertSummary(s);
        setActiveId(s.id);
        setActiveSession(s);
      } catch (e) {
        setError(String((e as Error).message || e));
      }
    },
    [upsertSummary],
  );

  const sendMessage = useCallback(async (text: string) => {
    if (!activeId) return;
    const id = activeId;
    setSending(true);
    setError(null);

    // Optimistically add the user turn and a placeholder assistant turn that
    // fills in as the stream arrives.
    const now = Date.now();
    setActiveSession((prev) =>
      prev && prev.id === id
        ? {
            ...prev,
            messages: [
              ...prev.messages,
              { role: "user", content: text, ts: now },
              { role: "assistant", content: "", toolEvents: [], ts: now + 1 },
            ],
          }
        : prev,
    );

    // Mutate the trailing assistant message as events stream in.
    const patchAssistant = (fn: (m: ChatMessage) => ChatMessage) => {
      setActiveSession((prev) => {
        if (!prev || prev.id !== id) return prev;
        const msgs = prev.messages.slice();
        const last = msgs[msgs.length - 1];
        if (last?.role === "assistant") msgs[msgs.length - 1] = fn(last);
        return { ...prev, messages: msgs };
      });
    };

    try {
      await api.sendMessageStream(id, text, (ev) => {
        if (ev.type === "text") {
          patchAssistant((m) => ({ ...m, content: m.content + ev.delta }));
        } else if (ev.type === "tool") {
          patchAssistant((m) => ({
            ...m,
            toolEvents: [...(m.toolEvents ?? []), ev.event],
          }));
        } else if (ev.type === "ids") {
          setActiveSession((prev) =>
            prev && prev.id === id
              ? { ...prev, mcpSessionId: ev.mcpSessionId, policySessionId: ev.policySessionId }
              : prev,
          );
        } else if (ev.type === "done") {
          setActiveSession(ev.session);
          upsertSummary(ev.session);
        } else if (ev.type === "error") {
          setError(ev.hint ? `${ev.error} — ${ev.hint}` : ev.error);
        }
      });
    } catch (e) {
      setError(String((e as Error).message || e));
    } finally {
      setSending(false);
    }
  }, [activeId, upsertSummary]);

  return {
    config,
    sessions,
    activeId,
    activeSession,
    sending,
    error,
    notice,
    selectSession,
    createSession,
    sendMessage,
    clearError: () => setError(null),
    clearNotice: () => setNotice(null),
  };
}
