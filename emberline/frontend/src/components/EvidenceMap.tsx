import type { BBox, Hotspot } from "../lib/types";
import { project } from "../lib/geo";

type Props = {
  bbox: BBox;
  hotspots?: Hotspot[];
  weather?: { lat?: number; lon?: number } | null;
};

export function EvidenceMap({ bbox, hotspots = [], weather }: Props) {
  const w = 720;
  const h = 460;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="map-frame" role="img" aria-label="Watch box with detection points">
      <defs>
        <radialGradient id="glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#ff6b35" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#ff6b35" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width={w} height={h} fill="#100c0a" />
      {Array.from({ length: 12 }).map((_, i) => (
        <g key={i} stroke="rgba(244,236,224,0.05)">
          <line x1={0} y1={(h / 12) * i} x2={w} y2={(h / 12) * i} />
          <line x1={(w / 12) * i} y1={0} x2={(w / 12) * i} y2={h} />
        </g>
      ))}
      <rect x={18} y={18} width={w - 36} height={h - 36} fill="none" stroke="#e85d04" strokeDasharray="5 4" />
      {hotspots.map((pt) => {
        const p = project(pt.lat, pt.lon, bbox, w, h);
        const r = 3.5 + pt.brightness_k / 180;
        return (
          <g key={pt.id}>
            <circle cx={p.x} cy={p.y} r={r * 3} fill="url(#glow)" opacity={0.35} />
            <circle cx={p.x} cy={p.y} r={r} fill="#ff6b35" />
          </g>
        );
      })}
      {weather?.lat != null && weather.lon != null && (
        <circle
          cx={project(weather.lat, weather.lon, bbox, w, h).x}
          cy={project(weather.lat, weather.lon, bbox, w, h).y}
          r={5}
          fill="#3dd6c6"
        />
      )}
      <text x={24} y={h - 20} fill="#8a7b6d" fontSize="11" fontFamily="IBM Plex Mono, monospace">
        {bbox.west} , {bbox.south} → {bbox.east} , {bbox.north} · points only
      </text>
    </svg>
  );
}
