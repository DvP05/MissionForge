import { ConstraintBadge, type ConstraintStatus } from "@/components/common/ConstraintBadge";
import { FidelityBadge, type Fidelity } from "@/components/common/FidelityBadge";
import { ProvenancePopover, type Provenance } from "@/components/common/ProvenancePopover";

const CONSTRAINT_STATES: ConstraintStatus[] = ["pass", "warning", "fail", "not-modelled"];
const FIDELITIES: Fidelity[] = [
  "source-backed",
  "derived",
  "gameplay-estimate",
  "not-modelled",
];

// Demonstration record for the legend only; not a real catalogue value.
const EXAMPLE_PROVENANCE: Provenance = {
  fidelity: "gameplay-estimate",
  sourceName: "Example entry (legend only)",
  sourceVersion: "n/a",
  assumptions: ["Shown to explain what the provenance panel contains."],
};

const FIDELITY_TIERS: [Fidelity, string][] = [
  ["source-backed", "Copied from a cited primary source (with edition, retrieval date and units) and checked by a person."],
  ["derived", "Computed by the MISSIONFORGE engine from other values with a documented equation; only as good as its inputs."],
  ["gameplay-estimate", "A plausible illustrative number chosen for the game. Useful for learning trade-offs, not for engineering."],
  ["not-modelled", "Deliberately not computed. Shown as a dash with the reason, never as zero or as a pass."],
];

const FEATURES: [string, string, string, string][] = [
  ["Mission digital twin + STM/MTM", "NASA model-based mission formulation", "One canonical mission state; generated traceability matrices", "Educational subset of MBSE"],
  ["Architecture impact graph", "NASA mission formulation; architecture-graph research", "Typed dependency edges and graph traversal", "Deterministic project model"],
  ["Pareto Design Arena", "Bussemaker and Firchau; model-based CubeSat design", "Candidate mutations + non-dominated sorting", "Simplified multi-objective search"],
  ["Robustness Lab", "Babapour and Taheri; design under uncertainty", "Seeded Monte Carlo + Wilson interval", "Not a flight probability model"],
  ["Science belief tracker", "Guirguis et al.; Kim et al.", "Bayesian hypothesis updates + entropy", "Synthetic mission likelihoods"],
  ["Blackout autonomy", "Kim et al.", "Three policies; hard resource checks", "Rule-based autonomy analogue, not a POMDP solver"],
  ["Science/downlink scheduler", "Levinson et al., IJCAI 2025", "One-spacecraft greedy data-cycle scheduler", "Not a globally optimal MILP"],
  ["Telemetry health monitor", "Goetze et al.; Alcarria et al.", "EWMA residual, thresholds, persistence", "Explainable statistical baseline, not a trained detector"],
];

const REFERENCES: [string, string][] = [
  ["NASA model-based mission formulation", "https://ntrs.nasa.gov/citations/20220019154"],
  ["Bussemaker and Firchau (2025), system architecture optimization", "https://doi.org/10.1007/s12567-025-00626-7"],
  ["Schmitt et al. (2025), mission architecture sandbox game framework", "https://doi.org/10.1016/j.actaastro.2025.04.004"],
  ["Guirguis et al. (2026), POMDP science exploration (preprint)", "https://arxiv.org/abs/2608.03155"],
  ["Kim et al. (2025), offline belief-state science operations (preprint)", "https://arxiv.org/abs/2510.08812"],
  ["Babapour and Taheri (2026), robust low-thrust covariance steering (preprint)", "https://arxiv.org/abs/2601.17629"],
  ["Levinson et al. (2025), science/downlink planning", "https://doi.org/10.24963/ijcai.2025/950"],
  ["Goetze et al. (2025), telemetry anomaly detection", "https://doi.org/10.1109/SCC66396.2025.00019"],
  ["Alcarria et al. (2026), unsupervised telemetry anomaly detection (preprint)", "https://arxiv.org/abs/2609.10017"],
  ["IEEE Access (2026), serious games in engineering education", "https://doi.org/10.1109/ACCESS.2026.3669416"],
  ["NASA Small Spacecraft State-of-the-Art (2026)", "https://www.nasa.gov/smallsat-institute/sst-soa/"],
  ["JPL Small-Body Mission Design API", "https://ssd-api.jpl.nasa.gov/doc/mdesign.html"],
];

export const metadata = { title: "About | MISSIONFORGE" };

export default function AboutPage() {
  return (
    <div className="space-y-10">
      <section className="max-w-2xl space-y-3">
        <h1 className="text-3xl font-semibold tracking-tight">About MISSIONFORGE</h1>
        <p className="text-muted">
          MISSIONFORGE is an independent educational prototype. The Python engine owns all
          engineering calculations; this interface presents results and how much to trust them.
        </p>
      </section>

      <section aria-labelledby="fidelity-legend" className="space-y-3">
        <h2 id="fidelity-legend" className="text-xl font-semibold">
          Value fidelity
        </h2>
        <ul className="flex flex-wrap items-center gap-3">
          {FIDELITIES.map((f) => (
            <li key={f}>
              <FidelityBadge fidelity={f} />
            </li>
          ))}
          <li className="flex items-center gap-2 text-sm text-muted">
            Example provenance panel
            <ProvenancePopover provenance={EXAMPLE_PROVENANCE} label="the example value" />
          </li>
        </ul>
      </section>

      <section aria-labelledby="constraint-legend" className="space-y-3">
        <h2 id="constraint-legend" className="text-xl font-semibold">
          Constraint results
        </h2>
        <ul className="flex flex-wrap gap-3">
          {CONSTRAINT_STATES.map((s) => (
            <li key={s}>
              <ConstraintBadge status={s} />
            </li>
          ))}
        </ul>
        <p className="text-sm text-muted">
          Every result carries an icon and a word, so meaning never depends on colour alone.
        </p>
      </section>

      <section aria-labelledby="fidelity-tiers" className="max-w-3xl space-y-3">
        <h2 id="fidelity-tiers" className="text-xl font-semibold">
          What each fidelity level means
        </h2>
        <dl className="space-y-3 text-sm">
          {FIDELITY_TIERS.map(([tier, text]) => (
            <div key={tier} className="space-y-1">
              <dt>
                <FidelityBadge fidelity={tier} />
              </dt>
              <dd className="text-muted">{text}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section aria-labelledby="modelled" className="space-y-3">
        <h2 id="modelled" className="text-xl font-semibold">
          What is modelled, and what is not claimed
        </h2>
        <div
          tabIndex={0}
          role="region"
          aria-label="Feature fidelity table (scrolls sideways)"
          className="overflow-x-auto rounded-xl border border-border"
        >
          <table className="w-full min-w-[40rem] text-left text-sm">
            <thead className="text-muted">
              <tr>
                <th scope="col" className="px-3 py-2 font-medium">Feature</th>
                <th scope="col" className="px-3 py-2 font-medium">Research inspiration</th>
                <th scope="col" className="px-3 py-2 font-medium">What MISSIONFORGE implements</th>
                <th scope="col" className="px-3 py-2 font-medium">Fidelity statement</th>
              </tr>
            </thead>
            <tbody>
              {FEATURES.map((row) => (
                <tr key={row[0]} className="border-t border-border/60 align-top">
                  {row.map((cell, i) => (
                    <td key={i} className="px-3 py-2">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-sm text-muted">
          Research papers motivate the features; they are not claims that MISSIONFORGE reproduces their methods. No
          large language model is used to compute any number.
        </p>
      </section>

      <section aria-labelledby="sources" className="max-w-3xl space-y-3">
        <h2 id="sources" className="text-xl font-semibold">
          Sources and references
        </h2>
        <ul className="space-y-1 text-sm">
          {REFERENCES.map(([label, url]) => (
            <li key={url} className="break-words">
              {label}:{" "}
              <a href={url} className="text-accent-cyan underline underline-offset-2" rel="noreferrer" target="_blank">
                {url}
              </a>
            </li>
          ))}
        </ul>
        <p className="text-sm text-muted">
          Preprints are labelled as such; a preprint is research, not a standard or an endorsement. Catalogue values
          are gameplay estimates until a human source audit links each one to a primary table.
        </p>
      </section>

      <section aria-labelledby="credits" className="max-w-3xl space-y-3">
        <h2 id="credits" className="text-xl font-semibold">
          Credits and endorsement
        </h2>
        <p className="text-sm">
          Built by the MISSIONFORGE team for the 2026 NASA Space Apps Challenge (Space Mission Design Game). Built
          with FastAPI, Pydantic, Next.js, React, Tailwind CSS, Recharts, Zustand, lucide icons, and Playwright with
          axe-core.
        </p>
        <p data-testid="about-non-endorsement" className="text-sm">
          MISSIONFORGE is an independent educational prototype. It is not endorsed by, affiliated with, or sponsored
          by NASA or JPL, and it uses no NASA or JPL logos. Results are for learning and must not be used for real
          mission planning.
        </p>
      </section>
    </div>
  );
}
