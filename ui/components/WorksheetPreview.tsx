"use client";

import "../app/upload.css";
import { useRef, useState, type ReactNode, type RefObject, type SyntheticEvent } from "react";
import { motion, useReducedMotion } from "motion/react";
import { motionTokens } from "@/lib/motion-tokens";

type Props = {
  src: string;
  alt: string;
};

type Rotation = 0 | 90 | 180 | 270;
type IconName = "zoom-in" | "zoom-out" | "reset" | "rotate" | "fullscreen" | "close";

const MIN_ZOOM = 1;
const MAX_ZOOM = 3;
const ZOOM_STEP = 0.5;
const ENTER_SCALE = 0.98;
const NEXT_ROTATION: Record<Rotation, Rotation> = { 0: 90, 90: 180, 180: 270, 270: 0 };

const ICON_PATHS: Record<IconName, ReactNode> = {
  "zoom-in": (
    <>
      <circle cx="11" cy="11" r="6.5" />
      <path d="M16 16l4.5 4.5M11 8v6M8 11h6" />
    </>
  ),
  "zoom-out": (
    <>
      <circle cx="11" cy="11" r="6.5" />
      <path d="M16 16l4.5 4.5M8 11h6" />
    </>
  ),
  reset: (
    <>
      <path d="M4 12a8 8 0 1 0 2.3-5.7" />
      <path d="M4 4v5h5" />
    </>
  ),
  rotate: (
    <>
      <path d="M20 12a8 8 0 1 1-2.3-5.7" />
      <path d="M20 4v5h-5" />
    </>
  ),
  fullscreen: <path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" />,
  close: <path d="M6 6l12 12M18 6L6 18" />,
};

function ToolIcon({ name }: { name: IconName }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {ICON_PATHS[name]}
    </svg>
  );
}

// Offsets, as a percent of the photo's own width and height, that move the scaled and turned box back
// inside the scrollable area. The transform origin is the top-left, so a turned photo would otherwise
// extend past the top or left edge where the student cannot scroll.
function overshootShift(rotation: Rotation, ratio: number): [string, string] {
  switch (rotation) {
    case 0:
      return ["0%", "0%"];
    case 90:
      return [`${100 / ratio}%`, "0%"];
    case 180:
      return ["100%", "100%"];
    case 270:
      return ["0%", `${ratio * 100}%`];
  }
}

function imageTransform(rotation: Rotation, zoom: number, ratio: number): string {
  const [shiftX, shiftY] = overshootShift(rotation, ratio);
  return `translate(calc(${zoom} * ${shiftX}), calc(${zoom} * ${shiftY})) rotate(${rotation}deg) scale(${zoom})`;
}

interface ToolbarProps {
  zoom: number;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
  onRotate: () => void;
  onFullscreen?: () => void;
  fullscreenRef?: RefObject<HTMLButtonElement>;
  onClose?: () => void;
}

function PreviewToolbar({ zoom, onZoomIn, onZoomOut, onReset, onRotate, onFullscreen, fullscreenRef, onClose }: ToolbarProps) {
  return (
    <div className="preview-toolbar" role="group" aria-label="Photo tools">
      <button type="button" className="preview-tool quiet" onClick={onZoomOut} disabled={zoom <= MIN_ZOOM}>
        <ToolIcon name="zoom-out" />
        Zoom out
      </button>
      <button type="button" className="preview-tool quiet" onClick={onZoomIn} disabled={zoom >= MAX_ZOOM}>
        <ToolIcon name="zoom-in" />
        Zoom in
      </button>
      <button type="button" className="preview-tool quiet" onClick={onReset}>
        <ToolIcon name="reset" />
        Reset
      </button>
      <button type="button" className="preview-tool quiet" onClick={onRotate}>
        <ToolIcon name="rotate" />
        Rotate
      </button>
      {onFullscreen && (
        <button ref={fullscreenRef} type="button" className="preview-tool quiet" onClick={onFullscreen}>
          <ToolIcon name="fullscreen" />
          Full screen
        </button>
      )}
      {onClose && (
        <button type="button" className="preview-tool quiet" onClick={onClose}>
          <ToolIcon name="close" />
          Close
        </button>
      )}
    </div>
  );
}

interface FrameProps {
  src: string;
  alt: string;
  transform: string;
  inDialog?: boolean;
  onMeasure: (ratio: number) => void;
}

// One photo in a scrollable frame. Keyed by src by the parent, so a new photo starts unloaded.
function PhotoFrame({ src, alt, transform, inDialog = false, onMeasure }: FrameProps) {
  const reduce = Boolean(useReducedMotion());
  const [loaded, setLoaded] = useState(false);

  function handleLoad(event: SyntheticEvent<HTMLImageElement>) {
    const { naturalWidth, naturalHeight } = event.currentTarget;
    if (naturalWidth > 0 && naturalHeight > 0) onMeasure(naturalWidth / naturalHeight);
    setLoaded(true);
  }

  return (
    <div className={`preview-frame${inDialog ? " is-dialog" : ""}`} role="region" aria-label={alt} tabIndex={0}>
      <motion.div
        className="preview-reveal"
        initial={{ opacity: 0, scale: reduce ? 1 : ENTER_SCALE }}
        animate={{ opacity: loaded ? 1 : 0, scale: loaded || reduce ? 1 : ENTER_SCALE }}
        transition={{
          duration: reduce ? motionTokens.duration.fast : motionTokens.duration.normal,
          ease: motionTokens.easing.smooth,
        }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img className="preview-image" src={src} alt={alt} style={{ transform }} onLoad={handleLoad} draggable={false} />
      </motion.div>
    </div>
  );
}

export function WorksheetPreview({ src, alt }: Props) {
  const [zoom, setZoom] = useState(MIN_ZOOM);
  const [rotation, setRotation] = useState<Rotation>(0);
  const [ratio, setRatio] = useState(1);
  const fullscreenButton = useRef<HTMLButtonElement>(null);
  const dialog = useRef<HTMLDialogElement>(null);

  const transform = imageTransform(rotation, zoom, ratio);
  const percent = Math.round(zoom * 100);

  function zoomIn() {
    setZoom((current) => Math.min(MAX_ZOOM, current + ZOOM_STEP));
  }

  function zoomOut() {
    setZoom((current) => Math.max(MIN_ZOOM, current - ZOOM_STEP));
  }

  function reset() {
    setZoom(MIN_ZOOM);
    setRotation(0);
  }

  function rotate() {
    setRotation((current) => NEXT_ROTATION[current]);
  }

  function openFullscreen() {
    dialog.current?.showModal();
  }

  function closeFullscreen() {
    dialog.current?.close();
  }

  const tools = { zoom, onZoomIn: zoomIn, onZoomOut: zoomOut, onReset: reset, onRotate: rotate };

  return (
    <div className="worksheet-preview">
      <PreviewToolbar {...tools} onFullscreen={openFullscreen} fullscreenRef={fullscreenButton} />
      <p className="preview-status" aria-live="polite">
        Zoom {percent}%
      </p>
      <PhotoFrame key={src} src={src} alt={alt} transform={transform} onMeasure={setRatio} />

      <dialog
        ref={dialog}
        className="preview-dialog"
        aria-label="Worksheet photo"
        onClose={() => fullscreenButton.current?.focus()}
      >
        <PreviewToolbar {...tools} onClose={closeFullscreen} />
        <PhotoFrame key={`${src}-full`} src={src} alt={alt} transform={transform} inDialog onMeasure={setRatio} />
      </dialog>
    </div>
  );
}
