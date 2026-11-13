// A problem statement may arrive with bare LaTeX ("Compute \int_0^5 v(t)\,dt and write ...") and no $ signs.
// When there is no $ at all, wrap each run of LaTeX-looking words so it renders as math. Plain words stay plain.

const LOOKS_LIKE_LATEX = /[\\^_]/;

function braceDelta(word: string): number {
  return (word.match(/\{/g) ?? []).length - (word.match(/\}/g) ?? []).length;
}

export function wrapBareLatex(text: string): string {
  if (text.includes("$")) return text;
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
    } else if (!isSpace && LOOKS_LIKE_LATEX.test(word)) {
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
  return next !== undefined && LOOKS_LIKE_LATEX.test(next);
}
