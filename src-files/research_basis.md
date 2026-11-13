# MISSIONFORGE — Research Basis & Evidence-to-Feature Review

**Version:** 1.0  
**Review date:** 2026-10-31  
**Purpose:** An annotated research review translating open research and NASA technical references into an implementable hackathon product.  
**Important:** The project is an independent educational prototype. Research methods below motivate product features; simplified implementations must not be described as reproductions of the full research methods.

---

## 1. Executive synthesis

MISSIONFORGE should be built around five research-backed ideas:

1. **Model-based engineering:** one coherent digital mission model keeps science objectives, requirements, equipment, budgets and operational plans consistent.
2. **Multi-objective design-space exploration:** the result should be a set of non-dominated architectures, not one arbitrary high score.
3. **Robustness under uncertainty:** feasibility should be evaluated under sampled variations, not only one nominal input set.
4. **Science-aware autonomy:** observations update beliefs and can change the next onboard science action during communication blackout.
5. **Integrated science and downlink scheduling:** collection is only valuable when resources and contact opportunities permit the data to be stored and returned.

Three supporting ideas make the experience more complete: transparent telemetry health monitoring, pedagogically grounded serious-game evaluation, and evidence/provenance passports.

The recommended build is not a full operational research suite. It is a carefully bounded interactive analogue that uses the same conceptual structure, exposes assumptions, and includes known-answer tests.

**Implementation architecture decision:** MISSIONFORGE's main mission architecture is implemented in Python. The canonical mission model and all engineering analysis, optimization, uncertainty, belief-state/autonomy, scheduling, simulation and telemetry logic belong in a Python domain/backend package (FastAPI + Pydantic). The Next.js/TypeScript application is only the user interface and visualization client. Each research-derived method below must be translated into testable Python modules; do not create parallel TypeScript implementations of these algorithms.

---

## 2. Primary research papers

### 2.1 Model-based mission formulation — NASA NTRS

**Source:** Marcus, M. L., Legesse, H. A., and Richardson, D. H., *A Model-Based Framework for NASA Science Mission Formulation* (2023 manuscript).  
**Link:** https://ntrs.nasa.gov/citations/20220019154  
**Research contribution:** A digital system model / system architecture model used early in formulation can maintain mission requirements, subsystem structure, Master Equipment List (MEL), Science Traceability Matrix (STM), Mission Traceability Matrix (MTM), key performance parameters and simulation artifacts in a connected model. This makes inconsistencies visible earlier and supports trade studies.

**MISSIONFORGE translation:**

- Maintain one canonical Python/Pydantic mission state in the backend.
- Generate equipment lists, objective traceability and mission traceability as views from the same source.
- Show each component's upstream reason (science requirement) and downstream consequences (mass, power, data, pointing, cost, returned science).
- Export an auditable mission dossier.

**What not to claim:** MISSIONFORGE is not a SysML or NASA pre-formulation environment. It borrows the consistency and traceability principle for a smaller educational model.

### 2.2 System architecture optimization — Pareto front

**Source:** Bussemaker, J. H., and Firchau, T., *System architecture optimization: an example application to space mission planning*, CEAS Space Journal, published 18 June 2025; volume 18 (2026), pages 737–745.  
**Link:** https://doi.org/10.1007/s12567-025-00626-7  
**Research contribution:** The paper models mission- and spacecraft-level decisions as an architecture design space with function-component allocation decisions, component variables, constraints and system objectives. It uses NSGA-II to explore the space and obtain a Pareto front trading system mass against experiment duration / scientific value.

**MISSIONFORGE translation:**

- Generate an explicit set of candidate spacecraft configurations.
- Keep hard feasibility checks separate from soft objectives.
- Compute the non-dominated set using transparent Pareto dominance.
- Offer three understandable archetypes: Lean, Science-max and Resilient.
- Let the user inspect, compare and load each candidate into the architect.

**Hackathon simplification:** Start with seeded candidate generation, catalog substitutions and O(n²) non-dominated sorting over 100–250 candidates. NSGA-II is a stretch task. Do not claim to have implemented the paper's ADSG / ADORE toolchain.

### 2.3 Sandbox games joined to higher-fidelity mission models

**Source:** Schmitt, R. N., Becker, M. F., DeLaurentis, D., and Oguri, K., *Design of space systems and operational mission architectures using sandbox games*, Acta Astronautica 234 (2025), pages 41–58.  
**Link:** https://doi.org/10.1016/j.actaastro.2025.04.004  
**Research contribution:** The paper proposes coupling intuitive sandbox-game interactions with higher-fidelity mission engineering and astrodynamics representations. Its examples include object-oriented system-of-systems architectures and a differential-corrections targeter for the circular restricted three-body problem, exploring mission complexity, cost and time-of-flight.

**MISSIONFORGE translation:**

- Keep the UI playful and spatial, but route every component edit into the same engineering model.
- Use the visual scene as a front-end to the model, not an isolated toy physics layer.
- Show architecture complexity and operational implications alongside cost and science return.
- Make the mission-design sandbox and the mission-control simulator share one architecture state.

**Hackathon simplification:** Use curated trajectory choices/JPL stored mission options and educational budgets. Do not attempt CR3BP differential correction in the browser.

### 2.4 Science-hypothesis planning under partial observability

**Source:** Guirguis, D., Wallace, N., Kurniawati, H., and Sukkarieh, S., *POMDPs for Autonomous Science Exploration*, arXiv:2608.03155, 4 August 2026.  
**Link:** https://arxiv.org/abs/2608.03155  
**Research contribution:** The paper introduces a Science Hypothesis Map POMDP that reasons over inferred physical properties rather than branching on huge raw observation spaces. Its aim is to preserve uncertainty while making science-driven planning computationally tractable. It discusses exploration under observation uncertainty and limited communication, where new findings should influence replanning.

**MISSIONFORGE translation:**

- Represent a small set of competing science hypotheses and belief probabilities.
- Use measurement outcome likelihoods to update the belief state with Bayes' rule.
- Calculate entropy and expected information gain for candidate observations.
- During comm blackout, select the next observation that improves expected science while respecting resources.

**Hackathon simplification:** Use 3–8 hypotheses and a finite candidate set with deterministic one-step look-ahead. Likelihood matrices and hidden truth are synthetic gameplay data. This is not a full POMDP or SHM-POMDP implementation.

### 2.5 Offline belief-state planning for deep-space science operations

**Source:** Kim, G. R., Warner, H., Eddy, D., Astle, E., Booth, Z., Balaban, E., and Kochenderfer, M. J., *Adaptive Science Operations in Deep Space Missions Using Offline Belief State Planning*, arXiv:2510.08812, 9 October 2025.  
**Link:** https://arxiv.org/abs/2510.08812  
**Research contribution:** Presents a POMDP framework for adaptively sequencing science instruments when communication delays prevent real-time human intervention. A Bayesian network structures measurement dependencies; offline policies are generated and evaluated for resource-aware operations. The paper reports a case study based on the proposed Enceladus Orbilander life-detection suite.

**MISSIONFORGE translation:**

- Allow players to choose an onboard policy before blackout.
- Make observation sequences respond to new evidence.
- Show the autonomy policy's inputs, candidate actions and decision explanation.
- Separate ground commands from onboard decisions in the event log.

**Hackathon simplification:** Three fixed interpretable policies (Conservative, Science-first, Resource-aware) are sufficient. Do not implement a general belief-space planner or claim the paper's experimental performance.

### 2.6 Robust low-thrust design under uncertainty

**Source:** Babapour, M., and Taheri, E., *Robust Spacecraft Low-Thrust Trajectory Design: A Chance-Constrained Covariance-Steering Approach*, arXiv:2601.17629, 24 January 2026.  
**Link:** https://arxiv.org/abs/2601.17629  
**Research contribution:** Uses chance-constrained covariance steering and sequential convex programming to design robust low-thrust trajectories, explicitly considering mass change and stochastic disturbance intensity. The work demonstrates that mass variation can influence uncertainty and that ignoring it may underestimate mission risk.

**MISSIONFORGE translation:**

- Treat key mission inputs as uncertain rather than burying them in fixed safety factors.
- Show probability of satisfying simplified hard constraints across sampled parameter variations.
- Track uncertainty in mass, propulsion, power, navigation/execution, pointing and downlink.
- Show metric quantiles and failure causes.

**Hackathon simplification:** Use seeded Monte Carlo sampling of simplified model parameters with a Wilson interval around the observed feasible fraction. This is not covariance steering, chance-constrained optimal control, or a flight risk assessment.

### 2.7 Efficient global search for low-thrust gravity-assist trajectories

**Source:** Iijima, R., Oguri, K., and Kuwahara, T., *Global Optimization Framework for Automated Low-Thrust Gravity-Assist Trajectory Design*, arXiv:2609.09515, 8 September 2026.  
**Link:** https://arxiv.org/abs/2609.09515  
**Research contribution:** The paper explains why full nonlinear optimization over all candidate gravity-assist sequences is computationally expensive. It combines broad search, convex pruning of infeasible cases and robust local low-thrust optimization. Its BepiColombo-inspired example reports substantially more feasible solutions in the broad search than a conventional setup.

**MISSIONFORGE translation:**

- Use a two-stage search for mission choices: inexpensive screening first, detailed engine evaluation second.
- Prune obviously infeasible catalogue/trajectory combinations before expensive robustness sampling.
- Keep the design explorer's candidate generation separate from evaluation so later optimizers can replace it.

**Hackathon simplification:** Use rule-based screening and JPL stored mission options. Do not reproduce the paper's low-thrust/global optimizer.

### 2.8 Joint science collection and downlink scheduling

**Source:** Levinson, R., Ravindra, V., and Roy-Singh, S., *Optimal Planning to Coordinate Science Data Collection and Downlink for a Constellation of Agile Satellites with Limited Storage*, IJCAI 2025, pages 8544–8553.  
**Link:** https://doi.org/10.24963/ijcai.2025/950  
**Research contribution:** Formulates integrated science observation and downlink scheduling as a mixed-integer linear program. It explicitly accounts for limited memory, energy, temporal windows and science rewards; a data-cycle abstraction organizes collection and downlink opportunities. The reported study uses real-world-scale data for an eight-satellite wildfire application.

**MISSIONFORGE translation:**

- Show observation opportunities and contact windows on one timeline.
- Track generated bits, storage capacity, contact capacity, deadlines and power.
- Penalize data that cannot be delivered before a buffer or deadline constraint is hit.
- Let users alter observation cadence, data compression or comms capacity to recover return.

**Hackathon simplification:** One spacecraft, one ground station and a deterministic greedy interval scheduler with local swaps. Do not claim MILP optimality.

### 2.9 Spacecraft telemetry anomaly detection under edge constraints

**Source:** Goetze, C., Schlippe, T., and Lakey, D., *Deep Learning-Based Anomaly Detection in Spacecraft Telemetry on Edge Devices*, IEEE Space Computing Conference 2025; arXiv version 2603.29375 (31 March 2026).  
**Links:** https://doi.org/10.1109/SCC66396.2025.00019 and https://arxiv.org/abs/2603.29375  
**Research contribution:** Compares forecasting-plus-threshold, direct classification and image classification for spacecraft telemetry anomaly detection. It studies edge deployment and multi-objective model compression. Its reported results motivate attention to both detection quality and constrained onboard compute.

**MISSIONFORGE translation:**

- Show expected telemetry envelopes and live residuals.
- Use an explainable forecasting/threshold baseline with persistence and severity levels.
- Connect detected anomalies to a specific system fault and recovery decision.

**Hackathon simplification:** Implement moving-average or EWMA residual rules. Do not claim neural-network inference or reproduce the paper's metrics.

### 2.10 Serious games and learning design

**Source:** *Advancing Engineering Education Through Serious Games: A Systematic Literature Review of Technological Innovation, Challenges, and Future Directions*, IEEE Access 14 (2026), DOI 10.1109/ACCESS.2026.3669416.  
**Link:** https://doi.org/10.1109/ACCESS.2026.3669416  
**Research contribution:** Synthesizes 63 studies published during 2020–2025. The review describes the prevalence of web/mobile serious games, potential of immersive tools for spatial understanding, limited AI-driven adaptivity, and recurring gaps in pedagogical alignment and measurement of long-term learning outcomes.

**MISSIONFORGE translation:**

- Keep the core game browser-first and accessible; 3D is optional rather than required.
- Define learning outcomes before adding badges or points.
- Use pre/post concept checks, decision explanations and a debrief that maps misconceptions to evidence.
- Treat engagement and learning gains as separate metrics.

**What not to claim:** A short hackathon demo cannot prove long-term learning gains. At most, the product can demonstrate an evaluation design and capture indicative pre/post performance.

### 2.11 Gamification for space sustainability

**Source:** *Gamification as a tool to identify and address ongoing challenges in space activities: the case of space debris mitigation*, Acta Astronautica 225 (December 2024), DOI 10.1016/j.actaastro.2024.09.057.  
**Link:** https://doi.org/10.1016/j.actaastro.2024.09.057  
**Research contribution:** Proposes a serious-game framing for space-debris mitigation and uses a game-design model to explore how a game can help surface strategic incentives and sustainability concerns.

**MISSIONFORGE translation:**

- In an extended LEO scenario, add an optional end-of-life disposal / debris-mitigation decision.
- Make sustainability a visible design objective and consequence, not an isolated trivia quiz.

**Hackathon scope:** Keep this as a later scenario extension unless the core mission is complete.

---

## 3. NASA and operational engineering references

### 3.1 NASA 2026 Small Spacecraft State-of-the-Art

**Source:** NASA Ames / Small Spacecraft Systems Virtual Institute, *State-of-the-Art of Small Spacecraft Technology*, 2026 online edition.  
**Link:** https://www.nasa.gov/smallsat-institute/sst-soa/  
**Key metadata:** NASA's page identifies the 2026 edition as published May 2026, with information on publicly available SmallSat technology as of April 1, 2026. The edition includes updated chapters for spacecraft platforms, power, propulsion, GNC, avionics, communications, launch/integration and ground systems/operations.

**Use in MISSIONFORGE:** Component catalogue sourcing, subsystem constraints, TRL context, technology applicability. Every catalogue item should store its primary source, exact table/chapter, edition, source date, retrieval date, spacecraft class, environment, and whether it is a demonstrated product, developmental technology or conceptual assumption.

**Important distinction:** This 2026 online edition is newer than the 2025 NTRS report (NTRS 20250000142), whose public-information cutoff was September 30, 2024. Do not cite the older report as if it reflected April 2026 technology status.

### 3.2 NASA General Mission Analysis Tool (GMAT)

**Source:** NASA Software Catalog, *General Mission Analysis Tool (GMAT) Version R2026*.  
**Link:** https://software.nasa.gov/software/GSC-19640-1  
**Contribution:** GMAT is an open-source mission design, optimization and navigation environment spanning LEO through lunar, libration-point and deep-space mission regimes. NASA describes GUI, script, Python and Java usage modes.

**Use in MISSIONFORGE:** Use GMAT as an external reference / advanced-validation path for selected benchmark cases, not as a browser-side runtime dependency. The hackathon MVP should not embed GMAT in the browser frontend; any optional comparison adapter must remain isolated behind the Python backend. Where a comparison is made, record exact GMAT release, force model, ephemerides, coordinate frame and solver settings.

### 3.3 NASA tool interoperability

**Source:** NASA NESC Technical Bulletin 23-05, *Flight Mechanics Analysis Tools Interoperability and Component Sharing* (2023).  
**Link:** https://www.nasa.gov/centers-and-facilities/nesc/nesc-technical-bulletin-23-05-flight-mechanics-analysis-tools-interoperability-and-component-sharing/  
**Contribution:** Highlights the complexity of transferring trajectory and model information across Copernicus, GMAT and MONTE, and the value of interoperable data and shared components.

**Use in MISSIONFORGE:** Use neutral, versioned internal representations for trajectory options and ephemeris metadata. Keep provider-specific response parsing inside adapters. Avoid binding the domain engine to JPL's API response format.

### 3.4 JPL Small-Body Mission Design API

**Source:** JPL SSD, *Small-Body Mission Design API*, API documentation and fair-use rules.  
**Link:** https://ssd-api.jpl.nasa.gov/doc/mdesign.html and https://ssd-api.jpl.nasa.gov/doc/  
**Use in MISSIONFORGE:** NEO accessible target discovery and stored mission design options. All requests are server-side, serialized, identified by an application-specific User-Agent, cached, timeout-bounded and response-version checked. An offline source snapshot must be available. Never make the live API a judging dependency.

---

## 4. Feature-to-source traceability matrix

| Feature | Primary research inspiration | Minimum implementation | Fidelity statement |
|---|---|---|---|
| Mission digital twin + STM/MTM | NASA Model-Based Mission Formulation | One canonical domain state; generated matrices | Educational subset of MBSE |
| Architecture impact graph | NASA mission formulation + architecture graph research | Typed dependency edges and graph traversal | Deterministic project model |
| Pareto Design Arena | Bussemaker & Firchau; model-based CubeSat design | Candidate mutations + non-dominated sorting | Simplified multiobjective search |
| Robustness Lab | Babapour & Taheri; mission design under uncertainty | Seeded Monte Carlo + Wilson interval | Not a flight probability model |
| Science belief tracker | Guirguis et al.; Kim et al. | Bayesian hypothesis updates + entropy | Synthetic mission likelihoods |
| Blackout autonomy | Kim et al. | Three offline policies; hard resource checks | Rule-based finite-state autonomy analogue |
| Science/downlink scheduler | Levinson et al. IJCAI | One-craft data-cycle greedy scheduler | Not a globally optimal MILP |
| Telemetry health monitor | Goetze et al.; Alcarria et al. | EWMA/threshold/persistence | Explainable statistical baseline |
| Game learning/debrief | IEEE Access 2026 serious-game review; 2022 engineering serious-game framework | Learning objectives, pre/post checks, explanatory debrief | Indicative evaluation, not long-term causal evidence |
| LEO sustainability extension | Acta Astronautica 2024 space-debris gamification | End-of-life choice and penalty/reward | Scenario-level sustainability lesson |
| External trajectory cross-check | NASA GMAT, JPL API and NASA tool interoperability | Optional offline benchmark comparisons | Depends on exact external settings |

---

## 5. Source quality and implementation rules

1. Prefer original research papers, NASA technical reports, official API documentation, and official technology surveys over blogs or unsourced summaries.
2. Record publication date and event/data cutoff separately. A paper published in 2026 may use data from an earlier period.
3. For arXiv papers, label them as preprints unless a peer-reviewed publication is confirmed. A preprint is useful research, not automatic NASA endorsement or a standard.
4. Never copy a component's numerical specifications from an abstract or secondary source. Open the cited primary table/datasheet and save its exact units, environmental limits, test conditions and applicability.
5. Store source URLs as metadata on each `CatalogComponent`; do not only keep a global bibliography.
6. Record equation versions in the engine. When changing an equation, increment `ENGINE_VERSION` and update known-answer tests.
7. Keep the simulation deterministic, and never let generative AI be the source of numerical truth.
8. Separate research motivation from implemented fidelity in the UI and submission narrative.

---

## 6. Selected references and access links

- NASA model-based mission formulation: https://ntrs.nasa.gov/citations/20220019154
- Bussemaker & Firchau (2025), system architecture optimization: https://doi.org/10.1007/s12567-025-00626-7
- Schmitt et al. (2025), mission architecture sandbox game framework: https://doi.org/10.1016/j.actaastro.2025.04.004
- Guirguis et al. (2026), POMDP science exploration: https://arxiv.org/abs/2608.03155
- Kim et al. (2025), offline belief-state science operations: https://arxiv.org/abs/2510.08812
- Babapour & Taheri (2026), robust low-thrust covariance steering: https://arxiv.org/abs/2601.17629
- Iijima et al. (2026), global low-thrust gravity-assist search: https://arxiv.org/abs/2609.09515
- Levinson et al. (2025), science/downlink planning: https://doi.org/10.24963/ijcai.2025/950
- Goetze et al. (2025/2026), telemetry anomaly detection: https://doi.org/10.1109/SCC66396.2025.00019 and https://arxiv.org/abs/2603.29375
- Alcarria et al. (2026), structure-aware unsupervised telemetry anomaly detection: https://arxiv.org/abs/2609.10017
- IEEE Access (2026), serious games in engineering education review: https://doi.org/10.1109/ACCESS.2026.3669416
- Acta Astronautica (2024), gamification and space debris mitigation: https://doi.org/10.1016/j.actaastro.2024.09.057
- NASA SmallSat SoA (2026): https://www.nasa.gov/smallsat-institute/sst-soa/
- NASA GMAT R2026: https://software.nasa.gov/software/GSC-19640-1
- NASA flight mechanics tool interoperability bulletin: https://www.nasa.gov/centers-and-facilities/nesc/nesc-technical-bulletin-23-05-flight-mechanics-analysis-tools-interoperability-and-component-sharing/
- JPL Small-Body Mission Design API: https://ssd-api.jpl.nasa.gov/doc/mdesign.html
