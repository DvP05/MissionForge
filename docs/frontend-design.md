# Frontend rebuild: game-style spacecraft builder

This note records how the frontend was rebuilt against the frontend design brief (`front_design.md`),
which libraries were used, which were not, and why.

## What changed

| Destination | Route | What it is now |
|---|---|---|
| Mission Hangar | `/` | Hero, saved missions to continue, scenario cards with destination art, package import and demo |
| Mission Briefing | `/mission/<id>` | Unchanged content, new design system; step 1 of the mission flow |
| Science Laboratory | `/science/<id>` (new) | Objective → measurement → instrument capability → engineering consequence → expected return; highlights serving instruments on the 3D spacecraft |
| Spacecraft Architect | `/architect/<id>` | Catalogue (search, subsystem filters) / live 3D viewport / component inspector, with the live engineering dashboard |
| Trade Study | `/arena/<id>` | Existing Pareto explorer, robustness lab and comparison, relabelled "Trade study" |
| Mission Control | `/control/<runId>` | New header, "Revise in architect" link; telemetry, events, decisions and map unchanged |
| Mission Review | `/review/<runId>` | Outcome-coloured debrief header, "Revise the spacecraft" link |
| Mission Archive | `/archive` (new) | Saved designs, revisions, flown runs with replay and report links, package restore |

The mission workspace shows the design flow as numbered steps: Brief → Science lab → Architect → Trade study.

## Engineering truth is unchanged

- The canonical design is still the Zustand `useMissionStore` `MissionState`. Every install, replace or remove goes
  through `selectComponent` + `commitRevision`, so each change is one numbered design revision.
- Every engineering number still comes from `POST /api/mission/validate` via `useAnalysis`, which keeps stale responses
  out (revision match, abort, debounce). The new dashboard and inspector only read `MissionAnalysis`.
- New presentation-only state lives in `state/architect-ui-store.ts`: selection, view mode, overlays, highlights and the
  install animation trigger. It never decides what is installed.
- Status language: PASS / WATCH / FAIL / NOT MODELLED come from backend constraint results; ANALYSING / STALE come
  from comparing the analysis revision with the design revision (`lib/spacecraft/engineering-status.ts`). A metric
  with no result shows `NOT MODELLED`, never a zero.

## 3D spacecraft

- `lib/spacecraft/part-registry.ts` is the component-to-geometry mapping layer. For each component it gives:
  - mount point, position and normal;
  - exploded offset;
  - subsystem group;
  - placeholder shape kind and variant.
- The catalogue has no dimensions, so every shape is marked `geometryStatus: "placeholder"`. Visual size follows the
  component's rank within its category (more panels, a bigger dish), never a physical dimension. The viewport says
  "Illustrative placeholder geometry · not to scale".
- The ground segment is not drawn: it is not on the spacecraft.
- `components/spacecraft3d/SpacecraftViewport.tsx` uses React Three Fiber plus drei: orbit controls, HTML labels, stars,
  and a local light-panel environment (no HDR download).
  - Rendering is on demand (`frameloop="demand"`).
  - The viewport is loaded with `next/dynamic` (`ssr: false`), so `three` is not in the hangar bundle. An e2e test
    checks this.
- View modes:
  - assembly, exploded, subsystem isolation, technical (labels, mount points, wireframe);
  - power, comms, science and thermal highlights. Each highlight note says it is a visual highlight, not a simulation.
- Camera controls: reset, front, side, top, focus on the selected part.
- WebGL fallback: `SpacecraftSchematic2D` draws a 2D schematic of the same parts.
- An accessible "Installed parts" button list mirrors the 3D scene for keyboard and screen-reader use.

## Animation

- **Motion** (`motion@14`, `motion/react`) handles interface transitions:
  - page fade (`app/template.tsx`, `MotionConfig reducedMotion="user"`);
  - scenario card hover;
  - inspector panel changes.
- **anime.js** (`animejs@4`) handles orchestrated sequences on 3D objects and the launch indicator:
  - component install (fly in along the mount normal, overshoot settle, solar wing deployment);
  - exploded / assembled transitions;
  - camera moves;
  - the launch sequence bar, shown only while the simulation request is in flight.
- Both respect `prefers-reduced-motion`: anime sequences are skipped (instant placement) and Motion reduces its
  transitions.

## Libraries named in the brief

| Name | Decision | Reason |
|---|---|---|
| anime.js | Used (4.5.0) | Install, deploy, camera and launch sequences |
| Motion | Used (14.14.0) | Page, panel and card transitions |
| Three.js / React Three Fiber / drei | Used (0.187.0 / 9.8.2 / 10.7.9) | The interactive spacecraft |
| Higgsfield | Not used | A paid generative-media service that needs the team's account; the brief also forbids a runtime dependency on it. Backdrops are drawn in code (CSS / SVG) and work offline. Generated stills can be added later as optional media in `public/`. |
| Convex | Not used | The product spec requires no database, sign-in or paid service, and the app must work offline. Persistence stays in browser storage plus exportable mission packages; the Archive page covers saved designs, revisions and runs. |
| 21st.dev | Not adopted as a dependency | A registry of copy-paste components. Its card, toolbar and inspector patterns were adapted in our own Tailwind components rather than importing code with a second design language. |
| SmoothUI | Not adopted as a dependency | Same reason as 21st.dev; motion patterns are covered by Motion. |
| bklitUI | Identified, not used | An MIT-licensed shadcn chart registry (github.com/bklit/bklit-ui). It would duplicate Recharts, which the existing charts already use. |
| Shoogle | Identified, no integration | A search engine over shadcn/ui component registries (a discovery tool with an MCP server), not a runtime library. |

## Tests

`frontend/tests/e2e/spacecraft-builder.spec.ts` covers:

- the viewport renders the canonical parts;
- installing a high-gain antenna changes the saved design, the 3D parts, the inspector and the analysed link margin;
- stale analysis responses cannot overwrite a newer revision;
- installing and removing an instrument from the inspector;
- view modes and their honesty notes;
- no number is shown for an unmodelled metric;
- Science Lab highlighting;
- the Archive;
- the hangar bundle does not load the 3D engine.

The existing suites (layout ratios, accessibility at 1280 / 375 px, persistence, mission control, review) still run
against the rebuilt screens.

## Gameplay redesign (design_update.md)

The second brief made the architect playable rather than a parts form. Everything below still edits only the canonical
`MissionState` through the store actions and still shows only backend analysis values.

### Add / replace / remove

- A single path, `components/architect/component-actions.ts`, handles every add, replace and remove. It records the
  previous architecture for Undo.
  - `requestChange` decides whether to ask: an add with no catalogue conflict applies at once; a replace, a remove, or
    anything that breaks a catalogue rule opens `ComponentChangeDialog`.
  - The replace dialog compares the installed and new component (key specifications from the catalogue).
  - The remove dialog lists the required measurements that would be left without a capable instrument (catalogue
    capability mapping; the engine re-checks coverage).
  - The conflict dialog names the selection that would break. No other selection is ever changed.
- Undo restores the earlier architecture through the same store actions as a **new** revision (`restoreArchitecture`).
  It never rewinds revision numbers and is never a visual-only rollback.
- Catalogue cards have distinct, labelled states: available, installed (solid badge plus green rail), inspecting (focus
  ring), incompatible (exact reason), awaiting confirmation. The primary action names exactly what happens (Add,
  Replace, Remove); "Details" only inspects.

### Architect layout

- **Left: build tree.** Every subsystem with its installed part, a required tag, EMPTY if nothing is fitted, and the
  worst backend constraint status (or ANALYSING / STALE).
- **Centre: spacecraft stage.**
  - The 3D view outlines the subsystem being browsed and shows empty payload slots while instruments are browsed.
  - Under it sit the impact report and the readiness gate board.
- **Right: component panel.** Tabs for Available (search plus cards), Installed (textual component tree, also the
  accessible alternative to 3D) and Details (Quick view / Engineering view with source, assumptions and failure modes).
- **Bottom: live budget rail**, always visible. A value lifts in briefly only after a confirmed analysis changes it.
- **Phones:** Build / Spacecraft / Budgets tabs; every action stays available.

### Impact report and gates

- **Impact report.** Compares the backend analyses of the revisions before and after the change:
  - budget values, before and after, with no frontend arithmetic;
  - constraints that changed status, with their backend explanations;
  - margins that moved;
  - science requirements gained or lost;
  - impacted subsystems, plus a cause-and-effect chain.
  The engine sends no separate impact narrative, and the report says so.
- **Readiness gates.** `lib/spacecraft/gates.ts` groups constraint results into eight gates: science, launch mass,
  power, propulsion, comms/data, thermal, budget, compatibility.
  - Each gate shows actual / limit / margin, the backend explanation and suggested action, and an "Open <subsystem>"
    repair.
  - A gate whose constraints are all not modelled is NOT MODELLED, never PASS.

### Progression

- `lib/progress/progress.ts` computes eight stages: accept, science, build, gates, trade study, readiness, fly, review.
  It uses only real state: the saved design, the analysis of the current revision, cached runs, and recorded actions
  (trade study run, robustness run, review opened, passport exported).
- Badges (Science Traceable, Power Margin Recovered, Downlink Plan Ready, Risk Reviewed, Mission Ready):
  - each needs a passing engine result or a real action;
  - the starter design earns nothing until the player changes it;
  - nothing rewards spending.
- Optional challenges are judged only by constraint results. They show "needs a current analysis" when there is none.
- The workspace shows a stage rail (complete / current / needs attention / not started) and a recommended next step.
  Mission control and review carry the same rail, and no stage is locked.

### Motion, atmosphere and references

- `lib/motion/motion.ts` holds the motion tokens (micro 150 ms, panel 220 ms, state 360 ms, milestone 600 ms) and the
  anime.js helpers (`enter`, `emphasiseChange`, `settle`, `milestone`). Every helper is a no-op under reduced motion.
  - The top bar has a Motion setting that forces reduced motion regardless of the OS.
  - Values never tween through invented intermediate numbers; only the confirmed value is emphasised.
- Backgrounds are three small local SVGs in `public/backdrops/` (`orbital-layers`, `star-chart`, `signal-waves`), drawn
  in Haikei's layered-wave style.
  - **Haikei itself was not used:** it is an interactive web generator that could not be operated from this
    environment.
  - The assets are hand-authored, low contrast, under 2 KB each, and never loaded at runtime from a third party.
- **Refero was not accessed** (it is a sign-in research library). These patterns were adapted from general product
  practice:
  - a three-zone configurator (tree / canvas / inspector);
  - a sticky metric rail;
  - a gate board in a status-page style;
  - before/after confirmation diffs.

### Known gaps (backend contracts that would help)

- No impact narrative from the engine. The report uses constraint explanations and before/after values only.
- No scenario "difficulty" or "primary challenge" field. Scenario cards show target, duration, objective count, top
  constraints and the fidelity note instead of inventing difficulty.
- Dependencies are only the catalogue `compatibleWith` rules. There is no "requires component X" contract, so no
  automatic dependency adds.
- No per-scenario list of optional subsystems. Every subsystem is treated as required, matching the current schema, in
  which every architecture field is mandatory.

### Tests

`frontend/tests/e2e/architect-gameplay.spec.ts` covers:

- the component selection journey: inspect, add, replace with comparison, remove with what is lost, undo as a new
  revision, and unrelated selections unchanged;
- constraint recovery through a gate repair;
- progression (next step, a real milestone, stages for flying);
- reduced motion;
- the phone-width tabs.

Existing specs were updated to confirm replacements.

## Stitch command-system restyle

The visual system now follows the Stitch "Aerospace Mission Telemetry & Command System" pack, supplied as a zip by the
user. The pack has a `DESIGN.md` and four screens: command centre, architect, mission control and readiness review.

- **Tokens** (`app/globals.css`):
  - graphite surfaces: `#121413` base, `#0d0e0e` wells, `#1b1c1c` bulkheads, `#292a2a` tactical cards;
  - hairline `#696e6e`-based borders;
  - `#d8d9da` primary readouts;
  - signal amber `#f5a623` for the active station and the primary trigger;
  - micro-accents: orbital cyan `#38bdf8`, warning amber `#fbbf24`, emergency crimson `#f87171`;
  - every radius is 0 (machined corners); `.chamfer` cuts hero bays; `.hud-grid` / the backdrop draw the 24 px datum
    grid; `.label-caps` is the mono uppercase telemetry label.
- **Type:** Space Grotesk and JetBrains Mono, self-hosted via `@fontsource-variable/*` (OFL-1.1), so the app needs no
  font network at runtime. Structural headings are uppercase.
- **Shell:**
  - a station rail with every destination, always clickable; before a flight, Mission control and Debrief open the
    launch panel;
  - a telemetry strip showing only real values (target, design revision, analysed link margin, readiness);
  - a Stations menu on phones.
- **New Readiness Review station** (`/readiness/<id>`): gate-by-gate GO / NO-GO from the engine's constraint results
  with actual, limit and margin; flight authorisation through the ordinary launch; the robustness lab; and a return to
  the architect.
- **Not taken from the mockups:** their invented telemetry (mission clocks, a commander's name, XP and ranks, made-up
  specs and hashes). Every number shown is still the engine's.
- **3D spacecraft:** the satellite and its launch adapter are unchanged, set in a graphite viewport with a HUD grid.
