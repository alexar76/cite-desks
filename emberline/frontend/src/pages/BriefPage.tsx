import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { BriefDocument } from "../components/BriefDocument";
import { SideNav } from "../components/Nav";
import { api } from "../lib/api";
import type { Brief } from "../lib/types";

export function BriefPage() {
  const { id } = useParams();
  const [brief, setBrief] = useState<Brief | null>(null);
  const [rawOpen, setRawOpen] = useState(false);
  const [packError, setPackError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    api.brief(id).then(setBrief).catch(() => setBrief(null));
  }, [id]);

  return (
    <div className="app-shell">
      <SideNav />
      <main className="main">
        <div className="kicker">Immutable archive object</div>
        <h2 className="serif">Evidence brief</h2>
        {brief ? (
          <>
            <BriefDocument brief={brief} />
            <div className="hero-actions" style={{ marginTop: 16 }}>
              <button
                className="btn btn-ember"
                type="button"
                onClick={() => {
                  setPackError(null);
                  void api.citePack(brief.id).catch(() => setPackError("Cite pack download failed."));
                }}
              >
                Download cite pack
              </button>
              <button className="btn" type="button" onClick={() => setRawOpen((v) => !v)}>
                {rawOpen ? "Hide JSON" : "Open JSON"}
              </button>
            </div>
            {packError && <p className="muted">{packError}</p>}
            {rawOpen && (
              <pre className="card mono" style={{ overflow: "auto", fontSize: 12 }}>
                {JSON.stringify(brief, null, 2)}
              </pre>
            )}
          </>
        ) : (
          <p className="muted">Brief not found or still loading.</p>
        )}
      </main>
    </div>
  );
}
