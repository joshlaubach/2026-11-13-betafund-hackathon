"use client";

import "../app/tutor.css";
import { motion, useReducedMotion } from "motion/react";
import {
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type CSSProperties,
  type KeyboardEvent,
  type PointerEvent,
  type ReactNode,
} from "react";
import { motionTokens, springs } from "@/lib/motion-tokens";
import {
  TUTOR_DEFAULT_WIDTH,
  TUTOR_MIN_WIDTH,
  browserStorage,
  clampTutorWidth,
  nextWidthForKey,
  readStoredWidth,
  tutorMaxWidth,
  writeStoredWidth,
} from "@/lib/split";
import { useIsDesktop } from "@/lib/use-desktop";
import { useKeyboardInset } from "@/lib/keyboard-inset";

export type MobileView = "worksheet" | "tutor";

export type SplitWorkspaceProps = {
  workspace: ReactNode;
  tutor: ReactNode;
  tutorOpen: boolean;
  onTutorOpenChange: (open: boolean) => void;
  mobileView: MobileView;
  onMobileViewChange: (view: MobileView) => void;
};

const TABS: { view: MobileView; label: string }[] = [
  { view: "worksheet", label: "Worksheet" },
  { view: "tutor", label: "Tutor" },
];
const SEPARATOR_PX = 8;
const SERVER_VIEWPORT = 1440;
const PANE_HIDDEN_X = "100%";

function subscribeToResize(onChange: () => void): () => void {
  window.addEventListener("resize", onChange);
  return () => window.removeEventListener("resize", onChange);
}

function readViewport(): number {
  return window.innerWidth;
}

function useViewportWidth(): number {
  return useSyncExternalStore(subscribeToResize, readViewport, () => SERVER_VIEWPORT);
}

function tabId(view: MobileView): string {
  return `split-tab-${view}`;
}

function panelId(view: MobileView): string {
  return `split-panel-${view}`;
}

// Arrow keys wrap between tabs; Home and End jump to the first and last tab.
function nextTabIndex(key: string, index: number, count: number): number | null {
  if (key === "ArrowRight") return (index + 1) % count;
  if (key === "ArrowLeft") return (index - 1 + count) % count;
  if (key === "Home") return 0;
  if (key === "End") return count - 1;
  return null;
}

type DragState = { startX: number; startWidth: number; latest: number };

export function SplitWorkspace({
  workspace,
  tutor,
  tutorOpen,
  onTutorOpenChange,
  mobileView,
  onMobileViewChange,
}: SplitWorkspaceProps) {
  const isDesktop = useIsDesktop();
  useKeyboardInset();
  const tutorVisible = isDesktop ? tutorOpen : mobileView === "tutor";
  const workspaceVisible = isDesktop || mobileView === "worksheet";
  const viewport = useViewportWidth();
  const reduceMotion = Boolean(useReducedMotion());
  const [storedWidth, setStoredWidth] = useState(TUTOR_DEFAULT_WIDTH);
  const width = clampTutorWidth(storedWidth, viewport);
  const dragRef = useRef<DragState | null>(null);
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const tutorPaneRef = useRef<HTMLDivElement>(null);
  const scrollMemory = useRef<Partial<Record<MobileView, number>>>({});

  useEffect(() => {
    const stored = readStoredWidth(browserStorage());
    if (stored !== null) setStoredWidth(stored);
  }, []);

  // A hidden tutor column must not be focusable or reachable by assistive tech.
  useEffect(() => {
    tutorPaneRef.current?.toggleAttribute("inert", !tutorVisible);
  }, [tutorVisible]);

  // Each phone view keeps its own scroll position, since the hidden view leaves the page.
  useEffect(() => {
    if (isDesktop) return;
    window.scrollTo({ top: scrollMemory.current[mobileView] ?? 0, behavior: "auto" });
  }, [mobileView, isDesktop]);

  function commitWidth(next: number): void {
    setStoredWidth(next);
    writeStoredWidth(browserStorage(), next);
  }

  function handlePointerDown(event: PointerEvent<HTMLDivElement>): void {
    if (event.button !== 0) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = { startX: event.clientX, startWidth: width, latest: width };
  }

  // The separator sits to the left of the tutor, so dragging left makes the tutor wider.
  function handlePointerMove(event: PointerEvent<HTMLDivElement>): void {
    const drag = dragRef.current;
    if (!drag) return;
    drag.latest = clampTutorWidth(drag.startWidth + (drag.startX - event.clientX), viewport);
    setStoredWidth(drag.latest);
  }

  function handlePointerEnd(event: PointerEvent<HTMLDivElement>): void {
    const drag = dragRef.current;
    if (!drag) return;
    dragRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    writeStoredWidth(browserStorage(), drag.latest);
  }

  function handleSeparatorKey(event: KeyboardEvent<HTMLDivElement>): void {
    const next = nextWidthForKey(event.key, width, viewport);
    if (next === null) return;
    event.preventDefault();
    commitWidth(next);
  }

  function select(view: MobileView): void {
    if (view === mobileView) return;
    scrollMemory.current[mobileView] = window.scrollY;
    onMobileViewChange(view);
    onTutorOpenChange(view === "tutor");
  }

  function handleTabKey(event: KeyboardEvent<HTMLButtonElement>, index: number): void {
    const target = nextTabIndex(event.key, index, TABS.length);
    if (target === null) return;
    event.preventDefault();
    tabRefs.current[target]?.focus();
    select(TABS[target].view);
  }

  const paneTransition = reduceMotion
    ? { duration: 0 }
    : { duration: motionTokens.duration.normal, ease: motionTokens.easing.smooth };
  const pillTransition = reduceMotion ? { duration: 0 } : springs.snappy;
  // Desktop grid columns: a separator and the tutor column are 0px while the tutor is closed.
  const splitStyle = {
    "--split-sep": isDesktop && tutorOpen ? `${SEPARATOR_PX}px` : "0px",
    "--split-tutor": isDesktop && tutorOpen ? `${width}px` : "0px",
  } as CSSProperties;
  const panelRole = isDesktop ? undefined : "tabpanel";

  return (
    <>
      <div className="split" style={splitStyle}>
        <div
          id={panelId("worksheet")}
          role={panelRole}
          aria-labelledby={isDesktop ? undefined : tabId("worksheet")}
          className="split-pane split-pane-workspace"
          hidden={!workspaceVisible}
        >
          {workspace}
        </div>

        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize tutor"
          aria-valuenow={width}
          aria-valuemin={TUTOR_MIN_WIDTH}
          aria-valuemax={tutorMaxWidth(viewport)}
          tabIndex={0}
          className="split-separator"
          hidden={!isDesktop || !tutorOpen}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerEnd}
          onPointerCancel={handlePointerEnd}
          onDoubleClick={() => commitWidth(clampTutorWidth(TUTOR_DEFAULT_WIDTH, viewport))}
          onKeyDown={handleSeparatorKey}
        />

        <div
          ref={tutorPaneRef}
          id={panelId("tutor")}
          role={panelRole}
          aria-labelledby={isDesktop ? undefined : tabId("tutor")}
          className="split-pane split-pane-tutor"
          hidden={!isDesktop && !tutorVisible}
        >
          {/* The slide is transform-only, so it never animates width. The pane's column width changes instantly. */}
          <motion.div
            className="split-pane-slide"
            initial={false}
            // After the exit slide finishes, the closed tutor is fully hidden, not just transparent.
            animate={
              isDesktop && !tutorOpen
                ? { x: PANE_HIDDEN_X, opacity: 0, transitionEnd: { visibility: "hidden" } }
                : { x: 0, opacity: 1, visibility: "visible" }
            }
            transition={paneTransition}
          >
            {tutor}
          </motion.div>
        </div>
      </div>

      <div className="split-tabs" role="tablist" aria-label="Worksheet or tutor" hidden={isDesktop}>
        {TABS.map((tab, index) => {
          const selected = tab.view === mobileView;
          return (
            <button
              key={tab.view}
              ref={(element) => {
                tabRefs.current[index] = element;
              }}
              id={tabId(tab.view)}
              type="button"
              role="tab"
              aria-selected={selected}
              aria-controls={panelId(tab.view)}
              tabIndex={selected ? 0 : -1}
              className="split-tab"
              onClick={() => select(tab.view)}
              onKeyDown={(event) => handleTabKey(event, index)}
            >
              {selected && (
                <motion.span layoutId="split-tab-pill" className="split-tab-pill" aria-hidden="true" transition={pillTransition} />
              )}
              <span className="split-tab-label">{tab.label}</span>
            </button>
          );
        })}
      </div>
    </>
  );
}
