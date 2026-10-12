import { FormEvent, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { BBoxMap } from "../components/BBoxMap";
import { CopyButton } from "../components/CopyButton";
import { SideNav } from "../components/Nav";
import { clipWatchBbox, isValidWatchBbox } from "../lib/geo";
import { api } from "../lib/api";
import type { BBox } from "../lib/types";

export function WatchNew() {
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [clipNote, setClipNote] = useState("");
  const [secret, setSecret] = useState("");
  const [watchId, setWatchId] = useState("");
  const [form, setForm] = useState({
    name: "New corridor",
    west: "-122.6",
    south: "36.8",
    east: "-121.2",
    north: "38.2",
    schedule: "60m",
    policy: "on_match",
    quiet_hours: "",
    slack_webhook: "",
    https_webhook: "",
    smoke: false,
  });

  const bbox = useMemo(() => {
    const raw: BBox = {
      west: Number(form.west),
      south: Number(form.south),
      east: Number(form.east),
      north: Number(form.north),
    };
    if (isValidWatchBbox(raw)) return raw;
    const finite = [raw.west, raw.south, raw.east, raw.north].every(Number.isFinite);
    if (finite && raw.east > raw.west && raw.north > raw.south) return clipWatchBbox(raw).bbox;
    return null;
  }, [form.west, form.south, form.east, form.north]);

  function set(key: string, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function applyBbox(next: BBox, clipped: boolean) {
    setForm((prev) => ({
      ...prev,
      west: String(next.west),
      south: String(next.south),
      east: String(next.east),
      north: String(next.north),
    }));
    setClipNote(clipped ? "Box clipped to 40° × 30° (evidence watch maximum)." : "");
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const watch = await api.createWatch({
        name: form.name,
        west: Number(form.west),
        south: Number(form.south),
        east: Number(form.east),
        north: Number(form.north),
        schedule: form.schedule,
        policy: form.policy,
        quiet_hours: form.quiet_hours,
        slack_webhook: form.slack_webhook,
        https_webhook: form.https_webhook,
        layers: form.smoke ? ["fire", "weather", "smoke"] : ["fire", "weather"],
      });
      if (watch.webhook_secret) {
        setSecret(watch.webhook_secret);
        setWatchId(watch.id);
        return;
      }
      navigate(`/watches/${watch.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create watch");
    }
  }

  return (
    <div className="app-shell">
      <SideNav />
      <main className="main">
        <div className="kicker">Watch CRUD</div>
        <h2 className="serif">Draw the box. Not the fire.</h2>
        {secret && (
          <div className="card" style={{ maxWidth: 640, marginBottom: 16 }}>
            <div className="kicker">Shown once</div>
            <p>Webhook HMAC secret. Store it now. Emberline will not display it again.</p>
            <p className="mono" style={{ marginTop: 12, wordBreak: "break-all" }}>
              {secret}
            </p>
            <div className="hero-actions" style={{ marginTop: 16 }}>
              <CopyButton value={secret} label="Copy secret" />
              <button className="btn btn-ember" type="button" onClick={() => navigate(`/watches/${watchId}`)}>
                Continue
              </button>
            </div>
          </div>
        )}
        {!secret && (
          <form onSubmit={onSubmit} className="card" style={{ maxWidth: 760 }}>
            <label className="field">
              Name
              <input value={form.name} onChange={(e) => set("name", e.target.value)} />
            </label>
            <div style={{ marginTop: 16 }}>
              <BBoxMap bbox={bbox} onChange={applyBbox} />
            </div>
            {clipNote && <p className="warn">{clipNote}</p>}
            <div className="grid-2" style={{ marginTop: 12 }}>
              {(["west", "south", "east", "north"] as const).map((key) => (
                <label className="field" key={key}>
                  {key}
                  <input value={form[key]} onChange={(e) => set(key, e.target.value)} />
                </label>
              ))}
            </div>
            <p className="muted" style={{ marginTop: 8 }}>
              GIS numbers stay authoritative. Map is a rectangle, not a fire layer.
            </p>
            <div className="grid-2" style={{ marginTop: 12 }}>
              <label className="field">
                Schedule
                <select value={form.schedule} onChange={(e) => set("schedule", e.target.value)}>
                  <option value="15m">every 15 min</option>
                  <option value="30m">every 30 min</option>
                  <option value="60m">every 60 min</option>
                </select>
              </label>
              <label className="field">
                Policy
                <select value={form.policy} onChange={(e) => set("policy", e.target.value)}>
                  <option value="on_match">watchbox then brief</option>
                  <option value="always_brief">always fire.weather</option>
                </select>
              </label>
            </div>
            <label className="field" style={{ marginTop: 12 }}>
              <input
                type="checkbox"
                checked={form.smoke}
                onChange={(e) => setForm((prev) => ({ ...prev, smoke: e.target.checked }))}
              />{" "}
              Also buy HMS smoke (North America qualitative polygon — not PM2.5, not a perimeter)
            </label>
            <label className="field" style={{ marginTop: 12 }}>
              Quiet hours (24h, watch timezone) e.g. 22-06
              <input value={form.quiet_hours} onChange={(e) => set("quiet_hours", e.target.value)} placeholder="22-06" />
            </label>
            <p className="muted" style={{ marginTop: 16 }}>
              Delivery is optional. Slack, HTTPS webhooks, and desk push on an installed PWA. Email is not a channel.
            </p>
            <label className="field" style={{ marginTop: 12 }}>
              Slack webhook (https only)
              <input
                value={form.slack_webhook}
                onChange={(e) => set("slack_webhook", e.target.value)}
                placeholder="https://hooks.slack.com/…"
              />
            </label>
            <label className="field" style={{ marginTop: 12 }}>
              HTTPS webhook (https, public host)
              <input value={form.https_webhook} onChange={(e) => set("https_webhook", e.target.value)} />
            </label>
            {error && <p className="err">{error}</p>}
            <button className="btn btn-ember" style={{ marginTop: 18 }} type="submit">
              Save watch
            </button>
          </form>
        )}
      </main>
    </div>
  );
}
