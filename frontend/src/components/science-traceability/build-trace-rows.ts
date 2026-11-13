import type { MissionAnalysis, ScienceObjective } from "@/state/mission-store";

/** An instrument as the traceability join needs it (catalogue lookup data). */
export interface InstrumentRef {
  id: string;
  name: string;
  capabilities: readonly string[];
}

/**
 * "uncovered": no selected instrument lists the capability (capability match only).
 * "not-returned": backend analysis lists the requirement in missingRequirements.
 * "covered": backend analysis for the current revision does not list it.
 * "matched": instrument(s) have the capability; no current backend verdict yet
 *            (analysis pending/failed, or the requirement is optional).
 */
export type TraceStatus = "uncovered" | "not-returned" | "covered" | "matched";

export interface TraceRow {
  objectiveId: string;
  objectiveTitle: string;
  requirementId: string;
  requirementText: string;
  capability: string;
  required: boolean;
  instruments: InstrumentRef[];
  status: TraceStatus;
  /** True when the operations plan has an observation item for this requirement. */
  scheduled: boolean;
}

/**
 * Lookup/display join: objective -> requirement -> selected instruments whose
 * catalogue `capabilities` include the requirement's `instrumentCapability`.
 * Coverage verdicts come only from the backend analysis (`missingRequirements`).
 * `analysis` must already be filtered to the current revision by the caller.
 */
export function buildTraceRows(
  objectives: readonly ScienceObjective[],
  selectedInstruments: readonly InstrumentRef[],
  analysis: MissionAnalysis | null,
  scheduledMeasurementIds: ReadonlySet<string> = new Set(),
): TraceRow[] {
  const missing = new Set(analysis?.science.missingRequirements ?? []);
  const rows: TraceRow[] = [];
  for (const objective of objectives) {
    for (const req of objective.requiredMeasurements) {
      const instruments = selectedInstruments.filter((i) =>
        i.capabilities.includes(req.instrumentCapability),
      );
      let status: TraceStatus;
      if (instruments.length === 0) status = "uncovered";
      else if (analysis && req.required) status = missing.has(req.id) ? "not-returned" : "covered";
      else status = "matched";
      rows.push({
        objectiveId: objective.id,
        objectiveTitle: objective.title,
        requirementId: req.id,
        requirementText: req.description,
        capability: req.instrumentCapability,
        required: req.required,
        instruments,
        status,
        scheduled: scheduledMeasurementIds.has(req.id),
      });
    }
  }
  return rows;
}
