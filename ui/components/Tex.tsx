"use client";

import katex from "katex";
import { useMemo } from "react";

function render(latex: string, display: boolean): string {
  return katex.renderToString(latex, {
    throwOnError: false,
    displayMode: display,
    output: "html",
    strict: "ignore",
    trust: false,
    maxSize: 10,
    maxExpand: 200,
  });
}

// Bare LaTeX, such as an answer key.
export function Tex({ latex, display = false }: { latex: string; display?: boolean }) {
  const html = useMemo(() => render(latex, display), [latex, display]);
  return <span dangerouslySetInnerHTML={{ __html: html }} />;
}

const MATH_SPLIT = /(\$\$[^$]+\$\$|\$[^$]+\$)/g;

// Text with $...$ segments, such as a problem statement. Plain text stays plain text.
export function MathText({ text }: { text: string }) {
  const parts = useMemo(() => text.split(MATH_SPLIT).filter((part) => part !== ""), [text]);
  return (
    <>
      {parts.map((part, index) => {
        if (part.startsWith("$$")) return <Tex key={index} latex={part.slice(2, -2)} display />;
        if (part.startsWith("$")) return <Tex key={index} latex={part.slice(1, -1)} />;
        return <span key={index}>{part}</span>;
      })}
    </>
  );
}
