// The browser's speech recognition, typed by hand because lib.dom does not declare it everywhere.
// Returns null when the browser has none, so the page can hide the microphone button.

export interface SpeechEvent {
  results: ArrayLike<ArrayLike<{ transcript: string }>>;
}

export interface SpeechErrorEvent {
  error: string;
}

export interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: SpeechEvent) => void) | null;
  onerror: ((event: SpeechErrorEvent) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

export type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

interface SpeechWindow {
  SpeechRecognition?: SpeechRecognitionConstructor;
  webkitSpeechRecognition?: SpeechRecognitionConstructor;
}

export function getSpeechRecognition(): SpeechRecognitionConstructor | null {
  if (typeof window === "undefined") return null;
  const scope = window as unknown as SpeechWindow;
  return scope.SpeechRecognition ?? scope.webkitSpeechRecognition ?? null;
}

// Every result so far, joined. Interim results are included, so the text grows while the student speaks.
export function transcriptOf(event: SpeechEvent): string {
  return Array.from(event.results, (result) => result[0]?.transcript ?? "").join("");
}
