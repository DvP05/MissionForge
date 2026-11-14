import { create } from "zustand";

/** What the last import could not keep, shown once on the opened mission (in memory only). */
export interface ImportNotice {
  missionId: string;
  total: number;
  notKept: string[];
}

interface NoticeState {
  notice: ImportNotice | null;
  setNotice: (n: ImportNotice | null) => void;
}

export const useImportNotice = create<NoticeState>((set) => ({ notice: null, setNotice: (notice) => set({ notice }) }));
