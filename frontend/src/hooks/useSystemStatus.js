import { useEffect, useState } from "react";

import { fetchSystemStatus } from "../services/projectApi.js";

const POLL_INTERVAL_MS = 30_000;

export function useSystemStatus() {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let active = true;
    let controller;

    const load = async () => {
      controller?.abort();
      controller = new AbortController();
      try {
        const data = await fetchSystemStatus(controller.signal);
        if (active) {
          setStatus(data);
          setError("");
        }
      } catch (requestError) {
        if (active && requestError.name !== "AbortError") {
          setError(requestError.message || "Unable to load system status.");
        }
      } finally {
        if (active) setIsLoading(false);
      }
    };

    load();
    const interval = window.setInterval(load, POLL_INTERVAL_MS);
    return () => {
      active = false;
      controller?.abort();
      window.clearInterval(interval);
    };
  }, []);

  return { status, error, isLoading };
}
