// Echo's motion tokens (from the motion-foundations skill). Every animated component imports these;
// no component defines its own duration, easing, distance, or spring.

export const motionTokens = {
  duration: {
    instant: 0.08,
    fast: 0.18,
    normal: 0.32,
    slow: 0.55,
  },
  easing: {
    smooth: [0.22, 1, 0.36, 1] as [number, number, number, number],
    sharp: [0.4, 0, 0.2, 1] as [number, number, number, number],
  },
  distance: {
    xs: 4,
    sm: 8,
    md: 16,
  },
  stagger: {
    list: 0.05,
    chips: 0.04,
  },
  scale: {
    press: 0.97,
  },
} as const;

export const springs = {
  snappy: { type: "spring", stiffness: 300, damping: 30 },
  gentle: { type: "spring", stiffness: 140, damping: 18 },
} as const;
