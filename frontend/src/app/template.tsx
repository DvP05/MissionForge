"use client";

import { MotionConfig, motion } from "motion/react";
import type { ReactNode } from "react";

import { useMotionPref } from "@/components/shell/MotionToggle";

/**
 * Page transition (Motion): a short fade-and-rise on every navigation. `reducedMotion="user"`
 * makes every Motion animation in the app honour prefers-reduced-motion.
 */
export default function Template({ children }: { children: ReactNode }) {
  const pref = useMotionPref();
  return (
    <MotionConfig reducedMotion={pref === "reduced" ? "always" : "user"}>
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25, ease: [0.2, 0.7, 0.2, 1] }}
      >
        {children}
      </motion.div>
    </MotionConfig>
  );
}
