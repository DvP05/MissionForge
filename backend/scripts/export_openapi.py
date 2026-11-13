"""Write the FastAPI OpenAPI schema to backend/openapi.json (input for TS type generation)."""

import json
from pathlib import Path

from app.main import create_app

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "openapi.json"


def main() -> None:
    schema = create_app().openapi()
    OUTPUT_PATH.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
