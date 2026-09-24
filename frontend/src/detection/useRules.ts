import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { Configuration } from "./types";
const eventName = "liveclip-rules-changed";
export function rulesChanged() {
  window.dispatchEvent(new Event(eventName));
}
export function useRules() {
  const [config, setConfig] = useState<Configuration | null>(null),
    [error, setError] = useState("");
  const reload = useCallback(async () => {
    try {
      const value = await api<Configuration>("/moment-rules/configuration");
      setConfig((old) => (old?.revision === value.revision ? old : value));
      setError("");
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "No se pudieron cargar las reglas",
      );
    }
  }, []);
  useEffect(() => {
    void reload();
    const listener = () => void reload();
    window.addEventListener(eventName, listener);
    const timer = setInterval(listener, 5000);
    return () => {
      clearInterval(timer);
      window.removeEventListener(eventName, listener);
    };
  }, [reload]);
  return { config, error, reload };
}
