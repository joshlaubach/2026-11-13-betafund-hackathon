"use client";

import "../app/tutor.css";
import { motion, useReducedMotion } from "motion/react";
import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { ApiError } from "@/lib/api";
import { motionTokens, springs } from "@/lib/motion-tokens";
import { sendTutorMessage } from "@/lib/tutor-api";
import { parseTutorMarkdown, type TutorBlock } from "@/lib/tutor-markdown";
import type {
  TutorAction,
  TutorContext,
  TutorMessage,
  TutorOkResponse,
  TutorRole,
  TutorSource,
  TutorTurn,
} from "@/lib/tutor-types";
import type { Mode } from "@/lib/types";
import { useIsDesktop } from "@/lib/use-desktop";
import { Presence, Reveal, StaggerItem } from "./Motion";
import { MathText } from "./Tex";

export type TutorPanelProps = {
  open: boolean;
  onClose: () => void;
  mode: Mode;
  context: TutorContext | null;
  onAction: (action: TutorAction) => void;
  // When nonce changes while open, text is sent as a student message.
  prompt?: { text: string; nonce: number };
  // Shown under the title, e.g. "About: Chain rule, problem 2".
  contextLabel?: string;
  // "docked" sits in a parent column (SplitWorkspace). "overlay" is the old fixed drawer, kept for now.
  layout?: "docked" | "overlay";
  // Called when "/" is pressed outside a text field while the tutor is closed.
  onRequestOpen?: () => void;
};

interface Chip {
  key: string;
  label: string;
  run: () => void;
}

const TUTOR_MAX_CHARS = 500;
const TUTOR_INPUT_MAX_LINES = 6;
const CONTROL_CHARS = /[\u0000-\u001f\u007f]/g;
const LINE_BREAKS = /\s*[\r\n]+\s*/g;
const BOLD_SPLIT = /\*\*([^*]+)\*\*/;
const DOT_INDEXES = [0, 1, 2];
const FALLBACK_ERROR = "The tutor could not be reached. Try again.";
const EXPLAIN_PROMPT = "Explain the idea behind this problem.";
const WORKED_PROMPT = "Show me a worked example.";
const TOPIC_PROMPT = "Explain the main idea of this topic.";
const INPUT_HINT = "Enter to send, Shift+Enter for a new line";
const SCRIPTED_PROVENANCE = "Offline tutor: a worked example from Echo's problem bank (bank confirmed), no AI";
const GROUNDED_PROVENANCE = "AI tutor reply, citing an example from Echo's problem bank. Not checked by Echo.";
const UNGROUNDED_PROVENANCE = "AI tutor reply. Not checked by Echo.";
const HINT_ACTION: TutorAction = { id: "show_hint", label: "Give me a hint", params: {} };

function toTurns(messages: TutorMessage[]): TutorTurn[] {
  return messages.map(({ role, text }) => ({ role, text }));
}

function latestTutorResponse(messages: TutorMessage[]): TutorOkResponse | undefined {
  return [...messages].reverse().find((message) => message.role === "tutor")?.response;
}

function provenanceLine(response: TutorOkResponse): string {
  if (response.engine === "scripted") return SCRIPTED_PROVENANCE;
  return response.grounded ? GROUNDED_PROVENANCE : UNGROUNDED_PROVENANCE;
}

// Line breaks become spaces (the backend rejects control characters), then the text is trimmed and capped.
function normalizeStudentText(raw: string): string {
  return raw.replace(LINE_BREAKS, " ").replace(CONTROL_CHARS, "").trim().slice(0, TUTOR_MAX_CHARS);
}

function isTextEntryTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

// Grows the input to fit its text, up to a fixed number of lines, then scrolls.
function fitInputHeight(element: HTMLTextAreaElement | null): void {
  if (!element) return;
  element.style.height = "auto";
  const style = getComputedStyle(element);
  const lineHeight = Number.parseFloat(style.lineHeight) || 0;
  const chrome =
    Number.parseFloat(style.paddingTop) +
    Number.parseFloat(style.paddingBottom) +
    Number.parseFloat(style.borderTopWidth) +
    Number.parseFloat(style.borderBottomWidth);
  const maxHeight = lineHeight * TUTOR_INPUT_MAX_LINES + chrome;
  const wanted = element.scrollHeight + (element.offsetHeight - element.clientHeight);
  element.style.height = `${Math.min(wanted, maxHeight)}px`;
  element.style.overflowY = wanted > maxHeight ? "auto" : "hidden";
}

// **bold** becomes <strong>; every other run goes through MathText. Nothing is injected as HTML.
function TutorInline({ text }: { text: string }) {
  const parts = text.split(BOLD_SPLIT);
  return (
    <>
      {parts.map((part, index) =>
        index % 2 === 1 ? (
          <strong key={index}>
            <MathText text={part} />
          </strong>
        ) : (
          <MathText key={index} text={part} />
        ),
      )}
    </>
  );
}

function TutorBlocks({ blocks }: { blocks: TutorBlock[] }) {
  return (
    <>
      {blocks.map((block, index) => {
        if (block.kind === "p") {
          return (
            <p key={index}>
              <TutorInline text={block.text} />
            </p>
          );
        }
        const items = block.items.map((item, itemIndex) => (
          <li key={itemIndex}>
            <TutorInline text={item} />
          </li>
        ));
        return block.kind === "ol" ? <ol key={index}>{items}</ol> : <ul key={index}>{items}</ul>;
      })}
    </>
  );
}

function SourceList({ sources }: { sources: TutorSource[] }) {
  return (
    <details className="tutor-sources">
      <summary>Sources ({sources.length})</summary>
      <ul>
        {sources.map((source, index) => (
          <li key={`${index}-${source.problem_id}`}>
            <code>{source.problem_id}</code>: <MathText text={source.statement} />{" "}
            <span className="tutor-topic">{source.topic_title}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}

function TutorReply({ message }: { message: TutorMessage }) {
  const response = message.response;
  return (
    <div className="tutor-bubble">
      <TutorBlocks blocks={parseTutorMarkdown(message.text)} />
      {response && <p className="tutor-provenance">{provenanceLine(response)}</p>}
      {response && response.sources.length > 0 && <SourceList sources={response.sources} />}
    </div>
  );
}

function TypingDots({ reduceMotion }: { reduceMotion: boolean }) {
  return (
    <div className="tutor-typing" role="status" aria-label="Tutor is replying">
      {DOT_INDEXES.map((index) => (
        <motion.span
          key={index}
          className="tutor-dot"
          aria-hidden="true"
          animate={reduceMotion ? undefined : { opacity: [0.25, 1, 0.25] }}
          transition={{
            duration: motionTokens.duration.slow,
            repeat: Infinity,
            delay: index * motionTokens.stagger.chips,
            ease: motionTokens.easing.sharp,
          }}
        />
      ))}
    </div>
  );
}

// Overlay only: the drawer slides in from the right on desktop and up from the bottom on small screens.
function overlayMotion(open: boolean, reduceMotion: boolean, isDesktop: boolean) {
  if (reduceMotion) return { x: 0, y: 0, opacity: open ? 1 : 0 };
  if (open) return { x: 0, y: 0, opacity: 1 };
  return isDesktop ? { x: "100%", y: 0, opacity: 1 } : { x: 0, y: "100%", opacity: 1 };
}

export function TutorPanel({
  open,
  onClose,
  mode,
  context,
  onAction,
  prompt,
  contextLabel,
  layout = "overlay",
  onRequestOpen,
}: TutorPanelProps) {
  const isOverlay = layout === "overlay";
  const titleId = useId();
  const inputId = useId();
  const hintId = useId();
  const panelRef = useRef<HTMLElement>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const nextIdRef = useRef(0);
  const handledNonceRef = useRef<number | null>(null);
  const [messages, setMessages] = useState<TutorMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const reduceMotion = Boolean(useReducedMotion());
  const isDesktop = useIsDesktop();

  function appendMessage(role: TutorRole, text: string, response?: TutorOkResponse): void {
    const id = nextIdRef.current;
    nextIdRef.current += 1;
    setMessages((current) => [...current, { id, role, text, response }]);
  }

  async function requestReply(message: string, prior: TutorTurn[]): Promise<void> {
    setPending(true);
    setError(null);
    try {
      const response = await sendTutorMessage(message, prior, context, mode);
      if (response.status === "error") {
        setError(response.error);
        return;
      }
      appendMessage("tutor", response.reply, response);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : FALLBACK_ERROR);
    } finally {
      setPending(false);
    }
  }

  // Returns false when the text was not sent (empty, or a reply is still pending).
  function sendStudent(raw: string): boolean {
    const text = normalizeStudentText(raw);
    if (!text || pending) return false;
    const prior = toTurns(messages);
    appendMessage("student", text);
    void requestReply(text, prior);
    return true;
  }

  // Resends the last student message. That message is already in the log, so it is not added again.
  function retry(): void {
    const last = messages[messages.length - 1];
    if (!last || last.role !== "student" || pending) return;
    void requestReply(last.text, toTurns(messages.slice(0, -1)));
  }

  function runAction(action: TutorAction): void {
    if (action.id === "explain_concept") {
      sendStudent(EXPLAIN_PROMPT);
      return;
    }
    if (action.id === "worked_example") {
      sendStudent(WORKED_PROMPT);
      return;
    }
    onAction(action);
  }

  function handleInputKey(event: KeyboardEvent<HTMLTextAreaElement>): void {
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) return;
    event.preventDefault();
    if (sendStudent(draft)) setDraft("");
  }

  function handleSubmit(): void {
    if (sendStudent(draft)) setDraft("");
  }

  // Effects read the latest sender through a ref, so they do not re-run on every render.
  const sendRef = useRef(sendStudent);
  useEffect(() => {
    sendRef.current = sendStudent;
  });

  const promptText = prompt?.text;
  const promptNonce = prompt?.nonce;
  useEffect(() => {
    if (promptText === undefined || promptNonce === undefined) return;
    if (handledNonceRef.current === promptNonce) return;
    handledNonceRef.current = promptNonce;
    if (open) sendRef.current(promptText);
  }, [open, promptText, promptNonce]);

  // Overlay only: a closed drawer stays mounted but inert. The docked panel is hidden by its parent instead.
  useEffect(() => {
    if (isOverlay) panelRef.current?.toggleAttribute("inert", !open);
    if (!open) return;
    // Wait two frames: the parent clears `inert` and makes the docked pane visible in its own effect, which runs
    // after this one, and focus on an inert or hidden element is silently ignored.
    let second = 0;
    const first = requestAnimationFrame(() => {
      second = requestAnimationFrame(() => inputRef.current?.focus({ preventScroll: true }));
    });
    return () => {
      cancelAnimationFrame(first);
      cancelAnimationFrame(second);
    };
  }, [open, isOverlay]);

  useEffect(() => {
    if (!open || !isOverlay) return;
    function handleKey(event: globalThis.KeyboardEvent): void {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, isOverlay, onClose]);

  // "/" focuses the input from anywhere on the page, opening the tutor first when it is closed.
  useEffect(() => {
    function handleSlash(event: globalThis.KeyboardEvent): void {
      if (event.key !== "/" || event.ctrlKey || event.metaKey || event.altKey) return;
      if (isTextEntryTarget(event.target)) return;
      event.preventDefault();
      if (open) inputRef.current?.focus({ preventScroll: true });
      else onRequestOpen?.();
    }
    document.addEventListener("keydown", handleSlash);
    return () => document.removeEventListener("keydown", handleSlash);
  }, [open, onRequestOpen]);

  useEffect(() => {
    const log = logRef.current;
    if (!log) return;
    log.scrollTo({ top: log.scrollHeight, behavior: reduceMotion ? "auto" : "smooth" });
  }, [messages.length, pending, error, reduceMotion]);

  useEffect(() => {
    fitInputHeight(inputRef.current);
  }, [draft]);

  function handlePanelKey(event: KeyboardEvent<HTMLElement>): void {
    if (event.key === "Escape" && isDesktop) onClose();
  }

  const latest = latestTutorResponse(messages);
  const chips: Chip[] = latest
    ? latest.actions.map((action) => ({ key: action.id, label: action.label, run: () => runAction(action) }))
    : [
        { key: "starter-explain", label: "Explain this topic", run: () => void sendStudent(TOPIC_PROMPT) },
        { key: "starter-hint", label: "Give me a hint", run: () => onAction(HINT_ACTION) },
        { key: "starter-example", label: "Show a worked example", run: () => void sendStudent(WORKED_PROMPT) },
      ];

  const canSend = draft.trim().length > 0 && !pending;
  const body = (
    <>
      <header className="tutor-head">
        <div className="tutor-heading">
          <h2 id={titleId} className="tutor-title">
            Echo tutor
          </h2>
          {contextLabel && <p className="tutor-context">{contextLabel}</p>}
        </div>
        <button type="button" className="quiet tutor-close" aria-label="Close tutor" onClick={onClose}>
          {"Close"}
        </button>
      </header>

      <div ref={logRef} role="log" aria-live="polite" aria-label="Tutor conversation" className="tutor-log">
        {messages.length === 0 && <p className="tutor-empty">Ask about this topic or problem.</p>}
        {messages.map((message) => (
          <Reveal key={message.id} className={`tutor-turn tutor-turn-${message.role}`}>
            {message.role === "student" ? (
              <p className="tutor-bubble">{message.text}</p>
            ) : (
              <TutorReply message={message} />
            )}
          </Reveal>
        ))}
        {pending && <TypingDots reduceMotion={reduceMotion} />}
        {error && (
          <div className="tutor-error" role="alert">
            <p>{error}</p>
            <button type="button" className="quiet" disabled={pending} onClick={retry}>
              Retry
            </button>
          </div>
        )}
      </div>

      <ul className="tutor-chips" aria-label="Suggested next steps">
        <Presence>
          {chips.map((chip, index) => (
            <StaggerItem key={chip.key} index={index} step={motionTokens.stagger.chips} className="tutor-chip-item">
              <button type="button" className="quiet tutor-chip" disabled={pending} onClick={chip.run}>
                {chip.label}
              </button>
            </StaggerItem>
          ))}
        </Presence>
      </ul>

      <form
        className="tutor-form"
        onSubmit={(event) => {
          event.preventDefault();
          handleSubmit();
        }}
      >
        <label htmlFor={inputId}>Ask the tutor</label>
        <textarea
          id={inputId}
          ref={inputRef}
          className="tutor-input"
          rows={1}
          value={draft}
          maxLength={TUTOR_MAX_CHARS}
          autoComplete="off"
          aria-describedby={hintId}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={handleInputKey}
        />
        <button type="submit" className="primary" disabled={!canSend}>
          Send
        </button>
        <p id={hintId} className="tutor-hint">
          {INPUT_HINT}
        </p>
      </form>
    </>
  );

  if (!isOverlay) {
    return (
      <section
        ref={panelRef}
        role="region"
        aria-label="Echo tutor"
        className="tutor-panel tutor-panel-docked"
        onKeyDown={handlePanelKey}
      >
        {body}
      </section>
    );
  }

  return (
    <motion.section
      ref={panelRef}
      role="dialog"
      aria-modal="false"
      aria-labelledby={titleId}
      aria-hidden={!open}
      className="tutor-panel tutor-panel-overlay"
      initial={false}
      animate={overlayMotion(open, reduceMotion, isDesktop)}
      transition={reduceMotion ? { duration: motionTokens.duration.fast } : springs.gentle}
    >
      {body}
    </motion.section>
  );
}
