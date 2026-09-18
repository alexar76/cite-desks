import { Canvas, useFrame } from "@react-three/fiber";
import { Line, OrbitControls, useTexture } from "@react-three/drei";
import { Suspense, useLayoutEffect, useMemo, useRef, type ReactNode } from "react";
import * as THREE from "three";
import { CA_BBOX, DEMO_POINTS, latLonToVec3 } from "../lib/geo";

function glowTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = 128;
  canvas.height = 128;
  const ctx = canvas.getContext("2d")!;
  const gradient = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
  gradient.addColorStop(0, "rgba(255, 196, 120, 0.7)");
  gradient.addColorStop(0.28, "rgba(255, 140, 72, 0.28)");
  gradient.addColorStop(0.62, "rgba(255, 110, 48, 0.08)");
  gradient.addColorStop(1, "rgba(255, 90, 28, 0)");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, 128, 128);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function EarthFallback() {
  return (
    <mesh>
      <sphereGeometry args={[1, 64, 64]} />
      <meshStandardMaterial color="#2c3a36" roughness={0.7} metalness={0.04} />
    </mesh>
  );
}

function Earth() {
  const color = useTexture("/earth-day.jpg");
  useLayoutEffect(() => {
    color.colorSpace = THREE.SRGBColorSpace;
    color.anisotropy = 8;
    color.needsUpdate = true;
  }, [color]);
  return (
    <mesh>
      <sphereGeometry args={[1, 96, 96]} />
      <meshStandardMaterial map={color} roughness={0.58} metalness={0.02} />
    </mesh>
  );
}

function Atmosphere() {
  return (
    <mesh scale={1.028}>
      <sphereGeometry args={[1, 64, 64]} />
      <meshBasicMaterial color="#8fb4d4" transparent opacity={0.08} side={THREE.BackSide} depthWrite={false} />
    </mesh>
  );
}

function WatchFrame() {
  const points = useMemo(() => {
    const { west, south, east, north } = CA_BBOX;
    const corners = [
      [north, west],
      [north, east],
      [south, east],
      [south, west],
      [north, west],
    ] as const;
    return corners.map(([lat, lon]) => {
      const v = latLonToVec3(lat, lon, 1.008);
      return [v.x, v.y, v.z] as [number, number, number];
    });
  }, []);
  return <Line points={points} color="#ff7a3c" lineWidth={1.2} />;
}

function Ember({
  lat,
  lon,
  k,
  seed,
  sprite,
}: {
  lat: number;
  lon: number;
  k: number;
  seed: number;
  sprite: THREE.Texture;
}) {
  const core = useRef<THREE.Mesh>(null);
  const glow = useRef<THREE.Sprite>(null);
  const position = useMemo(() => {
    const v = latLonToVec3(lat, lon, 1.014);
    return [v.x, v.y, v.z] as [number, number, number];
  }, [lat, lon]);
  const hot = k > 350;
  const radius = 0.0078 + (k - 320) / 4200;

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    const energy = 0.5 + 0.38 * Math.sin(t * 1.9 + seed) + 0.12 * Math.sin(t * 3.3 + seed * 1.5);
    if (core.current) {
      core.current.scale.setScalar(0.9 + energy * 0.28);
      (core.current.material as THREE.MeshBasicMaterial).opacity = 0.62 + energy * 0.32;
    }
    if (glow.current) {
      const size = radius * (8.2 + energy * 3.4);
      glow.current.scale.set(size, size, 1);
      glow.current.material.opacity = 0.26 + energy * 0.3;
    }
  });

  return (
    <group position={position}>
      <mesh ref={core}>
        <sphereGeometry args={[radius, 10, 10]} />
        <meshBasicMaterial color={hot ? "#ff8a4c" : "#e8a54a"} transparent opacity={0.85} depthWrite={false} />
      </mesh>
      <sprite ref={glow} scale={[radius * 9, radius * 9, 1]}>
        <spriteMaterial
          map={sprite}
          color={hot ? "#ff8a4c" : "#e8a54a"}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          opacity={0.4}
        />
      </sprite>
    </group>
  );
}

function EmberField() {
  const sprite = useMemo(() => glowTexture(), []);
  return (
    <group>
      {DEMO_POINTS.map((point, i) => (
        <Ember key={`${point.lat}-${point.lon}`} {...point} seed={i * 1.73 + 0.4} sprite={sprite} />
      ))}
    </group>
  );
}

function WeatherPin() {
  const core = useRef<THREE.Mesh>(null);
  const position = useMemo(() => {
    const v = latLonToVec3(37.6196, -122.3748, 1.016);
    return [v.x, v.y, v.z] as [number, number, number];
  }, []);

  useFrame(({ clock }) => {
    if (!core.current) return;
    const wave = 0.5 + 0.5 * Math.sin(clock.getElapsedTime() * 1.6);
    (core.current.material as THREE.MeshBasicMaterial).opacity = 0.55 + wave * 0.35;
  });

  return (
    <mesh ref={core} position={position}>
      <sphereGeometry args={[0.007, 10, 10]} />
      <meshBasicMaterial color="#3dd6c6" transparent opacity={0.8} depthWrite={false} />
    </mesh>
  );
}

function CaliforniaFacing({ children }: { children: ReactNode }) {
  const quaternion = useMemo(() => {
    const v = latLonToVec3(37.7, -120.4, 1);
    return new THREE.Quaternion().setFromUnitVectors(
      new THREE.Vector3(v.x, v.y, v.z).normalize(),
      new THREE.Vector3(0, 0, 1),
    );
  }, []);
  return <group quaternion={quaternion}>{children}</group>;
}

export function Globe() {
  return (
    <div className="globe-wrap">
      <Canvas
        camera={{ position: [0.18, 0.04, 3.15], fov: 30, near: 0.4, far: 20 }}
        dpr={[1, 1.5]}
        frameloop="always"
        gl={{ antialias: true, alpha: true, toneMapping: THREE.NoToneMapping }}
        onCreated={({ gl }) => {
          gl.setClearColor(0x1a1612, 0);
        }}
        style={{ background: "transparent" }}
      >
        <ambientLight intensity={0.75} />
        <directionalLight position={[2.2, 1.2, 2.8]} intensity={1.55} color="#fff6ea" />
        <CaliforniaFacing>
          <Suspense fallback={<EarthFallback />}>
            <Earth />
          </Suspense>
          <Atmosphere />
          <WatchFrame />
          <EmberField />
          <WeatherPin />
        </CaliforniaFacing>
        <OrbitControls enablePan={false} enableZoom={false} autoRotate autoRotateSpeed={0.28} />
      </Canvas>
      <div className="globe-hud">
        <span>Earth</span>
        <span>California corridor</span>
        <span className="live">LIVE 152</span>
        <span>367 K</span>
      </div>
      <div className="globe-caption">NASA Blue Marble · LIVE FIRMS points · bbox only · no perimeter</div>
    </div>
  );
}
