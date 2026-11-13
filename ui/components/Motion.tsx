"use client";

// Shared motion primitives. Reduced motion turns every transform off and keeps only a short fade.
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";
import { motionTokens } from "@/lib/motion-tokens";

const REDUCED_FADE = { duration: motionTokens.duration.fast };

function useEnter(distance: number = motionTokens.distance.md) {
  const reduce = useReducedMotion();
  const y = reduce ? 0 : distance;
  return {
    initial: { opacity: 0, y },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: reduce ? 0 : -motionTokens.distance.sm },
    transition: reduce
      ? REDUCED_FADE
      : { duration: motionTokens.duration.normal, ease: motionTokens.easing.smooth },
  };
}

// A block that fades and rises in when it mounts, and out when it leaves (inside a Presence).
export function Reveal({ children, className, delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  const enter = useEnter();
  return (
    <motion.div className={className} {...enter} transition={{ ...enter.transition, delay }}>
      {children}
    </motion.div>
  );
}

// Swaps one keyed child for the next: the old one leaves before the new one enters.
export function Swap({ children, swapKey }: { children: ReactNode; swapKey: string }) {
  return (
    <AnimatePresence mode="wait" initial={false}>
      <Reveal key={swapKey}>{children}</Reveal>
    </AnimatePresence>
  );
}

// Children that enter and leave independently, each keyed by the caller.
export function Presence({ children }: { children: ReactNode }) {
  return <AnimatePresence initial={false}>{children}</AnimatePresence>;
}

// List items that enter one after another.
export function StaggerItem({
  children,
  index,
  className,
  step = motionTokens.stagger.list,
}: {
  children: ReactNode;
  index: number;
  className?: string;
  step?: number;
}) {
  const enter = useEnter(motionTokens.distance.sm);
  return (
    <motion.li className={className} {...enter} transition={{ ...enter.transition, delay: index * step }}>
      {children}
    </motion.li>
  );
}
