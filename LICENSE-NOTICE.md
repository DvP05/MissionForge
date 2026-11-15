# Attribution and non-endorsement

MISSIONFORGE was built for the 2026 NASA Space Apps Challenge (Space Mission Design Game). The code is
released under the MIT License ([LICENSE](LICENSE)).

## Non-endorsement

MISSIONFORGE is an independent educational prototype. It is not endorsed by, affiliated with, or sponsored
by NASA, JPL or Caltech, and it uses no NASA or JPL logos or insignia. Results are for learning and must
not be used for real mission planning.

## Data

- **JPL Small-Body Mission Design API** (SSD/CNEOS, https://ssd-api.jpl.nasa.gov/doc/mdesign.html):
  near-Earth object trajectory options, fetched server-side only, under JPL's fair-use guidance (one
  request at a time, identifying User-Agent, cached). A captured snapshot is labelled with its capture
  date; the bundled synthetic snapshot is labelled "not JPL data".
- **Component catalogue** (`data/catalog`): illustrative archetypes written for this game. They are not
  real vendors or products, and every value is labelled a gameplay estimate until audited against a
  primary source.
- Research papers listed on the in-app `/about` page motivate features; MISSIONFORGE does not claim to
  reproduce their methods.

## Third-party software

FastAPI, Pydantic, httpx, Uvicorn, Next.js, React, Tailwind CSS, Recharts, Zustand, lucide icons,
Playwright and axe-core, each under its own license (see `backend/uv.lock` and `frontend/pnpm-lock.yaml`).
