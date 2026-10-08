import { useEffect, useState } from "react";
import { api } from "../lib/api";

export function RailsBanner() {
  const [health, setHealth] = useState<{ demo?: boolean; hub_mode?: string } | null>(null);
  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
  }, []);
  if (health?.demo) {
    return (
      <div className="demo-banner" role="status">
        DEMO <span>Not for sale. Checkout is closed.</span>{" "}
        <a className="demo-repo" href="https://github.com/alexar76/cite-desks">
          Fork · github.com/alexar76/cite-desks
        </a>
      </div>
    );
  }
  if (health?.hub_mode !== "fixture") return null;
  return (
    <div className="rails-banner" role="status">
      SAMPLE RAILS · Hub is not charged · not a live detection
    </div>
  );
}
