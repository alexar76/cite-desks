import { describe, expect, it } from "vitest";
import { CA_BBOX, clipWatchBbox, isValidWatchBbox, project } from "../lib/geo";

describe("geo projection", () => {
  it("places the north-west corner at the origin", () => {
    const p = project(CA_BBOX.north, CA_BBOX.west, CA_BBOX, 100, 50);
    expect(p.x).toBeCloseTo(0);
    expect(p.y).toBeCloseTo(0);
  });

  it("places the south-east corner at the far edge", () => {
    const p = project(CA_BBOX.south, CA_BBOX.east, CA_BBOX, 100, 50);
    expect(p.x).toBeCloseTo(100);
    expect(p.y).toBeCloseTo(50);
  });
});

describe("watch bbox clip", () => {
  it("keeps a legal box", () => {
    const { bbox, clipped } = clipWatchBbox(CA_BBOX);
    expect(clipped).toBe(false);
    expect(isValidWatchBbox(bbox)).toBe(true);
  });

  it("clips oversized width to 40° and height to 30°", () => {
    const { bbox, clipped } = clipWatchBbox({ west: -130, south: 10, east: -70, north: 55 });
    expect(clipped).toBe(true);
    expect(bbox.east - bbox.west).toBe(40);
    expect(bbox.north - bbox.south).toBe(30);
    expect(isValidWatchBbox(bbox)).toBe(true);
  });
});

describe("geo projection", () => {
  it("places the north-west corner at the origin", () => {
    const p = project(CA_BBOX.north, CA_BBOX.west, CA_BBOX, 100, 50);
    expect(p.x).toBeCloseTo(0);
    expect(p.y).toBeCloseTo(0);
  });

  it("places the south-east corner at the far edge", () => {
    const p = project(CA_BBOX.south, CA_BBOX.east, CA_BBOX, 100, 50);
    expect(p.x).toBeCloseTo(100);
    expect(p.y).toBeCloseTo(50);
  });
});
