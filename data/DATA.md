# PeakPilot bundled data — provenance

These CSVs are bundled so the demo runs without a network connection. They are
**public infrastructure facts**, kept strictly separate from PeakPilot's SIMULATED
device telemetry and simulation outputs.

## Files

### `utilities.csv` — Electric utility by town

- **Columns:** `TOWN`, `UTILITY`.
- **Rows:** 351 (every Massachusetts town).
- **Source:** MassGIS (Commonwealth of Massachusetts) — Electricity Providers layer,
  via the Hackachusetts 2026 climate kit.
  Live query: `https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/ElectricityProviders/MapServer/0/query?where=1%3D1&outFields=TOWN,ELEC,ELEC_LABEL&returnGeometry=false&f=json`
  Kit zip: `https://hackachusetts2026.vercel.app/kits/utilities.zip`
- **Retrieved:** 2026-10-24 (live query). Portal snapshot date: 2026-10-18.
- **Units:** none (categorical).
- **Missing values:** none observed; any empty utility is preserved as an empty string.

### `landfills.csv` — Renewables at Massachusetts landfills

- **Columns:** `TOWN`, `SITE`, `TYPE`, `MW`, `STATUS`, `SINCE`.
- **Rows:** 116 projects.
- **Source:** MassGIS (Commonwealth of Massachusetts) — DEP Renewables at MA Landfills
  layer, via the Hackachusetts 2026 climate kit.
  Live query: `https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/DEP/RenewablesAtMaLandfills/MapServer/0/query?where=1%3D1&outFields=MUNICIPALITY,FACILITY,TYPE_,MW_PERMITTED,MW_OPERATING,STATUS_1,OPERATING_SINCE&returnGeometry=false&f=json`
  Kit zip: `https://hackachusetts2026.vercel.app/kits/landfills.zip`
- **Retrieved:** 2026-10-24 (live query). Portal snapshot date: 2026-10-18.
- **Units:** `MW` is megawatts of reported capacity (operating value preferred, else
  permitted). `SINCE` is an ISO date (operating-since) where available.
- **Missing values:** `MW` and `SINCE` are empty strings where the source reported no
  value (e.g. permitted/construction projects). Empty is preserved, never guessed.

## Usage terms and honesty rules

- MassGIS / Commonwealth of Massachusetts open data. Confirm the layer terms before
  republishing. This repository links the source and shows the snapshot date in the UI.
- **These datasets describe local infrastructure only.** They do NOT establish live grid
  demand, available grid capacity, electricity prices, carbon intensity, or which
  generator supplies a given building.
- **Reported capacity (MW) is not generation.** Do not infer actual energy produced from
  installed/permitted megawatts.
- MassGIS facts are always presented separately from PeakPilot's simulated device data.
