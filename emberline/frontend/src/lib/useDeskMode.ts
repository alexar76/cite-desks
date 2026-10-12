import { useEffect, useState } from "react";
import { api } from "./api";

export type DeskMode = "loading" | "demo" | "live" | "unavailable";

export function useDeskMode(): DeskMode {
  const [mode, setMode] = useState<DeskMode>("loading");
  useEffect(() => {
    let active = true;
    api.health().then((health) => {
      if (active) setMode(health.demo === true ? "demo" : health.ok === true && health.demo === false ? "live" : "unavailable");
    }).catch(() => { if (active) setMode("unavailable"); });
    return () => { active = false; };
  }, []);
  return mode;
}
