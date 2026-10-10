export type GeographicPoint = [longitude: number, latitude: number];
export type LandPolygon = GeographicPoint[][];

type Geometry =
  | { type: "Polygon"; arcs: number[][] }
  | { type: "MultiPolygon"; arcs: number[][][] }
  | { type: "GeometryCollection"; geometries: Geometry[] };

export type LandTopology = {
  type: "Topology";
  transform: { scale: GeographicPoint; translate: GeographicPoint };
  objects: { land: Geometry };
  arcs: GeographicPoint[][];
};

/** Decode the small, bundled Natural Earth TopoJSON without a runtime mapping library. */
export function decodeLand(topology: LandTopology): LandPolygon[] {
  const cache = new Map<number, GeographicPoint[]>();
  const arc = (reference: number) => {
    const index = reference < 0 ? ~reference : reference;
    let points = cache.get(index);
    if (!points) {
      let x = 0;
      let y = 0;
      points = topology.arcs[index].map(([dx, dy]): GeographicPoint => {
        x += dx;
        y += dy;
        return [x * topology.transform.scale[0] + topology.transform.translate[0], y * topology.transform.scale[1] + topology.transform.translate[1]];
      });
      cache.set(index, points);
    }
    return reference < 0 ? [...points].reverse() : points;
  };
  const ring = (references: number[]) => references.flatMap((reference, index) => index === 0 ? arc(reference) : arc(reference).slice(1));
  const polygons: LandPolygon[] = [];
  const visit = (geometry: Geometry) => {
    if (geometry.type === "GeometryCollection") geometry.geometries.forEach(visit);
    else if (geometry.type === "Polygon") polygons.push(geometry.arcs.map(ring));
    else geometry.arcs.forEach((polygon) => polygons.push(polygon.map(ring)));
  };
  visit(topology.objects.land);
  return polygons;
}
