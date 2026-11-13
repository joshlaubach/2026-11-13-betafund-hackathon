// A problem statement may arrive with bare LaTeX ("Compute \int_0^5 v(t)\,dt and write ...") and no $ signs.
// When there is no $ at all, wrap each run of LaTeX-looking words so it renders as math. Plain words stay plain.

const LOOKS_LIKE_LATEX = /[\\^_]/;
// Any math delimiter we accept: $, $$, \( or \[.
const HAS_DELIMITER = /\$|\\\(|\\\[/;

// One alternation, in priority order: $$..$$ (display), \[..\] (display), \(..\) (inline), $..$ (inline).
// Groups 1 and 2 are display math; groups 3 and 4 are inline math. Unclosed delimiters do not match.
const MATH_PATTERN = /\$\$([^$]+)\$\$|\\\[([\s\S]+?)\\\]|\\\(([\s\S]+?)\\\)|\$([^$]+)\$/g;

export type MathSegmentKind = "text" | "inline" | "display";

export interface MathSegment {
  kind: MathSegmentKind;
  value: string;
}

// Splits text into plain runs and LaTeX runs. Plain text never gets dropped or reordered.
export function splitMath(text: string): MathSegment[] {
  const segments: MathSegment[] = [];
  let last = 0;
  for (const match of text.matchAll(MATH_PATTERN)) {
    const start = match.index ?? 0;
    if (start > last) segments.push({ kind: "text", value: text.slice(last, start) });
    const isDisplay = match[1] !== undefined || match[2] !== undefined;
    const value = match[1] ?? match[2] ?? match[3] ?? match[4] ?? "";
    segments.push({ kind: isDisplay ? "display" : "inline", value });
    last = start + match[0].length;
  }
  if (last < text.length) segments.push({ kind: "text", value: text.slice(last) });
  return segments;
}

// A snake_case word such as bank_key or net_change is a name, not math. Real subscripts like x_1 or a_n have a
// one-letter base or a digit, so they still render.
const SNAKE_CASE_WORD = /^[("'[]?[A-Za-z]{2,}(?:_[A-Za-z]{2,})+[)"'\].,;:!?]*$/;

function looksLikeLatex(word: string): boolean {
  if (SNAKE_CASE_WORD.test(word)) return false;
  return LOOKS_LIKE_LATEX.test(word);
}

function braceDelta(word: string): number {
  return (word.match(/\{/g) ?? []).length - (word.match(/\}/g) ?? []).length;
}

export function wrapBareLatex(text: string): string {
  if (HAS_DELIMITER.test(text)) return text;
  const words = text.split(/(\s+)/);
  const out: string[] = [];
  let run: string[] = [];
  let depth = 0;
  const flush = (): void => {
    if (run.length > 0) out.push(`$${run.join("").trim()}$`);
    run = [];
    depth = 0;
  };
  for (let index = 0; index < words.length; index += 1) {
    const word = words[index];
    const isSpace = /^\s+$/.test(word);
    if (run.length > 0 && depth > 0) {
      // Inside an open brace group such as \lim_{x\to 0}: keep going until it closes.
      run.push(word);
      depth += braceDelta(word);
    } else if (!isSpace && looksLikeLatex(word)) {
      run.push(word);
      depth += braceDelta(word);
    } else if (isSpace && run.length > 0 && nextWordLooksLikeLatex(words, index)) {
      run.push(word);
    } else {
      flush();
      out.push(word);
    }
  }
  flush();
  return out.join("");
}

function nextWordLooksLikeLatex(words: string[], spaceIndex: number): boolean {
  const next = words[spaceIndex + 1];
  return next !== undefined && looksLikeLatex(next);
}
