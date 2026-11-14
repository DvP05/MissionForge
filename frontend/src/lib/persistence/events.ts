/** Lightweight same-tab signal that saved runs / replay records changed (storage events do not fire in the writing tab). */
export const STORAGE_CHANGED_EVENT = "missionforge:storage-changed";

export function notifyStorageChanged(): void {
  if (typeof window !== "undefined") window.dispatchEvent(new Event(STORAGE_CHANGED_EVENT));
}
