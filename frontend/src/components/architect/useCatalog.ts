"use client";

import { useCallback, useEffect, useState } from "react";

import { apiGet } from "@/lib/api-client";
import { indexCatalog, type CatalogComponent, type CatalogGroup } from "./catalog-helpers";

export type CatalogState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; groups: CatalogGroup[]; index: Map<string, CatalogComponent> };

/** Loads GET /api/catalog (component options, parameters, compatibility rules). */
export function useCatalog(): { catalog: CatalogState; retry: () => void } {
  const [catalog, setCatalog] = useState<CatalogState>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    apiGet("/api/catalog", { signal: controller.signal }).then((result) => {
      if (controller.signal.aborted) return;
      if (!result.ok || !result.data) {
        setCatalog({
          kind: "error",
          message: result.error?.message ?? "The component catalogue could not be loaded.",
        });
        return;
      }
      setCatalog({ kind: "ready", groups: result.data.groups, index: indexCatalog(result.data.groups) });
    });
    return () => controller.abort();
  }, [attempt]);

  const retry = useCallback(() => {
    setCatalog({ kind: "loading" });
    setAttempt((n) => n + 1);
  }, []);
  return { catalog, retry };
}
