import { useEffect, useState } from "react";
import type { Map as LeafletMap } from "leaflet";
import { MapContainer, Rectangle, TileLayer, useMap, useMapEvents } from "react-leaflet";
import type { BBox } from "../lib/types";
import { clipWatchBbox, isValidWatchBbox } from "../lib/geo";
import "leaflet/dist/leaflet.css";

type Props = {
  bbox: BBox | null;
  onChange: (bbox: BBox, clipped: boolean) => void;
};

function MapHandle({ onReady }: { onReady: (map: LeafletMap) => void }) {
  const map = useMap();
  useEffect(() => {
    onReady(map);
  }, [map, onReady]);
  return null;
}

function FitBox({ bbox, enabled }: { bbox: BBox | null; enabled: boolean }) {
  const map = useMap();
  useEffect(() => {
    if (!enabled || !bbox || !isValidWatchBbox(bbox)) return;
    map.fitBounds(
      [
        [bbox.south, bbox.west],
        [bbox.north, bbox.east],
      ],
      { padding: [28, 28], maxZoom: 8 },
    );
  }, [map, enabled, bbox?.west, bbox?.south, bbox?.east, bbox?.north]);
  return null;
}

function DrawBox({
  drawing,
  onChange,
}: {
  drawing: boolean;
  onChange: (bbox: BBox, clipped: boolean) => void;
}) {
  const map = useMap();
  const [start, setStart] = useState<{ lat: number; lng: number } | null>(null);
  const [current, setCurrent] = useState<{ lat: number; lng: number } | null>(null);

  useEffect(() => {
    if (drawing) map.dragging.disable();
    else map.dragging.enable();
    map.getContainer().style.cursor = drawing ? "crosshair" : "";
    return () => {
      map.dragging.enable();
      map.getContainer().style.cursor = "";
    };
  }, [drawing, map]);

  useMapEvents({
    mousedown(event) {
      if (!drawing) return;
      setStart(event.latlng);
      setCurrent(event.latlng);
    },
    mousemove(event) {
      if (!drawing || !start) return;
      setCurrent(event.latlng);
    },
    mouseup(event) {
      if (!drawing || !start) return;
      const end = event.latlng;
      const raw: BBox = {
        west: Math.min(start.lng, end.lng),
        south: Math.min(start.lat, end.lat),
        east: Math.max(start.lng, end.lng),
        north: Math.max(start.lat, end.lat),
      };
      setStart(null);
      setCurrent(null);
      if (raw.east - raw.west < 0.01 || raw.north - raw.south < 0.01) return;
      const { bbox, clipped } = clipWatchBbox(raw);
      onChange(bbox, clipped);
    },
  });

  if (!start || !current) return null;
  const bounds: [[number, number], [number, number]] = [
    [Math.min(start.lat, current.lat), Math.min(start.lng, current.lng)],
    [Math.max(start.lat, current.lat), Math.max(start.lng, current.lng)],
  ];
  return (
    <Rectangle bounds={bounds} pathOptions={{ color: "#e85d04", weight: 2, dashArray: "4 4", fillOpacity: 0.08 }} />
  );
}

export function BBoxMap({ bbox, onChange }: Props) {
  const [drawing, setDrawing] = useState(false);
  const [map, setMap] = useState<LeafletMap | null>(null);
  const valid = bbox && isValidWatchBbox(bbox);
  const center: [number, number] = valid ? [(bbox.south + bbox.north) / 2, (bbox.west + bbox.east) / 2] : [37.5, -120];

  return (
    <div>
      <div className="bbox-map">
        <MapContainer center={center} zoom={6} scrollWheelZoom style={{ height: "100%", width: "100%" }}>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
            url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
          />
          <MapHandle onReady={setMap} />
          <FitBox bbox={bbox} enabled={!drawing} />
          <DrawBox
            drawing={drawing}
            onChange={(next, clipped) => {
              setDrawing(false);
              onChange(next, clipped);
            }}
          />
          {valid && (
            <Rectangle
              bounds={[
                [bbox.south, bbox.west],
                [bbox.north, bbox.east],
              ]}
              pathOptions={{ color: "#e85d04", weight: 2, fillColor: "#e85d04", fillOpacity: 0.08 }}
            />
          )}
        </MapContainer>
      </div>
      <div className="row" style={{ marginTop: 10 }}>
        <button className={`btn ${drawing ? "btn-ember" : ""}`} type="button" onClick={() => setDrawing((v) => !v)}>
          {drawing ? "Drag a rectangle, then release" : "Draw box"}
        </button>
        <button
          className="btn"
          type="button"
          onClick={() => {
            if (!map) return;
            const b = map.getBounds();
            const { bbox: next, clipped } = clipWatchBbox({
              west: b.getWest(),
              south: b.getSouth(),
              east: b.getEast(),
              north: b.getNorth(),
            });
            onChange(next, clipped);
          }}
        >
          Use map view
        </button>
        <span className="muted">OSM/Carto base. Rectangle only — no thermal points.</span>
      </div>
    </div>
  );
}
