import { create } from "zustand";

import type { ComponentCategory, ViewMode } from "@/lib/spacecraft/part-registry";

/**
 * Presentation-only state for the spacecraft architect: which part is inspected, the 3D view
 * mode and overlay toggles, and parts highlighted from elsewhere (e.g. a science objective).
 * It never holds engineering truth: what is installed always comes from the mission store.
 */
export type PanelTab = "available" | "installed" | "details";
export type MobileTab = "build" | "spacecraft" | "budgets";

export interface ArchitectUiState {
  selectedId: string | null;
  category: ComponentCategory;
  mode: ViewMode;
  labels: boolean;
  mounts: boolean;
  wireframe: boolean;
  /** Parts emphasised by another panel (science objective, constraint); empty = none. */
  highlightIds: string[];
  highlightReason: string | null;
  /** Bumped to ask the viewport to move the camera to the selected part. */
  focusNonce: number;
  /** Right-hand panel view: the catalogue, the installed tree, or the inspected part. */
  panelTab: PanelTab;
  /** Narrow screens show one zone at a time (design_update.md 13). */
  mobileTab: MobileTab;
  /** Last component installed by the player, for the install animation. */
  justInstalled: { componentId: string; nonce: number } | null;

  select: (id: string | null, category?: ComponentCategory) => void;
  setPanelTab: (tab: PanelTab) => void;
  setMobileTab: (tab: MobileTab) => void;
  setCategory: (category: ComponentCategory) => void;
  setMode: (mode: ViewMode) => void;
  toggle: (key: "labels" | "mounts" | "wireframe") => void;
  highlight: (ids: string[], reason: string | null) => void;
  focusSelected: () => void;
  markInstalled: (componentId: string) => void;
}

export const useArchitectUi = create<ArchitectUiState>()((set) => ({
  selectedId: null,
  category: "communications",
  mode: "assembly",
  labels: false,
  mounts: false,
  wireframe: false,
  highlightIds: [],
  highlightReason: null,
  focusNonce: 0,
  justInstalled: null,
  panelTab: "available",
  mobileTab: "build",

  select: (id, category) =>
    set((s) => ({ selectedId: id, category: category ?? s.category, panelTab: id ? "details" : s.panelTab })),
  setPanelTab: (panelTab) => set({ panelTab }),
  setMobileTab: (mobileTab) => set({ mobileTab }),
  setCategory: (category) => set({ category, panelTab: "available" }),
  setMode: (mode) =>
    set(() => ({
      mode,
      // the technical mode turns its overlays on; other modes leave the player's toggles alone
      ...(mode === "technical" ? { labels: true, mounts: true } : {}),
    })),
  toggle: (key) => set((s) => ({ [key]: !s[key] }) as Pick<ArchitectUiState, typeof key>),
  highlight: (ids, reason) => set({ highlightIds: ids, highlightReason: ids.length ? reason : null }),
  focusSelected: () => set((s) => ({ focusNonce: s.focusNonce + 1 })),
  markInstalled: (componentId) =>
    set((s) => ({ justInstalled: { componentId, nonce: (s.justInstalled?.nonce ?? 0) + 1 }, selectedId: componentId })),
}));
