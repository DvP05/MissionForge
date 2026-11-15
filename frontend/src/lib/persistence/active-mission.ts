/**
 * The mission the player last worked on in this browser, so the station rail can link to its
 * briefing, architect, readiness review and latest flight from any page. Presentation only.
 */
const KEY = "missionforge:active-mission";
export const ACTIVE_MISSION_EVENT = "missionforge:active-mission";

export function readActiveMission(): string | null {
  try {
    return window.localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function writeActiveMission(missionId: string): void {
  try {
    if (window.localStorage.getItem(KEY) === missionId) return;
    window.localStorage.setItem(KEY, missionId);
  } catch {
    /* storage unavailable: the rail falls back to the open mission only */
  }
  window.dispatchEvent(new Event(ACTIVE_MISSION_EVENT));
}
