import { create } from "zustand";

import type { ComponentCategory, MissionState } from "@/state/mission-store";

export type ChangeKind = "add" | "replace" | "remove";

/** A component change the player asked for and has not confirmed yet (presentation state). */
export interface ChangeRequest {
  kind: ChangeKind;
  category: ComponentCategory;
  componentId: string;
  /** Element to return focus to when the dialog closes. */
  opener: HTMLElement | null;
}

/** The last confirmed change, kept so it can be undone by restoring the earlier design. */
export interface AppliedChange {
  kind: ChangeKind;
  category: ComponentCategory;
  componentId: string;
  /** The component it replaced (replace only). */
  replacedId: string | null;
  /** Design revision the change created. */
  revision: number;
  /** Architecture before the change: undo restores it as a NEW revision. */
  before: MissionState["architecture"];
}

export interface ChangeStoreState {
  pending: ChangeRequest | null;
  applied: AppliedChange | null;
  request: (r: ChangeRequest) => void;
  cancel: () => void;
  recordApplied: (c: AppliedChange) => void;
  clearApplied: () => void;
}

export const useChangeStore = create<ChangeStoreState>()((set) => ({
  pending: null,
  applied: null,
  request: (pending) => set({ pending }),
  cancel: () => set({ pending: null }),
  recordApplied: (applied) => set({ applied, pending: null }),
  clearApplied: () => set({ applied: null }),
}));
