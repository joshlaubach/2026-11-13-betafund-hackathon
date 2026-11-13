"use client";

import { useId, useState } from "react";
import { ApiError, askEcho } from "@/lib/api";
import type { AskRow, Mode } from "@/lib/types";
import { MathText } from "./Tex";

export const ASK_MAX_CHARS = 300;
const SUGGESTIONS = ["Why is this marked this way?", "What did I do wrong?", "How was this checked?"];
const ASK_FALLBACK = "Echo could not reach the explanation step. Try again.";
const REPLY_LABEL = "Echo's explanation (AI, not a mark)";

interface Props {
  row: AskRow;
  mode: Mode;
}

export function AskBox({ row, mode }: Props) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [reply, setReply] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  // One question at a time: a new question clears the old reply. No history is kept.
  async function ask(question: string) {
    const cleaned = question.trim();
    if (!cleaned || pending) return;
    setPending(true);
    setError(null);
    setReply(null);
    try {
      const response = await askEcho(cleaned, row, mode);
      if (response.status === "error") {
        setError(response.error);
        return;
      }
      setReply(response.answer);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : ASK_FALLBACK);
    } finally {
      setPending(false);
    }
  }

  const panelId = `${id}-panel`;
  const inputId = `${id}-input`;
  const canAsk = text.trim().length > 0 && !pending;

  if (!open) {
    return (
      <div className="ask">
        <button type="button" className="quiet" aria-expanded={false} onClick={() => setOpen(true)}>
          Ask Echo about this part
        </button>
      </div>
    );
  }

  return (
    <div className="ask">
      <button
        type="button"
        className="quiet"
        aria-expanded={true}
        aria-controls={panelId}
        onClick={() => setOpen(false)}
      >
        Ask Echo about this part
      </button>
      <div id={panelId} className="ask-panel">
        <div className="ask-chips">
          {SUGGESTIONS.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              className="quiet ask-chip"
              disabled={pending}
              onClick={() => void ask(suggestion)}
            >
              {suggestion}
            </button>
          ))}
        </div>
        <form
          className="ask-form"
          onSubmit={(event) => {
            event.preventDefault();
            void ask(text);
          }}
        >
          <label htmlFor={inputId}>Your question</label>
          <input
            id={inputId}
            type="text"
            value={text}
            maxLength={ASK_MAX_CHARS}
            onChange={(event) => setText(event.target.value)}
          />
          <button type="submit" className="primary" disabled={!canAsk}>
            {pending ? "Asking Echo…" : "Ask"}
          </button>
        </form>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <div className="ask-reply" aria-live="polite">
          {reply && (
            <>
              <p className="ask-label">{REPLY_LABEL}</p>
              <p>
                <MathText text={reply} />
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
