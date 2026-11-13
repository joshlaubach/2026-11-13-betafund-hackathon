"use client";

import katex from "katex";
import { useMemo } from "react";
import { splitMath, wrapBareLatex } from "@/lib/mathtext";

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

// Text with $...$, $$...$$, \(...\) or \[...\] segments, such as a problem statement. Plain text stays plain text.
export function MathText({ text }: { text: string }) {
  const segments = useMemo(() => splitMath(wrapBareLatex(text)), [text]);
  return (
    <>
      {segments.map((segment, index) => {
        if (segment.kind === "display") return <Tex key={index} latex={segment.value} display />;
        if (segment.kind === "inline") return <Tex key={index} latex={segment.value} />;
        return <span key={index}>{segment.value}</span>;
      })}
    </>
  );
}
