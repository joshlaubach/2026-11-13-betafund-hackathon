// Turns a tutor reply into plain blocks. Pure text in, text out: nothing here produces HTML.
// Inline **bold** and math stay in the text; the component renders them.

export type TutorBlock =
  | { kind: "p"; text: string }
  | { kind: "ol"; items: string[] }
  | { kind: "ul"; items: string[] };

const ORDERED_ITEM = /^\d+\.\s+(.*)$/;
const BULLET_ITEM = /^-\s+(.*)$/;

// Blank lines split paragraphs and end lists. Consecutive "1. " or "- " lines form one list.
// A plain line right after a paragraph or list item continues it.
export function parseTutorMarkdown(text: string): TutorBlock[] {
  return parseLines(text).flatMap((block) => (block.kind === "p" ? splitInlineSteps(block.text) : [block]));
}

// "Step 1: ... Step 2: ..." written inside one paragraph becomes a numbered list, one step per line.
const STEP_MARKER = /\bStep\s+\d+\s*[:.]\s*/g;
const MIN_INLINE_STEPS = 2;

function splitInlineSteps(text: string): TutorBlock[] {
  const markers = [...text.matchAll(STEP_MARKER)];
  if (markers.length < MIN_INLINE_STEPS || insideMath(text, markers[0].index ?? 0)) return [{ kind: "p", text }];
  const blocks: TutorBlock[] = [];
  const lead = text.slice(0, markers[0].index).trim();
  if (lead) blocks.push({ kind: "p", text: lead });
  const items = markers.map((marker, index) => {
    const start = (marker.index ?? 0) + marker[0].length;
    const end = index + 1 < markers.length ? markers[index + 1].index : text.length;
    return text.slice(start, end).trim();
  });
  // The last step ends at its first sentence break outside math; anything after it is a new paragraph.
  const last = items[items.length - 1];
  const cut = sentenceEnd(last);
  const tail = cut === -1 ? "" : last.slice(cut).trim();
  items[items.length - 1] = cut === -1 ? last : last.slice(0, cut).trim();
  blocks.push({ kind: "ol", items });
  if (tail) blocks.push({ kind: "p", text: tail });
  return blocks;
}

// True when position sits inside a $...$ span.
function insideMath(text: string, position: number): boolean {
  return ((text.slice(0, position).match(/\$/g) ?? []).length % 2) === 1;
}

// Index just past the first ". " followed by a capital letter, outside math; -1 when there is none.
function sentenceEnd(text: string): number {
  let inMath = false;
  for (let index = 0; index < text.length - 2; index += 1) {
    if (text[index] === "$") inMath = !inMath;
    if (!inMath && text[index] === "." && text[index + 1] === " " && /[A-Z]/.test(text[index + 2])) return index + 1;
  }
  return -1;
}

function parseLines(text: string): TutorBlock[] {
  const blocks: TutorBlock[] = [];
  let open = false;
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (line === "") {
      open = false;
      continue;
    }
    const ordered = ORDERED_ITEM.exec(line);
    const bullet = BULLET_ITEM.exec(line);
    if (ordered) addListItem(blocks, open, "ol", ordered[1]);
    else if (bullet) addListItem(blocks, open, "ul", bullet[1]);
    else addText(blocks, open, line);
    open = true;
  }
  return blocks;
}

function addListItem(blocks: TutorBlock[], open: boolean, kind: "ol" | "ul", item: string): void {
  const last = blocks[blocks.length - 1];
  if (open && last && last.kind === kind) {
    blocks[blocks.length - 1] = { kind, items: [...last.items, item] };
    return;
  }
  blocks.push({ kind, items: [item] });
}

function addText(blocks: TutorBlock[], open: boolean, line: string): void {
  const last = blocks[blocks.length - 1];
  if (open && last && last.kind === "p") {
    blocks[blocks.length - 1] = { kind: "p", text: `${last.text} ${line}` };
    return;
  }
  if (open && last && last.kind !== "p") {
    const items = last.items;
    const tail = `${items[items.length - 1]} ${line}`;
    blocks[blocks.length - 1] = { kind: last.kind, items: [...items.slice(0, -1), tail] };
    return;
  }
  blocks.push({ kind: "p", text: line });
}
