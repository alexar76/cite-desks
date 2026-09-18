import { Link } from "react-router-dom";
import { formatCoord } from "../lib/geo";
import { money, shortDigest, when } from "../lib/format";
import type { Brief } from "../lib/types";
import { EvidenceMap } from "./EvidenceMap";

export function BriefDocument({
  brief,
  compact = false,
  sample = false,
  publicView = false,
}: {
  brief: Brief;
  compact?: boolean;
  sample?: boolean;
  publicView?: boolean;
}) {
  const rows = compact ? brief.hotspots.slice(0, 6) : brief.hotspots;
  return (
    <article className={`paper ${sample ? "sample-paper" : ""}`}>
      {sample && <div className="sample-watermark">SAMPLE</div>}
      <div className="meta">EMBERLINE EVIDENCE BRIEF · {brief.artifact_type}</div>
      <h3>{brief.watch.name}</h3>
      <div className="meta">
        {when(brief.generated_at)} · {formatCoord(brief.watch.bbox.south, "lat")} / {formatCoord(brief.watch.bbox.west, "lon")}
        {" → "}
        {formatCoord(brief.watch.bbox.north, "lat")} / {formatCoord(brief.watch.bbox.east, "lon")}
      </div>
      <div className="stamps">
        {brief.badges.map((b) => (
          <span className="stamp" key={b}>
            {b}
          </span>
        ))}
      </div>
      <p style={{ marginTop: 0, lineHeight: 1.55 }}>{brief.summary}</p>
      <div className="meta">
        {brief.evidence_status} · {brief.live_fire_detection_count} LIVE detections · SKUs {brief.skus_used.join(", ")} · COGS{" "}
        {money(brief.cogs_usd)}
      </div>
      {brief.delta && (
        <div className="delta-block">
          <div className="kicker" style={{ color: "#9a3412" }}>Run delta · not a spread model</div>
          <p style={{ margin: "8px 0 0", lineHeight: 1.5 }}>{brief.delta.summary}</p>
          {!compact && brief.delta.kind === "versus_prior" && brief.delta.versus_brief_id && (
            <div className="meta" style={{ marginTop: 8 }}>
              Versus{" "}
              {publicView ? (
                brief.delta.versus_brief_id
              ) : (
                <Link to={`/briefs/${brief.delta.versus_brief_id}`}>{brief.delta.versus_brief_id}</Link>
              )}
              {brief.delta.versus_generated_at ? ` · ${when(brief.delta.versus_generated_at)}` : ""}
              {typeof brief.delta.unchanged_count === "number"
                ? ` · ${brief.delta.unchanged_count} matched within ±${brief.delta.material_brightness_k ?? 5} K`
                : ""}
            </div>
          )}
          {!compact && brief.delta.kind === "versus_prior" && (
            <>
              {(brief.delta.appeared?.length ||
                brief.delta.disappeared?.length ||
                brief.delta.brightened?.length ||
                brief.delta.dimmed?.length) ? (
                <table className="hot-table" style={{ marginTop: 10 }}>
                  <thead>
                    <tr>
                      <th>change</th>
                      <th>lat</th>
                      <th>lon</th>
                      <th>K</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(brief.delta.appeared || []).map((row) => (
                      <tr key={`a-${row.id || row.lat}`}>
                        <td>appeared</td>
                        <td>{Number(row.lat).toFixed(4)}</td>
                        <td>{Number(row.lon).toFixed(4)}</td>
                        <td>{row.brightness_k}</td>
                      </tr>
                    ))}
                    {(brief.delta.disappeared || []).map((row) => (
                      <tr key={`d-${row.id || row.lat}`}>
                        <td>disappeared</td>
                        <td>{Number(row.lat).toFixed(4)}</td>
                        <td>{Number(row.lon).toFixed(4)}</td>
                        <td>{row.brightness_k}</td>
                      </tr>
                    ))}
                    {(brief.delta.brightened || []).map((row) => (
                      <tr key={`b-${row.id || row.lat}`}>
                        <td>brightened</td>
                        <td>{Number(row.lat).toFixed(4)}</td>
                        <td>{Number(row.lon).toFixed(4)}</td>
                        <td>
                          {row.from_k}→{row.to_k}
                        </td>
                      </tr>
                    ))}
                    {(brief.delta.dimmed || []).map((row) => (
                      <tr key={`m-${row.id || row.lat}`}>
                        <td>dimmed</td>
                        <td>{Number(row.lat).toFixed(4)}</td>
                        <td>{Number(row.lon).toFixed(4)}</td>
                        <td>
                          {row.from_k}→{row.to_k}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="meta" style={{ marginTop: 8 }}>
                  No material point changes on this run.
                </p>
              )}
              {brief.delta.limitations && brief.delta.limitations.length > 0 && (
                <ul className="delta-limits">
                  {brief.delta.limitations.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>
      )}
      {!compact && (
        <div style={{ margin: "16px -8px 8px" }}>
          <EvidenceMap bbox={brief.watch.bbox} hotspots={brief.hotspots} weather={brief.weather} />
        </div>
      )}
      <table className="hot-table">
        <thead>
          <tr>
            <th>lat</th>
            <th>lon</th>
            <th>K</th>
            <th>conf</th>
            <th>sat</th>
            <th>FRP</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((h) => (
            <tr key={h.id}>
              <td>{h.lat.toFixed(4)}</td>
              <td>{h.lon.toFixed(4)}</td>
              <td>{h.brightness_k.toFixed(1)}</td>
              <td>{h.confidence}</td>
              <td>{h.satellite || "—"}</td>
              <td>{h.frp_mw ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {brief.weather && (
        <p className="meta" style={{ marginTop: 12 }}>
          Weather {brief.weather.place} · {brief.weather.temperature_c}°C · RH {Number(brief.weather.humidity_pct).toFixed(1)}% ·{" "}
          {brief.weather.distance_km} km (max {brief.weather.max_weather_km} km)
        </p>
      )}
      <div className="limits">
        <strong>Limitations</strong>
        <ul>
          {brief.limitations.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
        {brief.legal_strip}
      </div>
      <div className="receipt-box">
        Receipt {brief.receipt?.signature_status} · {shortDigest(brief.receipt?.digest)}
        {!compact && brief.id && !publicView && (
          <>
            {" · "}
            <Link to={`/briefs/${brief.id}`}>open JSON</Link>
          </>
        )}
      </div>
    </article>
  );
}
