"use client";

import "../app/upload.css";
import { useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { motion, useReducedMotion } from "motion/react";
import { motionTokens } from "@/lib/motion-tokens";
import { acceptAttribute, formatFileSize, MAX_UPLOAD_MB, validateUpload } from "@/lib/upload";

type Props = {
  file: File | null;
  onFile: (file: File | null) => void;
  disabled?: boolean;
};

const DRAG_SCALE = 1.015;
const ERROR_ID = "upload-error";

function UploadIcon() {
  return (
    <svg className="dropzone-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 16V4" />
      <path d="M7 9l5-5 5 5" />
      <path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
    </svg>
  );
}

export function UploadDropzone({ file, onFile, disabled = false }: Props) {
  const reduce = Boolean(useReducedMotion());
  const input = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // A rejected file leaves the current choice alone; only a valid file reaches onFile.
  function accept(candidate: File | undefined): void {
    if (!candidate) return;
    const check = validateUpload(candidate);
    if (!check.ok) {
      setError(check.message);
      return;
    }
    setError(null);
    onFile(candidate);
  }

  function handleChoose(event: ChangeEvent<HTMLInputElement>) {
    accept(event.target.files?.[0]);
    // Clear the input so choosing the same photo again after Remove still fires a change.
    event.target.value = "";
  }

  function handleDragOver(event: DragEvent<HTMLLabelElement>) {
    if (disabled) return;
    event.preventDefault();
    setDragOver(true);
  }

  function handleDragLeave(event: DragEvent<HTMLLabelElement>) {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragOver(false);
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragOver(false);
    if (disabled) return;
    accept(event.dataTransfer.files[0]);
  }

  function openPicker() {
    input.current?.click();
  }

  function remove() {
    setError(null);
    onFile(null);
  }

  const dropzoneClass = ["dropzone", dragOver && "is-drag-over", disabled && "is-disabled", file && "has-file"]
    .filter(Boolean)
    .join(" ");

  return (
    <div className="upload-dropzone">
      <motion.label
        className={dropzoneClass}
        animate={{ scale: dragOver && !reduce ? DRAG_SCALE : 1 }}
        transition={{ duration: motionTokens.duration.fast, ease: motionTokens.easing.smooth }}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <input
          ref={input}
          id="worksheet"
          type="file"
          accept={acceptAttribute()}
          className="dropzone-input"
          disabled={disabled}
          aria-describedby={error ? ERROR_ID : undefined}
          onChange={handleChoose}
        />
        <span className="dropzone-face">
          <UploadIcon />
          <span className="dropzone-title">
            {file ? "Drop a different photo here, or click to choose one" : "Drop a worksheet photo here"}
          </span>
          <span className="dropzone-sub">
            or click to choose a file, PNG, JPEG, WebP or GIF, up to {MAX_UPLOAD_MB} MB
          </span>
        </span>
      </motion.label>

      {error && (
        <p id={ERROR_ID} className="upload-error" role="alert">
          {error}
        </p>
      )}

      {file && (
        <div className="chosen-file">
          <div className="chosen-meta">
            <span className="chosen-name">{file.name}</span>
            <span className="chosen-size">{formatFileSize(file.size)}</span>
          </div>
          <div className="chosen-actions">
            <button type="button" className="quiet" onClick={openPicker} disabled={disabled}>
              Replace photo
            </button>
            <button type="button" className="quiet" onClick={remove} disabled={disabled}>
              Remove
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
