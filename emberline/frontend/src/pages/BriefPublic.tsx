import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { BriefDocument } from "../components/BriefDocument";
import { SiteNav } from "../components/Nav";
import { api } from "../lib/api";
import type { Brief } from "../lib/types";

export function BriefPublic() {
  const { token } = useParams();
  const [brief, setBrief] = useState<Brief | null>(null);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    const tag = document.createElement("meta");
    tag.name = "robots";
    tag.content = "noindex, nofollow";
    document.head.appendChild(tag);
    return () => tag.remove();
  }, []);

  useEffect(() => {
    if (!token) return;
    api
      .publicBrief(token)
      .then((row) => {
        setBrief(row);
        setMissing(false);
      })
      .catch(() => {
        setBrief(null);
        setMissing(true);
      });
  }, [token]);

  return (
    <>
      <SiteNav />
      <section className="section">
        <div className="kicker">Unlisted brief</div>
        <h2 className="serif">Shared evidence</h2>
        <p className="sub">Not indexed. Presence of a brief is not a safety guarantee.</p>
        {brief ? (
          <div style={{ marginTop: 24, maxWidth: 820 }}>
            <BriefDocument brief={brief} publicView />
          </div>
        ) : (
          <p className="muted" style={{ marginTop: 24 }}>
            {missing ? "Brief not found." : "Loading…"}
          </p>
        )}
        <p className="muted" style={{ marginTop: 24 }}>
          <Link to="/sample">See a sample</Link>
          {" · "}
          <Link to="/login">Open the desk</Link>
        </p>
      </section>
    </>
  );
}
