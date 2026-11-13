# MISSIONFORGE — Product Requirements & Delivery Specification

**Document type:** Product requirements document (PRD), user experience specification, acceptance criteria and hackathon delivery plan  
**Version:** 1.1  
**Date:** 2026-10-31  
**Primary audience:** Product owner, designers, engineers, AI coding agents, judges

---

## 1. Product vision

MISSIONFORGE makes the invisible complexity of space mission engineering tangible. Players do not simply assemble a spacecraft; they construct a defensible mission architecture, see how engineering choices interact, operate the mission under pressure, and learn from the outcome.

**Vision statement:** Help a new learner think like a mission designer by making scientific intent, engineering constraints, uncertainty and operations part of one playable experience.

**One-line promise:** *Design a mission. Make the trade-offs. Fly the consequences.*

### 1.1 The product should feel

- Scientifically credible, but welcoming to a student who has never designed a spacecraft.
- Visually exciting, but never at the cost of understandable engineering information.
- Challenging, but fair: failures should be traceable to choices, assumptions or scenario risks.
- Educational, but not lecture-first: concepts should be explained at the moment they matter.
- Transparent: the player should know what is real data, what is derived, and what is simplified for gameplay.

---

## 2. Problem statement

The 2026 challenge calls out a gap: students often learn mission-design trade-offs as abstract concepts, without the chance to experiment with a complete mission from concept to operations. A single-discipline calculator cannot teach the system-level consequences. A conventional parts-selection game can encourage shallow optimization (“choose the strongest part”) without exposing coupling or operational effects.

MISSIONFORGE addresses this with:

1. A guided science-to-requirements workflow.
2. A coupled spacecraft design model.
3. Live resource and feasibility feedback.
4. A mission operations simulator with consequential choices.
5. A post-mission report that explains causality and suggests counterfactual redesigns.

---

## 3. Audience and personas

### Primary: Curious STEM learner

- Age: middle/high-school, undergraduate, or self-directed learner.
- Wants to understand how space missions work.
- May know popular space missions but not engineering vocabulary.
- Needs short explanations, visible cause/effect, guided defaults and no setup burden.

### Secondary: Engineering student / hackathon participant

- Interested in aerospace, software, physics, robotics or systems engineering.
- Wants realistic constraints, traceable values and more than trivia.
- Needs equations, unit labels, sources, trade studies and repeatable outcomes.

### Tertiary: Educator / outreach facilitator

- Wants a reusable classroom exercise.
- Needs a clear learning objective, short session duration, predictable scenario, and debrief/export.

### Judge / domain expert

- Wants to see technical depth, authentic data usage, complete end-to-end flow, coherent software design, and clear communication of limitations.
- Needs to understand the unique value within minutes.

---

## 4. Jobs to be done

| User job | Success condition |
|---|---|
| “Help me understand what a mission must accomplish.” | User can explain a mission's science objective and at least one measurable requirement. |
| “Help me build a spacecraft that can do it.” | User selects subsystems and sees relevant mass/power/data/propulsion changes. |
| “Show me why this design is not feasible.” | Every failed constraint has a cause, affected subsystem, and repair path. |
| “Let me try a different trade-off.” | User can compare designs without losing the original baseline. |
| “Let me experience mission operations.” | User sees phases, telemetry, and meaningful decisions. |
| “Tell me what I learned from the result.” | Post-mission report links result to the original design and operating decisions. |
| “Let me show or reuse my work.” | User exports a versioned mission dossier. |

---

## 5. Product principles

### P1 — Science traces forward

An instrument is not selected just because its score is high. It must support a measurement requirement, and the requirement must support a science objective.

### P2 — Consequences trace backward

A low science return or missed milestone must identify the earlier design or operations decision that contributed to it.

### P3 — Hard limits are not negotiable

The system may let a player experiment with an invalid design, but it must never label the design mission-ready if a hard feasibility gate fails.

### P4 — Uncertainty is part of design

Display margin and plausible ranges. The best design is not always the single highest nominal score; robustness matters.

### P5 — Operations are a first-class design input

A design with no workable observing schedule, energy plan or downlink opportunity is incomplete.

### P6 — Scientific honesty over visual drama

A stylized orbit is not an ephemeris. A game cost is not NASA cost. A simplified thermal warning is not a thermal analysis. Label it.

### P7 — Explain before optimizing

Before adding an auto-optimizer, make it clear why the current design passes or fails.

---

## 6. Goals and non-goals

### 6.1 Hackathon goals

1. Deliver a complete mission design → validate → simulate → review loop.
2. Demonstrate at least one authentic JPL mission-data integration.
3. Show at least three meaningful cross-subsystem consequences.
4. Demonstrate a mission operations anomaly and a real trade-off decision.
5. Include provenance and fidelity labels for engineering data.
6. Provide a polished, coherent UI with a functioning fallback when external data is unavailable.
7. Keep the technical core reproducible and testable.

### 6.2 Non-goals

- Flight dynamics tool or engineering qualification package.
- High-fidelity multiphysics simulation.
- Full-fledged classroom LMS or account system.
- Real-time multiplayer.
- AI-generated physical laws, specifications, or unverified values.
- A NASA-branded or NASA-endorsed product.

---

## 7. Feature requirements and priority

Priority scale:

- **P0:** must ship for a credible submission.
- **P1:** should ship if P0 is stable.
- **P2:** stretch / post-hackathon.

| ID | Feature | Priority | User value | Required proof |
|---|---|---:|---|---|
| F-001 | Scenario selection and mission brief | P0 | Establishes purpose and constraints | User can start one of three scenarios |
| F-002 | Science objective editor | P0 | Defines why the mission exists | 2–4 objective selection/edit flow |
| F-003 | Objective → measurement → instrument traceability | P0 | Teaches science-to-system decomposition | Visible matrix or graph with missing links |
| F-004 | Component catalogue | P0 | Lets user make design choices | Select/change at least one option in each core subsystem |
| F-005 | Live mass budget | P0 | Makes resource constraints concrete | Values update on component change |
| F-006 | Propulsion / maneuver budget | P0 | Shows delta-v and propellant trade-offs | Rocket-equation model with tests |
| F-007 | Power and energy budget | P0 | Shows peak/average/eclipses or phase loads | Power margin and battery reserve update |
| F-008 | Communications and data budget | P0 | Exposes the data return bottleneck | Link margin, data produced, data returned and buffer |
| F-009 | Budget/cost estimate | P0 | Forces project trade-offs | Transparent cost breakdown and fidelity label |
| F-010 | Constraint explanation panel | P0 | Makes design repair actionable | Every fail/warning has reason and suggested action |
| F-011 | JPL asteroid target/mission data | P0 | Demonstrates real-world data | Server-side Mode A and/or Q with attribution and fallback |
| F-012 | Mission operations simulation | P0 | Completes the mission lifecycle | Six+ phases and event log |
| F-013 | Mission-control telemetry | P0 | Makes simulation legible | At least three channels update by phase |
| F-014 | Anomaly decisions | P0 | Creates consequential gameplay | Two or more branches with visible trade-offs |
| F-015 | Mission review / autopsy | P0 | Converts outcome into learning | Score breakdown, root causes, next-best changes |
| F-016 | Deterministic replay | P0 | Enables reproducibility and fair demo | Same seed/input => same output |
| F-017 | Offline demo mode | P0 | Protects demo from network/API failure | Saved snapshot works without external network |
| F-018 | 3D solar-system / spacecraft scene | P1 | Creates emotional impact and spatial context | 3D view plus 2D fallback |
| F-019 | Two/three-design comparison and Pareto view | P1 | Helps players explore alternatives | Side-by-side metrics and non-dominated designs |
| F-020 | Export mission dossier | P1 | Makes output shareable | JSON export; print/PDF view if time allows |
| F-021 | Guided tutorial / progressive hints | P1 | Lowers learning barrier | User can complete first mission with hints |
| F-022 | Monte Carlo robustness analysis | P1 | Makes uncertainty tangible | P10/P50/P90 or success-frequency view with sample count |
| F-023 | JPL Mode M porkchop map | P2 | Adds advanced trajectory trade study | Launch date/TOF heat map with version/provenance |
| F-024 | Team roles / collaborative mode | P2 | Supports classroom teamwork | Shared mission and role permissions |
| F-025 | Educator analytics / learning study | P2 | Measures educational outcomes | Opt-in pre/post assessment and session summary |
| F-026 | AI mission coach | P2 | Makes the product more adaptive | Retrieval-backed hints from verified knowledge only |

---

## 8. UX information architecture

### 8.1 Navigation

```text
Home
└── Select a Mission
    ├── Mission Brief
    │   ├── Science Objectives
    │   ├── Measurement Requirements
    │   └── Destination / Trajectory
    ├── Mission Architect
    │   ├── Launch & Structure
    │   ├── Propulsion
    │   ├── Power
    │   ├── ADCS
    │   ├── Instruments
    │   ├── Communications & Data
    │   ├── Thermal / Avionics
    │   ├── Ground Segment
    │   └── Live Budgets & Constraints
    ├── Trade Study
    ├── Mission Control
    │   ├── Mission Timeline
    │   ├── Telemetry
    │   ├── Event Log
    │   └── Decision Cards
    └── Mission Review
        ├── Science Returned
        ├── Engineering Performance
        ├── Budget and Margins
        ├── Risks Realized
        ├── Counterfactuals
        └── Export Dossier
```

### 8.2 First-run onboarding

Target completion time: 45–75 seconds before the player reaches the design screen.

1. Show one sentence describing the scenario.
2. Explain the objective and the mission's top three constraints.
3. Provide one recommended default architecture, clearly labeled “starter design.”
4. Ask the user to choose or confirm 2–3 science objectives.
5. Start in the architect with the first subsystem highlighted.

Avoid a long multi-page tutorial. Use contextual “why this matters” micro-lessons.

### 8.3 Mission architect screen

**Must show simultaneously:**

- Selected component and what it does.
- Key specifications with units and fidelity badges.
- Compatibility indicator.
- Cost delta.
- Live system budget changes.
- Constraint status.
- One-sentence explanation for the biggest trade-off.

A design edit should never silently alter another user selection. If compatibility requires a dependent replacement, ask for confirmation and show the affected values.

### 8.4 Constraint states

- **Pass:** requirement met with acceptable margin.
- **Watch:** feasible, but margin or uncertainty is concerning.
- **Fail:** hard limit or required capability is violated.
- **Not modelled:** data/model insufficient for a reliable numeric conclusion.

The UI must pair icon + text; do not use green/amber/red alone.

### 8.5 Mission-control screen

The screen should communicate that the mission is alive, without becoming a noisy arcade interface.

- Phase ribbon at the top.
- Mission elapsed time and current spacecraft mode.
- Stylized target/spacecraft view.
- Telemetry strip with current value, unit, trend and threshold.
- Event log with causal labels.
- Decision card with two or three actions, each with a clear consequence.

### 8.6 Mission review screen

Use a flight-readiness / post-flight review structure:

1. Mission outcome and one-sentence explanation.
2. Science objectives: achieved / partial / missed.
3. Science collected vs. successfully returned.
4. Engineering margin chart: mass, energy, delta-v, data, budget.
5. Operations timeline with anomaly decisions.
6. Main root causes, ranked by contribution.
7. “One change that would have changed the outcome” counterfactual.
8. Data provenance and model limitations.
9. Download dossier.

---

## 9. Learning design and evaluation

The product is a serious game, not just an entertainment simulator. Its educational structure should be explicit.

### 9.1 Learning outcomes

After one session, a learner should be able to:

- LO-1: Explain why science objectives become measurable instrument requirements.
- LO-2: Identify at least three coupled spacecraft constraints.
- LO-3: Explain the difference between mass, power, and energy budgets.
- LO-4: Explain why trajectory `C3` / hyperbolic excess energy is not interchangeable with spacecraft maneuver delta-v.
- LO-5: Explain why collecting data is not the same as returning data to Earth.
- LO-6: Identify how margin and uncertainty affect mission robustness.
- LO-7: Explain how an operations choice can preserve one mission objective while sacrificing another.

### 9.2 Teaching mechanics

- **Just-in-time explanation:** show a 2–4 sentence concept card when the user first encounters a metric.
- **Prediction prompt:** before committing a component, ask “Which budget do you expect to change?” Optional, not blocking.
- **Causal visualization:** highlight the affected budget tiles after an edit.
- **Trade-off challenge:** small objectives such as “increase data return by 20% without exceeding the power budget.”
- **Debrief:** compare the user's prediction with actual engine output and show the governing equation.
- **Mastery, not spend:** badges reward sound engineering actions such as retaining margin, tracing science requirements, or recovering from an anomaly—not expensive component choices.

### 9.3 Evaluation approach

Use an optional three-question pre-check and post-check mapped to learning outcomes. Do not claim learning impact from a single hackathon demo. Record only anonymous aggregate metrics if the team has a privacy notice and consent.

Suggested measures:

- Mission completion rate.
- Percentage of users who can identify an instrument's objective traceability.
- Number of subsystem trade-offs correctly predicted.
- Change in concept-check responses.
- Percentage who can explain the mission's top failure cause after debrief.

The 2026 engineering-game systematic review finds promising educational uses but notes that robust evaluation is still uncommon. Present this as a prototype with an evaluation plan, not as proven educational efficacy.

---

## 10. Mission scenario specifications

### 10.1 NEO Rendezvous — “Echoes of Origins” (flagship)

**Narrative:** A robotic scout is sent to a near-Earth object to characterize its surface, composition and physical environment. The team must choose a feasible target and mission opportunity, then return useful data despite resource and operations constraints.

**Player decisions:**

- Target and launch opportunity.
- Arrival time / time of flight.
- Spacecraft dry mass and propulsion architecture.
- Optical / spectral / thermal / field instruments.
- Power generation and storage.
- ADCS pointing capability.
- RF antenna / transmitter / ground network.
- Observation timeline and downlink schedule.

**Science objectives (example set):**

- Determine surface morphology and shape.
- Characterize visible/near-infrared spectral properties.
- Measure thermal behaviour across local time.
- Characterize local magnetic/plasma environment (optional extension).

These are scenario objectives, not a claim about any particular real asteroid mission.

**Primary constraints:**

- A valid target opportunity exists for the chosen launch window.
- Launch energy is within the selected launch envelope (if available in the curated dataset).
- Spacecraft maneuver delta-v is sufficient for its explicitly modelled maneuvers.
- Total mass fits the launch option's selected reference envelope.
- Power and energy plan supports the observation sequence.
- Communication plan can return a useful fraction of the data.

**Narrative events:** launch injection dispersion, delayed commissioning, uncertain target illumination, pointing drift, missed contact, unexpected data backlog, safe-mode entry.

**Data source rule:** JPL mission data are source-backed only for the parameters actually returned by JPL. The spacecraft design, cost, subsystem performance and scenario events retain their own provenance class.

### 10.2 Lunar Polar Scout — “Shadowline”

**Narrative:** A small robotic mission scouts a lunar polar region for surface and illumination observations. The team must make a viable power and communication plan while balancing payload and mobility/landing constraints.

**Primary constraints:** power availability, energy storage, communication opportunities, thermal survival risk, payload mass and selected scenario delta-v.

**Fidelity:** curated educational scenario. No high-fidelity lunar transfer, descent guidance or surface thermal model in the MVP.

### 10.3 Earth Observation — “Blue Sentinel”

**Narrative:** A compact satellite collects repeated observations of a changing Earth system. The team balances spatial detail, revisit/coverage proxy, pointing, power, data volume and downlink.

**Primary constraints:** launch mass, orbit preset, payload data rate, energy, pointing and ground-contact capacity.

**Fidelity:** simplified circular two-body orbit with transparent assumptions; coverage is an educational proxy.


### 10.4 Mandatory implementation architecture: Python engineering core

MISSIONFORGE's **main architecture must be implemented in Python**. This is a product-level implementation constraint, not an optional stack preference.

- **Python 3.12+ / FastAPI / Pydantic v2** own the canonical `MissionState`, catalogue and analysis schemas, unit/provenance validation, engineering calculations, hard-constraint evaluation, traceability graph, Pareto exploration, Monte Carlo robustness, Bayesian science_belief updates, onboard autonomy policies, observation/downlink scheduling, mission simulation, telemetry health monitoring, mission analysis and JPL integration.
- Keep the engineering/domain modules under `backend/app/domain/` pure and deterministic. FastAPI routes and application services orchestrate these modules; they must not contain equations or duplicate domain rules.
- The **Next.js / React / TypeScript frontend** is the presentation layer: screens, forms, client-side navigation, visualizations, charts, accessibility and local draft/save UX. It calls the Python API for authoritative outputs. It must not reimplement the engineering models or run a parallel TypeScript mission engine.
- Pydantic models and FastAPI's generated OpenAPI document are the canonical API contracts. Generate or derive TypeScript client types from OpenAPI instead of maintaining separate hand-written mission/domain interfaces.
- Keep one Python modular-monolith backend. Do not split the engine, simulator, optimizer, scheduler or JPL adapter into separate microservices for the hackathon.
- Python tests use `pytest`; frontend journey tests may use Playwright. Every physics/domain test must exercise the Python implementation.

The UI may perform harmless presentation calculations (formatting, chart scaling, form validation for immediate feedback), but all engineering values, feasibility decisions, scores, simulation outcomes and recommended architectures returned to the player must originate from the Python backend.

---

## 11. Game scoring and progress

### 11.1 Score weights

| Dimension | Weight | Desired player behaviour |
|---|---:|---|
| Scientific return | 30% | Meet objectives and return usable data |
| Mission execution | 25% | Complete critical phases and objectives |
| Engineering robustness | 20% | Maintain margins, manage risk, recover faults |
| Resource stewardship | 15% | Stay within budget and manage finite resources |
| Operations quality | 10% | Schedule work, communicate, and respond well |

### 11.2 Hard-feasibility gate

A design with a failed hard constraint cannot earn “mission-ready” status, even if its weighted score is high. During gameplay, an infeasible mission can still be launched in “experimental” mode for learning, but the review page must state the violated assumptions and limits.

### 11.3 Progression

- First mission: guided defaults and two science objectives.
- Second mission: reduced hints and a more challenging trade.
- Advanced mission: optional uncertainty analysis and multiple target opportunities.

No progression should require payment, account creation or hours of play.

---

## 12. Product analytics and success metrics

### 12.1 Hackathon product metrics

| Metric | Target for demo/rehearsal | Why it matters |
|---|---:|---|
| Time from landing to editable mission | < 90 seconds | Low friction |
| Complete first mission design flow | < 6 minutes | Core loop comprehensible |
| Live analysis response | < 100 ms local p95 | Interaction feels immediate |
| Components with provenance | 100% of displayed numeric specs | Trust |
| Failed constraints with explanation | 100% | Explainability |
| Simulation phases | 6+ | End-to-end completeness |
| Meaningful anomaly decisions | 2+ | Operations gameplay |
| Deterministic replay | 100% of seeded fixtures | Demo repeatability |
| Offline demo completion | 100% of core journey | Resilience |

### 12.2 Optional anonymous event schema

If analytics are approved, use minimal events:

```ts
type ProductEvent =
  | { type: "scenario_started"; scenarioId: string }
  | { type: "objective_selected"; objectiveId: string }
  | { type: "component_changed"; category: string; componentId: string }
  | { type: "constraint_failed"; constraintId: string }
  | { type: "simulation_started"; seed: number }
  | { type: "decision_made"; eventId: string; choiceId: string }
  | { type: "mission_reviewed"; outcome: string; scoreBand: string };
```

Do not capture free text or personally identifying data. Analytics are not required for the hackathon MVP.

---

## 13. Acceptance criteria (product-level)

### AC-01: Mission briefing

Given a user opens the app, when the user selects any supported scenario, then the app shows a mission purpose, destination, objective set, top constraints, and a starter design.

### AC-02: Science traceability

Given a mission has one or more science objectives, when the user opens the science view, then every selected instrument shows which measurement requirement and objective it supports; unsupported requirements are marked missing.

### AC-03: Coupled design response

Given a valid mission state, when the user adds an instrument with non-zero mass, power and data-rate attributes, then mass, power, data budget, cost and science coverage recalculate; all outputs identify their units and fidelity.

### AC-04: Hard feasibility

Given a selected launch mass limit, when allocated mass exceeds it, then mission feasibility is not “feasible,” the constraint panel explains the exceedance, and the score cannot show “mission-ready.”

### AC-05: Propulsion correctness

Given an Isp, dry mass and maneuver delta-v requirement, when the propulsion model calculates propellant mass, then the output agrees with an independent rocket-equation test vector within defined tolerance.

### AC-06: Power correctness

Given component loads and duty cycles, when power is analyzed, then peak load and energy over the selected scenario window are reported separately; eclipse energy and battery reserve are checked.

### AC-07: Link/data correctness

Given a range, frequency, transmitter, antenna and data rate, when the communications model runs, then it reports path loss, link margin and downlink capacity; generated data is not counted as science returned until successfully downlinked.

### AC-08: JPL data use

Given the NEO scenario has network access, when the user requests accessible targets, then server-side code queries the JPL adapter and displays source/provenance. If the adapter is unavailable, a dated cached/demo response is clearly identified.

### AC-09: API policy

Given multiple browser clients request JPL data at once, then the adapter queues upstream calls serially, uses cached identical requests, identifies itself with the app-specific User-Agent, and applies backoff to retryable errors.

### AC-10: Mission operations

Given a feasible or experimental design, when simulation begins, then the user sees six or more phases and telemetry updates. At least two events offer choices with distinct measurable consequences.

### AC-11: Reproducibility

Given the same mission JSON, engine version, catalogue version, event-set ID and seed, when simulation is run twice, then the serialized result is identical.

### AC-12: Mission autopsy

Given a simulation has completed, when the user opens the review, then the app shows science collected vs. returned, score dimensions, resource margins, realized risks, causal explanations, and at least one counterfactual design action.

### AC-13: Export

Given a mission review is open, when the user exports, then a valid versioned JSON dossier is downloaded and can be re-imported without data loss.

### AC-14: Accessibility and fallback

Given a device does not support WebGL or the user prefers reduced motion, when the mission page loads, then the user can complete the core journey with a 2D/low-motion presentation.

---

## 14. Demo narrative and judging strategy

### 14.1 Recommended 5-minute narrative

**0:00–0:30 — Hook**  
“We are not building a spacecraft parts picker. We are making the mission's science, engineering, and operations one connected system.”

**0:30–1:15 — Authentic data**  
Open the NEO mission. Show a JPL-derived target or stored mission option, its departure/arrival date and the source badge. Mention that API access is server-side, cached, and version-checked.

**1:15–2:15 — System trade-off**  
Add a spectral instrument. Show the mission's mass, average/peak power and downlink data changing. Point to the measurement requirement that justifies the instrument.

**2:15–3:00 — Engineering repair**  
Show a data or power failure. Change the observing duty cycle or communications architecture. Explain why the selected action resolves one constraint but has a cost elsewhere.

**3:00–4:00 — Fly the mission**  
Start the seeded simulation. Show mission phases and telemetry. Resolve a predictable anomaly caused by the design/operations plan.

**4:00–5:00 — Mission autopsy**  
Show science collected vs. returned, score breakdown, margins, source fidelity and a counterfactual. Finish with the insight that a mission's objective is not to collect the most data, but to return the right data reliably.

### 14.2 What judges should remember

- It is a coherent end-to-end mission lifecycle, not isolated calculators.
- It incorporates real JPL mission opportunity data where applicable.
- It uses a single typed mission model and traceability.
- Every subsystem has consequences elsewhere.
- It exposes uncertainty and assumptions rather than hiding them.
- It is built to be extended with additional mission classes and data adapters.

### 14.3 Demo safety plan

- Always keep a local seeded mission snapshot.
- Pre-load a known JPL target result and show retrieval time.
- Run the entire presentation once on the exact judging laptop/browser.
- Keep a 2D screenshot/scene fallback for WebGL issues.
- Have a 60-second backup video or screen recording if the event venue network fails.

---

## 15. Roadmap and schedule strategy

For a short hackathon, plan against milestones rather than assuming a fixed number of people or hours.

| Stage | Deliverable | Gate to proceed |
|---|---|---|
| Foundation | Typed mission state, catalogue, working app shell | One scenario loads |
| Engineering core | Mass, propulsion, power, communications, data, science | Unit test vectors pass |
| Design journey | Architect screen + live constraints | One component change visibly changes connected budgets |
| Real data | JPL Mode A/Q adapter + cache + snapshot | Live/cached/demo source status works |
| Simulation | Phases, telemetry, seeded events, choices | Same seed is reproducible |
| Review | Score, science return, root cause, counterfactual | Review explains a successful and a failed run |
| Polish | Three scenarios, 3D view, responsive layout, export | Full demo rehearsed offline |

### Cut order when time is short

Keep: domain correctness, one full vertical slice, JPL integration with fallback, mission simulation, source attribution, review.  
Cut first: full Mode M interactive map, team collaboration, complex 3D animation, AI assistant, broad catalogue, optimizer beyond small trade studies.

---

## 16. Risks and mitigations

| Risk | Likelihood / impact | Mitigation |
|---|---|---|
| Over-scoping physics | High / High | Tiered fidelity; use JPL computed trajectories; limit in-house models to transparent first-order equations |
| Inaccurate or unsourced catalogue values | Medium / High | Provenance required in schema; source audit; label game estimates |
| JPL API unavailable / rate-limited | Medium / High | Server queue, TTL cache, fallback snapshot, offline demo |
| JPL API schema changes | Low / High | `signature.version` check, Pydantic validation, unknown-version fallback |
| Agents change shared types inconsistently | High / High | Single contract owner, protected files, vertical-slice merges |
| Physics model hides impossible designs | Medium / High | Independent test vectors; hard constraints separate from score |
| Visual work delays working product | High / Medium | Ship text/table/2D core before 3D polish |
| Mission simulation feels random | Medium / High | Seeded PRNG; events trace to design vulnerabilities or declared scenario events |
| User cannot understand terminology | Medium / Medium | Contextual micro-lessons, defaults, unit tooltips, guided scenario |
| Demo network/WebGL failure | Medium / High | Cached data, local seeded run, 2D fallback, recorded backup |
| Misleading NASA affiliation | Low / High | Independent-project disclaimer; no official logo/seal; proper attribution |

---

## 17. AI-agent delivery governance

### 17.1 Source of truth hierarchy

1. `architecture.md` — technical and calculation contracts.
2. `prod.md` — user behaviour and product acceptance.
3. `README.md` — run and contributor instructions.
4. Python/Pydantic domain and API models in `backend/app/` — executable source-of-truth contracts; frontend TypeScript types are generated from FastAPI OpenAPI.
5. Individual agent assumptions — never override the above without a documented design decision.

### 17.2 Protected files

Only the integration owner may change:

- `backend/app/schemas/mission.py`
- `backend/app/schemas/mission.py`
- `backend/app/schemas/catalog.py`
- `backend/app/schemas/analysis.py`
- `package.json` and lockfile
- API envelope types

Agents may request a contract change with: reason, affected modules, migration impact, and tests.

### 17.3 Code review checklist

- Is the feature tied to a product requirement ID?
- Does it preserve the fidelity/provenance rules?
- Are units explicit and consistent?
- Is domain code pure and deterministic?
- Are invalid values rejected rather than coerced silently?
- Does UI explain the result?
- Are loading/offline/error/empty states handled?
- Are tests added for normal, edge, and failure cases?
- Did the agent add dependencies or change contracts unnecessarily?

---

## 18. Release checklist

### Product

- [ ] Scenario brief tells a coherent science story.
- [ ] Science objectives trace to measurements and instruments.
- [ ] Design page shows coupled budgets.
- [ ] Hard constraint status is unmistakable.
- [ ] Mission simulation has meaningful operator decisions.
- [ ] Post-mission report explains success/failure.

### Engineering

- [ ] Python backend type/lint checks pass; frontend TypeScript checks pass.
- [ ] Lint, unit, contract, integration and build checks pass.
- [ ] Engineering equations have independent test vectors.
- [ ] JPL adapter uses server-side request, serial queue, cache, User-Agent and version check.
- [ ] No direct client-to-JPL fetch.
- [ ] Offline snapshot path works.
- [ ] Reproducibility check passes.

### Trust and communication

- [ ] Every spec and number has provenance or explicit gameplay estimate label.
- [ ] NASA/JPL sources are attributed.
- [ ] App says it is an independent educational prototype.
- [ ] No flight-readiness or mission-certification claim.
- [ ] Data limitations are visible in the report.

### Demo

- [ ] Fresh start works.
- [ ] One successful run rehearsed.
- [ ] One failed / recovered run rehearsed.
- [ ] Network-offline path rehearsed.
- [ ] 2D fallback rehearsed.
- [ ] Dossier export works.

---

## 19. Research bibliography and evidence-to-feature map

1. NASA, *Systems Engineering Handbook*, NASA/SP-2016-6105 Rev. 2 — requirements, lifecycle, verification and technical management. https://www.nasa.gov/reference/systems-engineering-handbook/
2. Marcus, Legesse & Richardson, *A Model-Based Framework for NASA Science Mission Formulation* (2023) — digital system model, STM/MTM, MEL, requirement architecture and automated consistency. https://ntrs.nasa.gov/citations/20220019154
3. Zadeh & Shirazi (2017), *Multidisciplinary design optimization architecture to concurrent design of satellite systems* — concurrent coupling of mission analysis, payload, structures, ADCS, communications, C&DH, power and thermal. https://doi.org/10.1177/0954410016665412
4. *Large-Scale Multidisciplinary Optimization of a Small Satellite’s Design and Operation* (2014) — coupled design and operations optimization. https://doi.org/10.2514/1.A32751
5. *Preliminary space mission design under uncertainty* (2009) — robust mission design and uncertainty treatment. https://doi.org/10.1016/j.actaastro.2009.09.005
6. NASA, *State-of-the-Art of Small Spacecraft Technology* (2026) — current public subsystem state-of-the-art and technology survey. https://www.nasa.gov/smallsat-institute/sst-soa/
7. JPL, *Small-Body Mission Design API* v1.2 — accessible small bodies, stored mission options, porkchop data, orbit-neighbour screening. https://ssd-api.jpl.nasa.gov/doc/mdesign.html
8. NASA VISITOR, LAR-18538-1 — modular conceptual interplanetary trajectory modelling, mass, launch window and operations. https://software.nasa.gov/software/LAR-18538-1
9. JPL, *Telecommunications Link Design Handbook 810-005* — spacecraft/DSN communications link engineering parameters. https://deepspace.jpl.nasa.gov/dsndocs/810-005/
10. *Games for teaching and training decision-making in engineering: a systematic literature review* (2026) — learning and decision-making design. https://doi.org/10.1080/03043797.2026.2672137
11. *Gamification in engineering education – An empirical assessment on learning and game performance* (2020). https://doi.org/10.1016/j.heliyon.2020.e04972
12. *Design of serious games in engineering education* (2022) — intended learning outcomes and alignment with gameplay mechanics. https://doi.org/10.1016/j.cirpj.2021.11.006
13. *From Classroom to Cosmos: The Impact of Space Teams Academy on Engineering Education* (2023) — virtual space-mission experiences and STEM learning. https://doi.org/10.1109/FIE58773.2023.10343490
14. Zandbergen, *Spacecraft bus design and sizing* (TU Delft, 2020; repository record). https://resolver.tudelft.nl/uuid:a2f8269f-fa26-4448-b7b5-2b549dcd1732

The sources inform the product's structure and educational method. Specific component numbers must be checked against the primary source's latest edition before appearing as source-backed catalogue values.

---

## 20. Advanced product features and release priority

The product should feel ambitious because the features reinforce one another, not because it has a long menu. All research-derived features must be introduced as transparent educational analogues of the referenced research methods.

### 20.1 Feature requirements

| ID | Feature | Priority | User-visible result | Acceptance criterion |
|---|---|---|---|---|
| FR-15 | Mission architecture graph | P0 | Interactive science-to-system dependency map | Selecting an objective highlights requirements, instruments, subsystem loads and science products |
| FR-16 | Causal impact explanation | P0 | “Why did this number change?” explanation | A component edit lists all affected outputs and constraint deltas |
| FR-17 | Mission Design Arena | P0 | Lean, Science-max and Resilient candidate designs | At least 100 deterministic candidates; all recommendations are feasible; each recommendation explains its objective |
| FR-18 | Pareto frontier | P0 | Scatter plot of non-dominated designs | Candidate dominance is unit-tested; users can load a point into Architect |
| FR-19 | Robustness Lab | P0/P1 | Chance-of-feasibility proxy with quantile bands | 100–250 seeded samples; Wilson interval; explicit model limitations |
| FR-20 | Science hypothesis tracker | P1 | Belief/probability update after a science observation | Valid Bayesian posterior and readable update explanation |
| FR-21 | Onboard autonomy policy | P1 | A spacecraft decision during comm blackout | Ground actions blocked during blackout; selected policy action respects constraints |
| FR-22 | Science/downlink schedule | P1 | Unified observation and contact timeline | Buffer, energy, capacity and time-window constraints enforced |
| FR-23 | Predictive health monitor | P1 | Telemetry anomaly with residual evidence | Threshold + EWMA + persistence; deterministic event and explanation |
| FR-24 | Mission Analyst | P1/P2 | Ranked counterfactual design recommendations | Recommendations computed from engine mutations; no LLM-generated values |
| FR-25 | Mission Evidence Passport | P0/P1 | Exportable mission engineering record | Includes sources, assumptions, versions, seeds, science traceability and decisions |
| FR-26 | Optional LLM narration | P2 | Natural-language mission briefing | LLM can only paraphrase validated JSON facts; deterministic fallback works offline |

### 20.2 Priority interpretation

- **P0:** must ship for a credible core product. If time is extremely limited, deliver graph/impact, a compact Pareto explorer and a basic dossier before decorative features.
- **P1:** the standout mission experience. Science belief, onboard autonomy, unified data scheduling and robustness should be built in a single thin vertical slice for the flagship scenario.
- **P2:** enhancement only. The product must be complete without an LLM, advanced trajectory solver, real-time external service or PDF generation.

### 20.3 Signature player journey: discover and adapt

Use one flagship storyline so the advanced features feel like one coherent mission rather than independent demos:

1. The player receives a scientific question about an asteroid target and chooses measurement requirements.
2. The architecture graph demonstrates which instrument can satisfy each requirement.
3. The design arena reveals three feasible but differently optimized spacecraft.
4. The player selects the robust architecture and checks the sensitivity of feasibility to uncertain parameters.
5. During target operations, an instrument observation updates a synthetic science belief distribution.
6. Ground contact is unavailable. The preloaded autonomy profile selects the most useful follow-up observation without violating battery/data constraints.
7. The schedule board shows the operational reason the choice is feasible.
8. The mission review distinguishes what was observed, what was inferred, what was returned, what was lost, and how confident the simulation is.

The science labels, observation likelihoods and hidden scenario truth are synthetic gameplay data, not claims about a real asteroid. JPL mission data supplies the target/trajectory context only.

---

## 21. Product experience additions

### 21.1 Mission Design Arena

The arena is a comparison-first screen. It must not look like a generic leaderboard.

- Left: objective selector and hard constraints.
- Centre: Pareto plot with selectable design points.
- Right: Lean / Science-max / Resilient candidate summaries.
- Bottom: candidate comparison table including cost, dry mass, total delta-v budget, energy margin, downlink capacity, expected science returned, probability-feasible proxy and uncertainty interval.

Clicking a point opens its design state. A side-by-side compare mode explains which subsystem differences cause the trade. Do not reduce multi-objective choice to a single weighted number without showing the weights.

### 21.2 Science Evidence View

Show:

- hypothesis cards with prior/posterior percentages;
- observation history and instrument identity;
- likelihood explanation for the observed outcome;
- entropy/information-gain change;
- what new observation would most reduce uncertainty;
- whether the result was actually downlinked to Earth.

Use probability bars and a simple evidence timeline. Do not present a posterior as factual certainty; it is conditional on the scenario's hypothesis set and likelihood model.

### 21.3 Autonomous Mission Control

The simulation control room must visibly distinguish `GROUND CONTROL` from `ONBOARD AUTONOMY`. During blackout:

- disable ground command controls;
- show the blackout countdown / time-to-contact as scenario data;
- display the onboard policy and candidate actions;
- show why the selected action wins its utility comparison;
- expose power, storage, pointing and thermal constraints;
- log the autonomous action for later audit.

The player should understand that the spacecraft follows a preplanned policy; it does not receive a magical live internet connection or real-time Earth instruction.

### 21.4 Mission Evidence Passport

Provide an export button on the final review. The dossier should include a compact executive summary, STM/MTM, selected architecture, Pareto alternatives, risk/robustness findings, observations, downlink, anomalies, autonomy choices, final science return, assumptions and sources. Include a machine-readable JSON export for reproducibility. HTML/Markdown export is sufficient for the hackathon; PDF is optional.

---

## 22. Revised acceptance tests

Add the following acceptance criteria to AC-01 through AC-14.

### AC-15 — Causal architecture graph

Given a mission with an objective, measurement requirement and instrument, when the instrument is removed, the graph marks the requirement uncovered and the objective's expected coverage falls. Every graph edge has a meaningful relationship type and a readable rationale.

### AC-16 — Pareto and design archetypes

Given a fixed mission baseline and seed, the arena generates at least 100 candidates or all available legal combinations when fewer exist. It identifies a non-dominated feasible set and displays Lean, Science-max and Resilient representatives. Reopening the same mission with the same seed gives identical output.

### AC-17 — Robustness interpretation

The robustness view displays sample count, seed, probability-feasible estimate, Wilson interval, metric quantiles, failure reasons and distribution assumptions. It explicitly states that the result is a game-level Monte Carlo proxy, not a flight risk estimate.

### AC-18 — Bayesian science update

After a valid observation outcome, hypothesis probabilities sum to 1 within tolerance and change according to the scenario likelihood table. The interface displays the prior, evidence and posterior. The result is labeled conditional on the scenario model.

### AC-19 — Blackout autonomy

During a communication blackout, ground commands cannot alter the plan. One of the preloaded policies selects a feasible candidate action, and the mission log captures inputs, candidate utilities, selected action and reason.

### AC-20 — Science/downlink schedule integrity

The schedule accounts for observation windows, contact windows, generated bits, data buffer capacity, contact capacity, power and any configured slew penalty. No silent buffer overflow or impossible downlink is allowed.

### AC-21 — Telemetry anomaly explainability

When a seeded anomaly occurs, the dashboard displays raw signal, expected envelope, residual, EWMA, persistence count and detector threshold. The fired detector maps to a mission event and recovery choice.

### AC-22 — Evidence Passport

The exported passport contains mission inputs, engine/catalogue/scenario versions, seed, provenance, objective traceability, final budgets, uncertainty assumptions, observations, data returned, anomalies, autonomy decisions and limitations. Importing the machine-readable mission JSON reproduces the same deterministic nominal run.

### AC-23 — LLM independence

The full core mission journey remains operable with no LLM provider configured and no network connection. LLM narration, if present, cannot change mission state or the numerical engine output.

---

## 23. Updated judging narrative and differentiators

The team should not claim that MISSIONFORGE is a NASA-grade design tool. It should claim something more credible and compelling: an evidence-aware educational mission-engineering game where research ideas become visible, interactive trade-offs.

### The judge should see five things

1. **Scientific intent:** the game starts from a science question and makes the requirement traceable.
2. **Engineering consequence:** components affect multiple budgets through one calculation model.
3. **Design-space intelligence:** the player sees a Pareto set, not one simplistic score.
4. **Autonomous science:** new evidence changes the plan while communication is unavailable.
5. **Trust:** calculations, uncertainty, sources, seeds and limitations are inspectable and exportable.

### Suggested single-slide project claim

> MISSIONFORGE turns space mission engineering into an evidence-aware, playable digital mission twin: design a spacecraft, explore its Pareto trade-offs, test its robustness, and watch it autonomously adapt its science plan when the unexpected happens.

Use no NASA logo or visual treatment that implies endorsement. Display the independent educational prototype disclaimer in the app and submission materials.

---

## 24. Scope lock and cut-order rules

The following order protects the winning story if integration time collapses:

1. Keep the end-to-end scenario and a working science-to-component trace.
2. Keep one high-quality coupled analysis engine and hard feasibility checks.
3. Keep a compact Pareto frontier with three meaningful archetypes.
4. Keep deterministic seeded simulation and a mission debrief.
5. Keep the science belief + blackout autonomy moment if its thin slice is stable.
6. Keep a 100-sample robustness display, even if the full uncertainty profile is simplified.
7. Keep a source-aware export/dossier.
8. Cut LLMs, advanced global trajectory optimization, multi-spacecraft operations, login, persistent cloud database, voice, multiplayer and elaborate 3D effects first.

Never try to finish every research-inspired feature superficially. A coherent working chain is stronger than many isolated mock screens.

---

## 25. Research review and evidence references

See `research_basis.md` for the annotated paper summaries and source-to-feature implementation map. New high-value sources include:

- Guirguis et al. (2026), *POMDPs for Autonomous Science Exploration*, arXiv:2608.03155.
- Kim et al. (2025), *Adaptive Science Operations in Deep Space Missions Using Offline Belief State Planning*, arXiv:2510.08812.
- Babapour & Taheri (2026), *Robust Spacecraft Low-Thrust Trajectory Design: A Chance-Constrained Covariance-Steering Approach*, arXiv:2601.17629.
- Iijima et al. (2026), *Global Optimization Framework for Automated Low-Thrust Gravity-Assist Trajectory Design*, arXiv:2609.09515.
- Bussemaker & Firchau (2025), *System architecture optimization: an example application to space mission planning*, DOI 10.1007/s12567-025-00626-7.
- Schmitt et al. (2025), *Design of space systems and operational mission architectures using sandbox games*, DOI 10.1016/j.actaastro.2025.04.004.
- Levinson et al. (IJCAI 2025), *Optimal Planning to Coordinate Science Data Collection and Downlink...*, DOI 10.24963/ijcai.2025/950.
- Goetze et al. (2025 conference / arXiv 2026), *Deep Learning-Based Anomaly Detection in Spacecraft Telemetry on Edge Devices*, DOI 10.1109/SCC66396.2025.00019.
- IEEE Access (2026), *Advancing Engineering Education Through Serious Games*, DOI 10.1109/ACCESS.2026.3669416.
- NASA, *State-of-the-Art of Small Spacecraft Technology*, 2026 online edition, publicly available technology information through April 1, 2026.


## 26. Final product definition

MISSIONFORGE is successful when a first-time player can answer three questions after the experience:

1. **What science was the mission trying to achieve?**
2. **Which engineering trade-offs made that science possible or impossible?**
3. **What would I change before flying the mission again?**

If the team delivers that loop with authentic data, defensible calculations, explicit uncertainty, and a polished mission-control experience, it will be a stronger hackathon entry than a much larger but shallow spacecraft game.
