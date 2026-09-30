import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { feature } from 'topojson-client';
import { SEVERITY_HEX, severityOf } from '../lib/severity';
import { satCategoryOf, SAT_CATEGORIES } from '../lib/satellites';
import type { EventItem, FlightArc, RegionMapPoint, SatelliteTrack } from '../api/client';

interface GlobeProps {
  regions: RegionMapPoint[];
  flights: FlightArc[];
  satellites: SatelliteTrack[];
  events: EventItem[];
  selectedRegionId: string | null;
  onSelectRegion: (id: string | null) => void;
  /** Categories to render; empty set hides the layer. Undefined = all. */
  visibleSatCategories?: Set<string>;
}

const R = 1; // globe radius

/** lat/lon (degrees) -> position on the sphere */
function latLonToVec3(lat: number, lon: number, radius = R): THREE.Vector3 {
  const phi = (90 - lat) * (Math.PI / 180);
  const theta = (lon + 180) * (Math.PI / 180);
  return new THREE.Vector3(
    -radius * Math.sin(phi) * Math.cos(theta),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta)
  );
}

/** Convert lon/lat (degrees) to a 3D position — matches latLonToVec3. */
function lonLatToVec3(lon: number, lat: number, radius = R): THREE.Vector3 {
  return latLonToVec3(lat, lon, radius);
}

/** Build filled land meshes + border lines from world-atlas TopoJSON. */
function buildLandGeometry(topo: unknown): {
  landGroup: THREE.Group;
} {
  const landGroup = new THREE.Group();
  const landColor = 0x2d4a22; // forest green
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const countries = (feature as any)(
    topo,
    (topo as { objects: Record<string, unknown> }).objects['countries']
  ) as GeoJSON.FeatureCollection<GeoJSON.Polygon | GeoJSON.MultiPolygon>;

  for (const country of countries.features) {
    const geometry = country.geometry;
    if (!geometry) continue;
    const polys: number[][][][] =
      geometry.type === 'Polygon'
        ? [geometry.coordinates as number[][][]]
        : (geometry.coordinates as number[][][][]);

    for (const poly of polys) {
      // Filled triangulated surface (outer ring; holes are rare at 110m)
      const outer = poly[0] as [number, number][];
      const triangles = triangulateRing(outer);
      if (triangles.length > 0) {
        const geo = new THREE.BufferGeometry();
        const pos = new Float32Array(triangles.length * 3);
        triangles.forEach((v, i) => {
          pos[i * 3] = v.x;
          pos[i * 3 + 1] = v.y;
          pos[i * 3 + 2] = v.z;
        });
        geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
        geo.computeVertexNormals();
        landGroup.add(
          new THREE.Mesh(
            geo,
            new THREE.MeshBasicMaterial({
              color: landColor,
              side: THREE.DoubleSide,
            })
          )
        );
      }

      // Borders
      for (const ring of poly) {
        const pts = ring.map(([lon, lat]) => lonLatToVec3(lon, lat, R * 1.003));
        const geo = new THREE.BufferGeometry().setFromPoints(pts);
        landGroup.add(
          new THREE.Line(
            geo,
            new THREE.LineBasicMaterial({
              color: 0x9fd0a0,
              transparent: true,
              opacity: 0.35,
            })
          )
        );
      }
    }
  }
  return { landGroup };
}

function pointInTri(
  p: [number, number],
  a: [number, number],
  b: [number, number],
  c: [number, number]
): boolean {
  const sign = (
    o: [number, number],
    d: [number, number],
    e: [number, number]
  ) => (d[0] - o[0]) * (e[1] - o[1]) - (d[1] - o[1]) * (e[0] - o[0]);
  const d1 = sign(p, a, b);
  const d2 = sign(p, b, c);
  const d3 = sign(p, c, a);
  const hasNeg = d1 < 0 || d2 < 0 || d3 < 0;
  const hasPos = d1 > 0 || d2 > 0 || d3 > 0;
  return !(hasNeg && hasPos);
}

/** One ear-clipping pass in a fixed orientation. */
function clipLoop(
  pts: [number, number][]
): [number, number][][] {
  const idx: number[] = pts.map((_, i) => i);
  const triangles: [number, number][][] = [];
  let guard = 0;
  while (idx.length > 3 && guard++ < 20000) {
    let clipped = false;
    for (let i = 0; i < idx.length; i++) {
      const i0 = idx[(i - 1 + idx.length) % idx.length];
      const i1 = idx[i];
      const i2 = idx[(i + 1) % idx.length];
      const a = pts[i0];
      const b = pts[i1];
      const c = pts[i2];
      // Convex ear check
      if ((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) <= 0)
        continue;
      // No other point inside this ear
      let contains = false;
      for (const j of idx) {
        if (j === i0 || j === i1 || j === i2) continue;
        if (pointInTri(pts[j], a, b, c)) {
          contains = true;
          break;
        }
      }
      if (contains) continue;
      triangles.push([a, b, c]);
      idx.splice(i, 1);
      clipped = true;
      break;
    }
    if (!clipped) break; // stuck: wrong orientation or degenerate
  }
  if (idx.length === 3) {
    triangles.push([pts[idx[0]], pts[idx[1]], pts[idx[2]]]);
  }
  return triangles;
}

/**
 * Ear-clipping triangulation of a 2D ring. Orientation-agnostic: if the
 * first pass clips nothing, retry reversed — the shoelace sign and the
 * ear-test convention disagree on some real-world rings.
 */
function earClip(ring: [number, number][]): [number, number][][] {
  if (ring.length < 3) return [];
  const forward = clipLoop(ring);
  if (forward.length > 0) return forward;
  return clipLoop([...ring].reverse());
}

const MAX_TRI_ANGLE = (5 * Math.PI) / 180;

/** Recursively subdivide a spherical triangle until edges hug the surface. */
function subdivideTriangle(
  a: THREE.Vector3,
  b: THREE.Vector3,
  c: THREE.Vector3,
  out: THREE.Vector3[]
): void {
  const maxEdge = Math.max(a.angleTo(b), b.angleTo(c), c.angleTo(a));
  if (maxEdge <= MAX_TRI_ANGLE) {
    out.push(a, b, c);
    return;
  }
  const mid = (p: THREE.Vector3, q: THREE.Vector3) =>
    p
      .clone()
      .add(q)
      .multiplyScalar(0.5)
      .normalize()
      .multiplyScalar(R * 1.002);
  const ab = mid(a, b);
  const bc = mid(b, c);
  const ca = mid(c, a);
  subdivideTriangle(a, ab, ca, out);
  subdivideTriangle(ab, b, bc, out);
  subdivideTriangle(ca, bc, c, out);
  subdivideTriangle(ab, bc, ca, out);
}

/**
 * Make longitudes continuous (e.g. 179 -> -179 becomes 179 -> 181) so
 * antimeridian-crossing rings (Fiji, Russia, USA) triangulate correctly.
 * The sphere is periodic, so unwrapped values still lift correctly.
 */
function unwrapRing(rawRing: [number, number][]): [number, number][] {
  // GeoJSON rings repeat the first point at the end; drop it and any
  // consecutive duplicates — zero-area segments stall ear clipping.
  const ring = [...rawRing];
  while (ring.length > 1 && ring[0][0] === ring[ring.length - 1][0] && ring[0][1] === ring[ring.length - 1][1]) {
    ring.pop();
  }
  const deduped = ring.filter(
    (p, i) => i === 0 || p[0] !== ring[i - 1][0] || p[1] !== ring[i - 1][1]
  );
  if (deduped.length < 3) return deduped;

  const out: [number, number][] = [];
  let offset = 0;
  let prev = deduped[0][0];
  for (const [lon, lat] of deduped) {
    let l = lon + offset;
    if (l - prev > 180) {
      offset -= 360;
      l -= 360;
    } else if (l - prev < -180) {
      offset += 360;
      l += 360;
    }
    out.push([l, lat]);
    prev = l;
  }
  return out;
}

/**
 * Triangulate a lon/lat ring into a triangle soup of sphere-surface vectors.
 * Ear-clips in 2D (correct for concave shapes), then lifts and subdivides
 * each triangle on the sphere so land never dips below the ocean.
 */
function triangulateRing(rawRing: [number, number][]): THREE.Vector3[] {
  const ring = unwrapRing(rawRing);
  const triangles2d = earClip(ring);
  const soup: THREE.Vector3[] = [];
  for (const [a, b, c] of triangles2d) {
    const lift = ([lon, lat]: [number, number]) =>
      lonLatToVec3(lon, lat, R * 1.002);
    subdivideTriangle(lift(a), lift(b), lift(c), soup);
  }
  return soup;
}

function severityColor(score: number): number {
  return SEVERITY_HEX[severityOf(score)];
}

/** Great-circle-ish arc between two surface points with altitude bulge. */
function arcCurve(start: THREE.Vector3, end: THREE.Vector3): THREE.QuadraticBezierCurve3 {
  const dist = start.distanceTo(end);
  const mid = start
    .clone()
    .add(end)
    .multiplyScalar(0.5)
    .normalize()
    .multiplyScalar(R + Math.max(0.08, dist * 0.35));
  return new THREE.QuadraticBezierCurve3(start, mid, end);
}

export const Globe: React.FC<GlobeProps> = ({
  regions,
  flights,
  satellites,
  events,
  selectedRegionId,
  onSelectRegion,
  visibleSatCategories,
}) => {
  const mountRef = useRef<HTMLDivElement>(null);

  // Mutable refs shared with the render loop
  const refs = useRef<{
    scene?: THREE.Scene;
    camera?: THREE.PerspectiveCamera;
    renderer?: THREE.WebGLRenderer;
    controls?: OrbitControls;
    globeGroup?: THREE.Group; // rotates
    regionMarkers?: THREE.Group;
    arcsGroup?: THREE.Group;
    satsGroup?: THREE.Group;
    eventsGroup?: THREE.Group;
    arcClock?: number;
  }>({});
  const dataRef = useRef({ regions, flights, satellites, events, selectedRegionId });
  useEffect(() => {
    dataRef.current = { regions, flights, satellites, events, selectedRegionId };
  }, [regions, flights, satellites, events, selectedRegionId]);

  /* ---------------- one-time scene bootstrap ---------------- */
  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(
      42,
      mount.clientWidth / Math.max(mount.clientHeight, 1),
      0.1,
      100
    );
    camera.position.set(0, 0.9, 2.9);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    mount.appendChild(renderer.domElement);

    // rotating group so markers/arcs stay glued to the surface
    const globeGroup = new THREE.Group();
    scene.add(globeGroup);

    const globe = new THREE.Mesh(
      new THREE.SphereGeometry(R, 64, 64),
      new THREE.MeshBasicMaterial({ color: 0x0c1a2e })
    );
    globeGroup.add(globe);

    // Real world land + country borders (bundled Natural Earth data)
    let landGroup: THREE.Group | null = null;
    fetch('/world-atlas.json')
      .then((res) => res.json())
      .then((topo) => {
        landGroup = buildLandGeometry(topo).landGroup;
        globeGroup.add(landGroup);
      })
      .catch((err) => console.warn('Failed to load world map data', err));

    const atmosphere = new THREE.Mesh(
      new THREE.SphereGeometry(R * 1.09, 48, 48),
      new THREE.MeshBasicMaterial({
        color: 0x38bdf8,
        transparent: true,
        opacity: 0.07,
        side: THREE.BackSide,
      })
    );
    scene.add(atmosphere);

    // starfield
    const starCount = 900;
    const positions = new Float32Array(starCount * 3);
    for (let i = 0; i < starCount; i++) {
      const r = 10 + Math.random() * 10;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = r * Math.cos(phi);
      positions[i * 3 + 2] = r * Math.sin(phi) * Math.sin(theta);
    }
    const starGeo = new THREE.BufferGeometry();
    starGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    scene.add(new THREE.Points(starGeo, new THREE.PointsMaterial({ color: 0x64748b, size: 0.02 })));

    const regionMarkers = new THREE.Group();
    regionMarkers.name = 'regionMarkers';
    const arcsGroup = new THREE.Group();
    const satsGroup = new THREE.Group();
    const eventsGroup = new THREE.Group();
    globeGroup.add(regionMarkers, arcsGroup, satsGroup, eventsGroup);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.enablePan = false;
    controls.minDistance = 1.5;
    controls.maxDistance = 6;
    controls.rotateSpeed = 0.5;

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();

    // Hover tooltip for satellites + region markers
    let tooltip: HTMLDivElement | null = null;
    const ensureTooltip = () => {
      if (tooltip) return tooltip;
      tooltip = document.createElement('div');
      tooltip.className =
        'pointer-events-none absolute z-40 rounded-md border border-slate-600 bg-slate-900/95 px-2 py-1 text-[10px] text-slate-100 shadow-xl';
      tooltip.style.display = 'none';
      mount.appendChild(tooltip);
      return tooltip;
    };

    const onPointerMove = (ev: MouseEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);

      const satHits = raycaster.intersectObjects(satsGroup.children, false);
      const regionHits = raycaster.intersectObjects(regionMarkers.children, false);
      const sat = satHits[0];
      const region = regionHits[0];

      let text = '';
      if (sat && (!region || sat.distance <= region.distance)) {
        const name = (sat.object.userData.satName as string) ?? 'Satellite';
        const cat = (sat.object.userData.category as string) ?? 'other';
        text = `<b>${name}</b><br/><span style="color:#94a3b8">${cat}</span>`;
      } else if (region) {
        const id = region.object.userData.regionId as string;
        const r = dataRef.current.regions.find((x) => x.id === id);
        if (r) {
          text = `<b>${r.name}</b><br/><span style="color:#94a3b8">index ${r.composite_index.toFixed(
            1
          )} · ${r.severity_label}</span>`;
        }
      }

      const tip = ensureTooltip();
      if (text) {
        tip.innerHTML = text;
        tip.style.display = 'block';
        const mountRect = mount.getBoundingClientRect();
        tip.style.left = `${ev.clientX - mountRect.left + 12}px`;
        tip.style.top = `${ev.clientY - mountRect.top + 12}px`;
        renderer.domElement.style.cursor = 'pointer';
      } else {
        tip.style.display = 'none';
        renderer.domElement.style.cursor = 'grab';
      }
    };
    renderer.domElement.addEventListener('pointermove', onPointerMove);

    const onClick = (ev: MouseEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const satHits = raycaster.intersectObjects(satsGroup.children, false);
      const regionHits = raycaster.intersectObjects(regionMarkers.children, false);
      // Satellites win ties; regions select on click.
      if (regionHits.length > 0 && (satHits.length === 0 || regionHits[0].distance < satHits[0].distance)) {
        const id = regionHits[0].object.userData.regionId as string;
        onSelectRegion(id === dataRef.current.selectedRegionId ? null : id);
      }
    };
    renderer.domElement.addEventListener('click', onClick);

    Object.assign(refs.current, {
      scene,
      camera,
      renderer,
      controls,
      globeGroup,
      regionMarkers,
      arcsGroup,
      satsGroup,
      eventsGroup,
      arcClock: 0,
    });

    let frame = 0;
    const animate = () => {
      frame = requestAnimationFrame(animate);
      controls.update();
      globeGroup.rotation.y += 0.0007;
      renderer.render(scene, camera);
    };
    animate();

    const onResize = () => {
      if (!mount.clientWidth) return;
      camera.aspect = mount.clientWidth / Math.max(mount.clientHeight, 1);
      camera.updateProjectionMatrix();
      renderer.setSize(mount.clientWidth, mount.clientHeight);
    };
    window.addEventListener('resize', onResize);

    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('resize', onResize);
      renderer.domElement.removeEventListener('click', onClick);
      renderer.domElement.removeEventListener('pointermove', onPointerMove);
      if (tooltip && tooltip.parentElement === mount) mount.removeChild(tooltip);
      tooltip = null;
      controls.dispose();
      renderer.dispose();
      if (renderer.domElement.parentElement === mount) mount.removeChild(renderer.domElement);
      refs.current = {};
    };
  }, [onSelectRegion]);

  /* ---------------- sync region markers ---------------- */
  useEffect(() => {
    const { regionMarkers } = refs.current;
    if (!regionMarkers) return;
    regionMarkers.clear();

    for (const region of regions) {
      const pos = latLonToVec3(region.lat, region.lon, R * 1.005);
      const color = severityColor(region.composite_index);
      const isHot = severityOf(region.composite_index) !== 'normal';
      const marker = new THREE.Mesh(
        new THREE.SphereGeometry(isHot ? 0.022 : 0.014, 16, 16),
        new THREE.MeshBasicMaterial({ color })
      );
      marker.position.copy(pos);
      marker.userData = { regionId: region.id };
      regionMarkers.add(marker);

      // pulsing ring for hot regions
      if (isHot) {
        const ring = new THREE.Mesh(
          new THREE.RingGeometry(0.03, 0.045, 32),
          new THREE.MeshBasicMaterial({
            color,
            transparent: true,
            opacity: 0.5,
            side: THREE.DoubleSide,
          })
        );
        ring.position.copy(pos);
        ring.lookAt(0, 0, 0);
        ring.userData = { regionId: region.id, isRing: true };
        regionMarkers.add(ring);
      }

      // selection highlight
      if (region.id === selectedRegionId) {
        const halo = new THREE.Mesh(
          new THREE.RingGeometry(0.05, 0.075, 40),
          new THREE.MeshBasicMaterial({
            color: 0xf8fafc,
            transparent: true,
            opacity: 0.9,
            side: THREE.DoubleSide,
          })
        );
        halo.position.copy(pos);
        halo.lookAt(0, 0, 0);
        regionMarkers.add(halo);
      }
    }
  }, [regions, selectedRegionId]);

  /* ---------------- sync flight arcs ---------------- */
  useEffect(() => {
    const { arcsGroup } = refs.current;
    if (!arcsGroup) return;
    arcsGroup.clear();

    for (const flight of flights) {
      const start = latLonToVec3(flight.origin.lat, flight.origin.lon, R * 1.002);
      const end = latLonToVec3(flight.destination.lat, flight.destination.lon, R * 1.002);
      const curve = arcCurve(start, end);
      const points = curve.getPoints(64);

      // Faint full route arc
      const routeGeo = new THREE.BufferGeometry().setFromPoints(points);
      arcsGroup.add(
        new THREE.Line(
          routeGeo,
          new THREE.LineBasicMaterial({
            color: 0x38bdf8,
            transparent: true,
            opacity: 0.22,
          })
        )
      );

      // Aircraft at its true position when known (live ADS-B);
      // fall back to progress point along the arc for simulated tracks.
      let planePos: THREE.Vector3;
      if (flight.position) {
        planePos = latLonToVec3(flight.position.lat, flight.position.lon, R * 1.012);
      } else {
        const upto = Math.max(2, Math.floor(points.length * Math.min(flight.progress, 1)));
        planePos = points[Math.min(upto - 1, points.length - 1)];
      }
      const isLive = flight.source === 'adsb.lol';
      const plane = new THREE.Mesh(
        isLive ? new THREE.ConeGeometry(0.012, 0.032, 6) : new THREE.SphereGeometry(0.011, 8, 8),
        new THREE.MeshBasicMaterial({ color: isLive ? 0xf8fafc : 0xe2e8f0 })
      );
      plane.position.copy(planePos);
      // Point cones along the aircraft heading, laying flat on the globe
      if (isLive && flight.heading_deg != null) {
        const up = planePos.clone().normalize();
        plane.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), up);
        plane.rotateY((-flight.heading_deg * Math.PI) / 180);
      }
      arcsGroup.add(plane);
    }
  }, [flights]);

  /* ---------------- sync satellites ---------------- */
  useEffect(() => {
    const { satsGroup } = refs.current;
    if (!satsGroup) return;
    satsGroup.clear();

    const visible = visibleSatCategories
      ? satellites.filter((s) => visibleSatCategories.has(satCategoryOf(s.category)))
      : satellites;

    // With a dense constellation, show all markers but keep orbit rings
    // subtle so the shell reads as a swarm, not a tangle.
    const dense = visible.length > 15;
    for (const sat of visible) {
      const cat = satCategoryOf(sat.category);
      const color = SAT_CATEGORIES[cat].hex;
      const alt = Math.min(Math.max(sat.altitude_km / 20000, 0.08), 0.35);
      const pos = latLonToVec3(sat.lat, sat.lon, R + alt);
      const marker = new THREE.Mesh(
        new THREE.OctahedronGeometry(dense ? 0.013 : 0.02),
        new THREE.MeshBasicMaterial({ color })
      );
      marker.position.copy(pos);
      marker.userData = { satName: sat.name, category: cat };
      satsGroup.add(marker);

      if (!dense) {
        // Detailed ring only when few satellites are shown
        const ring = new THREE.Mesh(
          new THREE.RingGeometry(R + alt - 0.004, R + alt + 0.004, 96),
          new THREE.MeshBasicMaterial({
            color,
            transparent: true,
            opacity: 0.25,
            side: THREE.DoubleSide,
          })
        );
        ring.rotation.x = Math.PI / 2.4;
        satsGroup.add(ring);
      }
    }
    if (dense) {
      // One soft shell at LEO altitude suggesting the constellation band
      const shell = new THREE.Mesh(
        new THREE.SphereGeometry(R + 0.09, 48, 48),
        new THREE.MeshBasicMaterial({
          color: 0xfbbf24,
          transparent: true,
          opacity: 0.03,
          side: THREE.BackSide,
        })
      );
      satsGroup.add(shell);
    }
  }, [satellites, visibleSatCategories]);

  /* ---------------- sync event dots ---------------- */
  useEffect(() => {
    const { eventsGroup } = refs.current;
    if (!eventsGroup) return;
    eventsGroup.clear();

    for (const event of events) {
      const pos = latLonToVec3(event.lat, event.lon, R * 1.004);
      const color =
        event.severity.toLowerCase() === 'high'
          ? 0xf43f5e
          : event.severity.toLowerCase() === 'medium'
            ? 0xfbbf24
            : 0x94a3b8;
      const dot = new THREE.Mesh(
        new THREE.SphereGeometry(0.01, 8, 8),
        new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.9 })
      );
      dot.position.copy(pos);
      eventsGroup.add(dot);
    }
  }, [events]);

  return <div ref={mountRef} className="h-full w-full cursor-grab active:cursor-grabbing" />;
};
