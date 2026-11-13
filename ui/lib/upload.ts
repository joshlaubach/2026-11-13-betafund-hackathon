// Pure upload rules shared by the dropzone and the analysis progress. No React or DOM imports,
// so Playwright can test these functions directly.

export const ACCEPTED_IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp", "image/gif"] as const;
export const MAX_UPLOAD_MB = 10;
export const MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024;

const BYTES_PER_KB = 1024;
const BYTES_PER_MB = 1024 * 1024;

export interface UploadCandidate {
  name: string;
  type: string;
  size: number;
}

export type UploadCheck = { ok: true } | { ok: false; message: string };

export type AnalysisStage = "reading" | "grading" | "done";
export type StepState = "waiting" | "active" | "done";

export function acceptAttribute(): string {
  return ACCEPTED_IMAGE_TYPES.join(",");
}

export function formatFileSize(bytes: number): string {
  if (bytes < BYTES_PER_KB) return `${bytes} B`;
  if (bytes < BYTES_PER_MB) return `${Math.round(bytes / BYTES_PER_KB)} KB`;
  return `${(bytes / BYTES_PER_MB).toFixed(1)} MB`;
}

export function validateUpload(candidate: UploadCandidate): UploadCheck {
  if (!(ACCEPTED_IMAGE_TYPES as readonly string[]).includes(candidate.type)) {
    const kind = candidate.type || "unknown type";
    return {
      ok: false,
      message: `"${candidate.name}" is not a photo Echo can read (${kind}). Choose a PNG, JPEG, WebP or GIF file.`,
    };
  }
  if (candidate.size === 0) {
    return { ok: false, message: `"${candidate.name}" is empty. Choose a photo that has content.` };
  }
  if (candidate.size > MAX_UPLOAD_BYTES) {
    return {
      ok: false,
      message: `"${candidate.name}" is ${formatFileSize(candidate.size)}, over the ${MAX_UPLOAD_MB} MB limit. Choose a smaller photo.`,
    };
  }
  return { ok: true };
}

// Each stage marks the steps before it done. A step is done only once the backend has moved past it.
export function stepStates(stage: AnalysisStage): [StepState, StepState] {
  switch (stage) {
    case "reading":
      return ["active", "waiting"];
    case "grading":
      return ["done", "active"];
    case "done":
      return ["done", "done"];
  }
}
