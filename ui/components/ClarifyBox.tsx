"use client";

import { useEffect, useId, useRef, useState } from "react";
import { ApiError, clarifyText } from "@/lib/api";
import { getSpeechRecognition, transcriptOf, type SpeechRecognitionLike } from "@/lib/speech";
import type { ClarifyField, Mode } from "@/lib/types";
import { Tex } from "./Tex";

export const CLARIFY_MAX_CHARS = 400;
const SPEECH_LANG = "en-US";
const VOICE_NOTE =
  "Voice uses your browser's speech recognition, which may send audio to your browser's vendor. Typing works without it.";
const VOICE_FALLBACK = "Voice input stopped. Type it instead.";
const VOICE_ERRORS: Record<string, string> = {
  "no-speech": "Echo heard no speech. Try again, or type it.",
  "not-allowed": "Microphone access was blocked. Type it instead.",
  network: "Your browser's speech service could not be reached. Type it instead.",
};
const CLARIFY_FALLBACK = "Echo could not reach the clarify step. Try again.";

interface Proposal {
  field: ClarifyField;
  latex: string;
  notes: string;
}

interface Props {
  mode: Mode;
  busy: boolean;
  onUse: (field: ClarifyField, latex: string) => void;
}

function clarifyErrorText(error: unknown): string {
  return error instanceof ApiError ? error.message : CLARIFY_FALLBACK;
}

// The server refuses control characters, and a line break is one, so line breaks become spaces.
function oneLine(text: string): string {
  return text.replace(/[\r\n]+/g, " ").trim();
}

export function ClarifyBox({ mode, busy, onUse }: Props) {
  const id = useId();
  const [field, setField] = useState<ClarifyField>("problem");
  const [text, setText] = useState("");
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [voiceSupported, setVoiceSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);

  // Checked after mount, so the server-rendered page and the first client render agree.
  useEffect(() => {
    setVoiceSupported(getSpeechRecognition() !== null);
    return () => recognitionRef.current?.abort();
  }, []);

  function startListening() {
    const Recognizer = getSpeechRecognition();
    if (!Recognizer) return;
    const recognition = new Recognizer();
    const spoken = text.trim() ? `${text.trim()} ` : "";
    recognition.lang = SPEECH_LANG;
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.onresult = (event) => setText(`${spoken}${transcriptOf(event)}`.slice(0, CLARIFY_MAX_CHARS));
    recognition.onerror = (event) => setVoiceError(VOICE_ERRORS[event.error] ?? VOICE_FALLBACK);
    recognition.onend = () => {
      recognitionRef.current = null;
      setListening(false);
    };
    recognitionRef.current = recognition;
    setVoiceError(null);
    setListening(true);
    try {
      recognition.start();
    } catch {
      recognitionRef.current = null;
      setListening(false);
      setVoiceError(VOICE_FALLBACK);
    }
  }

  function stopListening() {
    recognitionRef.current?.stop();
  }

  async function askEcho() {
    if (listening) stopListening();
    const cleaned = oneLine(text);
    if (!cleaned) return;
    setPending(true);
    setError(null);
    setProposal(null);
    try {
      const response = await clarifyText(field, cleaned, mode);
      if (response.status === "error") {
        setError(response.error);
        return;
      }
      setProposal({ field, latex: response.latex, notes: response.notes });
    } catch (caught) {
      setError(clarifyErrorText(caught));
    } finally {
      setPending(false);
    }
  }

  function cancel() {
    setProposal(null);
    setError(null);
  }

  const textareaId = `${id}-text`;
  const counterId = `${id}-count`;
  const voiceNoteId = `${id}-voice`;
  const fieldName = `${id}-field`;
  const canAsk = text.trim().length > 0 && !pending && !busy;

  return (
    <div className="clarify">
      <p className="clarify-lede">
        Tell Echo what this part asks, or what you wrote. Echo shows its reading, and the mark changes only after you
        confirm it.
      </p>
      <fieldset>
        <legend>What are you describing?</legend>
        <label>
          <input
            type="radio"
            name={fieldName}
            value="problem"
            checked={field === "problem"}
            onChange={() => setField("problem")}
          />
          This is the problem
        </label>
        <label>
          <input
            type="radio"
            name={fieldName}
            value="answer"
            checked={field === "answer"}
            onChange={() => setField("answer")}
          />
          This is my answer
        </label>
      </fieldset>
      <label htmlFor={textareaId}>Type or say it in words or math</label>
      <textarea
        id={textareaId}
        value={text}
        maxLength={CLARIFY_MAX_CHARS}
        rows={3}
        aria-describedby={counterId}
        onChange={(event) => setText(event.target.value)}
      />
      <p id={counterId} className="clarify-count">
        {text.length} of {CLARIFY_MAX_CHARS} characters
      </p>
      <div className="clarify-actions">
        {voiceSupported && (
          <button
            type="button"
            className="quiet"
            aria-describedby={voiceNoteId}
            onClick={listening ? stopListening : startListening}
          >
            {listening ? "Stop listening" : "Speak"}
          </button>
        )}
        <button type="button" className="primary" onClick={() => void askEcho()} disabled={!canAsk}>
          {pending ? "Reading…" : "Show Echo's reading"}
        </button>
      </div>
      {voiceSupported && (
        <p id={voiceNoteId} className="voice-note">
          {VOICE_NOTE}
        </p>
      )}
      {voiceError && (
        <p className="error" role="alert">
          {voiceError}
        </p>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {proposal && (
        <div className="clarify-result">
          <p>
            <strong>Echo understood:</strong> <Tex latex={proposal.latex} />
          </p>
          {proposal.notes && <p className="clarify-notes">{proposal.notes}</p>}
          <div className="clarify-actions">
            <button
              type="button"
              className="primary"
              onClick={() => onUse(proposal.field, proposal.latex)}
              disabled={busy}
            >
              {busy ? "Grading…" : "Use this"}
            </button>
            <button type="button" className="quiet" onClick={cancel} disabled={busy}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
