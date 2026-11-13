# MISSIONFORGE catalogue v0.1.0

Every record is an illustrative archetype: fidelity `gameplay-estimate`, `is_illustrative=true`,
each value carrying its own provenance and assumptions. Nothing is source-backed; values await
a human source audit (ruling R3). No real vendors or products.

Parameter keys (value is a `Quantity`; SI or the listed unit):

| Category | Keys |
|---|---|
| launch | `launch_mass_limit` kg, `cost` USD (C3 envelope not modelled, Tier 3) |
| bus | `mass` kg, `structure_mass` kg (included in `mass`), `power_w` W, `max_payload_mass` kg, `cost` |
| propulsion | `dry_mass` kg, `isp` s, `power_w` W, `propellant_capacity` kg, `cost` (no numeric thrust; tags `high-thrust` / `low-thrust`) |
| power | `mass` kg, `array_power_at_1au` W (engine scales by 1/d^2), `battery_capacity` Wh, `usable_dod` fraction, `eps_efficiency` fraction, `cost` |
| adcs | `mass`, `power_w`, `pointing_accuracy` deg, `cost` |
| communications | `mass`, `tx_power` W, `antenna_gain` dB (dBi), `frequency` Hz, `required_ebn0` dB, `implementation_loss` dB, `max_data_rate` bit/s, `power_w`, `cost` |
| thermal | `mass`, `power_w`, `cost`; capabilities `heaters`, `radiator`, `passive-insulation` |
| cdh | `mass`, `power_w`, `storage` bit, `cost` |
| instrument | `mass`, `power_w`, `data_rate` bit/s, `pointing_requirement` deg, `cost`; `capabilities` from: visible-imaging, shape-model, vnir-spectroscopy, thermal-infrared, magnetometry, plasma-environment, high-res-imaging, multispectral-imaging |
| ground | `station_gain` dB (dBi), `noise_temperature` K, `contact_availability` fraction, `cost` per mission-year |

`compatible_with` rules: each selected component of the named category must match one rule of
that category (by `ids` and/or `tags`). Validate with `cd backend && uv run python -m scripts.validate_catalog`.

Failure modes are per-component, differentiated gameplay estimates (distinct description,
`baseProbability`, `severity` 1-5). `affectedMetric` names a metric the engine reports
(`battery_soc`, `link_margin`, `pointing_error`, `data_buffer`, `delta_v`, `power_margin`,
`mass_margin`, `launch_mass_margin`, `thermal_margin`, `schedule_margin`, `cost_margin`,
`science_return`); `mitigationIds` reference component ids or tags that would reduce the risk.

Sizing note: `prop-biprop` is a smallsat-class system (12 kg dry, 35 kg propellant capacity).
