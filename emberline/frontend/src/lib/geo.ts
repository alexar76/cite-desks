import type { BBox } from "./types";

export function project(lat: number, lon: number, bbox: BBox, width: number, height: number) {
  const x = ((lon - bbox.west) / (bbox.east - bbox.west)) * width;
  const y = ((bbox.north - lat) / (bbox.north - bbox.south)) * height;
  return { x, y };
}

export function latLonToVec3(lat: number, lon: number, radius: number) {
  const phi = (90 - lat) * (Math.PI / 180);
  const theta = (lon + 180) * (Math.PI / 180);
  return {
    x: -radius * Math.sin(phi) * Math.cos(theta),
    y: radius * Math.cos(phi),
    z: radius * Math.sin(phi) * Math.sin(theta),
  };
}

export function formatCoord(value: number, axis: "lat" | "lon") {
  const hemi = axis === "lat" ? (value >= 0 ? "N" : "S") : value >= 0 ? "E" : "W";
  return `${Math.abs(value).toFixed(3)}° ${hemi}`;
}

export function clipWatchBbox(bbox: BBox): { bbox: BBox; clipped: boolean } {
  let west = bbox.west;
  let south = bbox.south;
  let east = bbox.east;
  let north = bbox.north;
  if (east < west) [west, east] = [east, west];
  if (north < south) [south, north] = [north, south];
  let clipped = false;
  if (east - west > 40) {
    east = west + 40;
    clipped = true;
  }
  if (north - south > 30) {
    north = south + 30;
    clipped = true;
  }
  return {
    bbox: {
      west: Number(west.toFixed(6)),
      south: Number(south.toFixed(6)),
      east: Number(east.toFixed(6)),
      north: Number(north.toFixed(6)),
    },
    clipped,
  };
}

export function isValidWatchBbox(bbox: BBox) {
  return (
    Number.isFinite(bbox.west) &&
    Number.isFinite(bbox.south) &&
    Number.isFinite(bbox.east) &&
    Number.isFinite(bbox.north) &&
    bbox.west < bbox.east &&
    bbox.south < bbox.north &&
    bbox.west >= -180 &&
    bbox.east <= 180 &&
    bbox.south >= -90 &&
    bbox.north <= 90 &&
    bbox.east - bbox.west <= 40 &&
    bbox.north - bbox.south <= 30
  );
}

export const CA_BBOX: BBox = { west: -125, south: 32, east: -114, north: 42 };

export const DEMO_POINTS = [
  { lat: 37.6584, lon: -121.3797, k: 367 },
  { lat: 41.1407, lon: -123.6132, k: 354 },
  { lat: 36.2422, lon: -121.7151, k: 350 },
  { lat: 39.3681, lon: -121.6274, k: 345 },
  { lat: 32.4977, lon: -116.8362, k: 345 },
  { lat: 38.4477, lon: -121.9078, k: 334 },
  { lat: 39.7995, lon: -117.5942, k: 321 },
];
