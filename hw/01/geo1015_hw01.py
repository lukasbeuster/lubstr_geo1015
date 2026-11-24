# -- geo1015.2026.hw01
# -- Lukas Beuster
# -- 924055

import argparse
import json
import random
import sys
from typing import Any
import math

import rasterio
import startinpy


def main() -> None:
    parser = argparse.ArgumentParser(description="My GEO1015.2026 hw01")
    parser.add_argument("inputfile", type=str, help="GeoTIFF")
    parser.add_argument(
        "thinning",
        type=float,
        help="Thinning factor (between 0 and 1: 0.0 = none kept, 1.0 = 100% kept)",
    )
    parser.add_argument(
        "range", type=str, help="a Python range for the contours, eg: (0, 1000, 100)"
    )

    args: argparse.Namespace = parser.parse_args()

    # Validate thinning factor
    if not 0 <= args.thinning <= 1:
        parser.error("Thinning factor must be between 0 and 1")
    # Validate the range
    tmp: list[int]
    try:
        tmp = list(map(int, args.range.strip("() ").split(",")))
    except:
        parser.error("range invalid")
    myrange: range = range(tmp[0], tmp[1], tmp[2]) # Only for 3? Potential to fix... 
    print("Extracting the contours at:", list(myrange))

    # -- load in memory the input GeoTIFF
    try:
        # -- this gives you a Rasterio dataset
        # -- https://rasterio.readthedocs.io/en/latest/quickstart.html
        d: rasterio.io.DatasetReader = rasterio.open(args.inputfile)
    except Exception as e:
        print(e)
        sys.exit()

    print("name:", d.name)
    print("crs:", d.crs)
    print("size:", d.shape)
    print("no_data:", d.nodata)
    
    band1 = d.read(1) # Read first layer of raster file
    # print(band1)
    t = d.transform # Gets the local transformation.
    # print(f'Transform 2 (Origin x?): {t[2]}, Transform 5 (Origin y?): {t[5]} and Transform 0 (cell size x?): {t[0]}, and Transform 4 (pixel size y?): {t[4]}')
    pts = [] #Empty pt list to fill
    # print(band1.shape[0])
    for i in range(band1.shape[0]): # For each x coordinate (or y?)
        for j in range(band1.shape[1]): # For each y coordinate (or x?), do something. How do nested loops work again?
            x = t[2] + (j * t[0]) + (t[0] / 2) # Retreives the x of the cell centre coordinate. origin x + (x cell count * cell size) + (x cell count /2) - but what is origin? I need a visual example of this.
            y = t[5] + (i * t[4]) + (t[4] / 2) # Same as above, but with the y coordinate, and with the y size (negative).
            z = band1[i][j] # Extracts the z coordinate for this cell.
            if (z != d.nodata): # Removed randomness. 
                pts.append([x, y, z]) # Adds to the list of centre coordinates, including the z coordinate.
    
    n =  int(args.thinning*(band1.shape[0]*band1.shape[1]))
    
    if n > len(pts):
        print(f'Sample is larger than possible population (Expected sample: {n} > valid points). All {len(pts)} valid points returned, ')
    else:
        pts = random.sample(pts, n)


    # -- create the TIN
    # -- full docs: https://startinpy.readthedocs.io
    dt = startinpy.DT()
    dt.insert(pts, insertionstrategy="BBox")

    # -- visit the triangles
    trs = dt.triangles
    # Polyscope uses 0-based indexing, and startinpy returns 1-based indices for triangles.
    # We need to adjust the indices to be 0-based. # What impact does this have downstream?
    # trs = trs - 1 # NOTE: remove before getting out. Solved with pts[0] = pts[1] before triangulation in the 3D vis example.
    
    one_triangle = trs[0]
    first_vertex = one_triangle[0]
    print("z-coordinate of first vertex: ", dt.points[first_vertex][2])
    
    print(dt.triangles[1])
    
    # -- Looping through the triangles
    
    dtpts = dt.points   # copy of points to avoid making copies for each call in the loop
    dttrs = dt.triangles # same as above. 
    
    features = []                              # empty "bag" that will hold one GeoJSON feature per contour segment
    for z0 in myrange:                         # OUTER loop: each contour height, eg 100, 200, 300 ...
        for tr in dt.dttrs:                # INNER loop: each triangle; tr = 3 row numbers into dt.points, eg [17, 4, 230]
            a = dt.dtpts[tr[0]]               # look up row tr[0] -> the actual corner [x, y, z] (no -1: row 0 is the infinite vertex)
            b = dt.dtpts[tr[1]]               # second corner
            c = dt.dtpts[tr[2]]               # third corner
            seg = intersect_triangle(a, b, c, z0)   # [] or [[x1, y1], [x2, y2]], oriented: higher ground on the left

            if seg:                            # an empty list counts as False, a list with points as True
                # -- azimuth: compass direction of the oriented segment (N = 0, E = 90, S = 180, W = 270)
                dx = seg[1][0] - seg[0][0]     # how far the segment goes right: second point's x - first point's x
                dy = seg[1][1] - seg[0][1]     # how far the segment goes up:    second point's y - first point's y
                # atan2(y, x) measures from EAST, anticlockwise (maths convention);
                # swapping the arguments, atan2(dx, dy), measures from NORTH, clockwise (compass convention).
                # degrees() converts from radians; % 360 (modulo) wraps -180..180 onto 0..360 (eg -90 -> 270)
                azimuth = math.degrees(math.atan2(dx, dy)) % 360
                
                # -- lightness: how much this segment faces the light (formula from the assignment page)
                #    light from the north-west: azimuth 225 -> 100 (white), 45 -> 0 (black), 135/315 -> 50
                l = abs(((azimuth - 225) % 360) - 180)    # 0..180: angular distance between this direction and 45 degrees
                lightness = l / 180 * 100                 # rescale to 0..100, as QGIS's color_hsl() expects
                
                # -- pack the segment as one GeoJSON feature
                f = {}                         # one GeoJSON feature = a Python dict
                f["type"] = "Feature"
                f["geometry"] = {"type": "LineString",       # a line through the two points
                                 "coordinates": [[float(seg[0][0]), float(seg[0][1])],   # float(): numpy numbers -> plain Python numbers for json
                                                 [float(seg[1][0]), float(seg[1][1])]]}
                f["properties"] = {"height": z0, "azimuth": azimuth, "lightness": lightness}   # the 3 attributes the assignment asks for
                features.append(f)             # put this feature in the bag
    print(len(features), "contour segments")

    # -- wrap all features in a FeatureCollection (the top level of a GeoJSON file)
    mygeojson: dict[str, Any] = {}
    mygeojson["type"] = "FeatureCollection"
    mygeojson["features"] = features           # the bag filled above

    # -- write the triangulation to a PLY file
    dt.write_ply("mydt.ply")
    print("File 'mydt.ply' created.")
    

    # -- write the contours to a GeoJSON file
    with open("mycontours.geojson", "w") as file:
        file.write(json.dumps(mygeojson, indent=2))
        print("File 'mycontour.geojson' created.")


def intersect_triangle(a, b, c, z0):
    """
    Where does the flat plane at height z0 ("the water level") cut the triangle abc?

    a, b, c: the three corners, each [x, y, z].
    Returns:
      - [] if this triangle has no contour piece at z0
      - [[x1, y1], [x2, y2]]: the two ends of the contour piece, ordered so that
        higher ground is on the LEFT when walking from the first to the second point.
    """
    # -- quick exit: water entirely above or below the triangle
    z_vals = [a[2], b[2], c[2]]                 # the three corner heights
    if z0 > max(z_vals) or z0 < min(z_vals):    # z0 outside their range
        return []                               # -> no contour piece here

    # -- step 1: label each corner relative to the water level
    vertices = [a, b, c]                        # corners in a list, so we can use index 0, 1, 2
    labels = []                                 # will hold one label per corner
    points = []                                 # contour points found so far (corners on z0 + edge crossings)
    for v in vertices:                          # visit each corner
        z = v[2]                                # [2] = height (z) of this corner
        if z > z0:
            labels.append(1)                    # +1 = above the water
        elif z < z0:
            labels.append(-1)                   # -1 = below the water
        else:
            labels.append(0)                    #  0 = exactly on the water line
            points.append(v[0:2])               # this corner IS a contour point: keep [x, y] (slice 0:2 stops before z)

    # -- step 2: walk along each edge, find where the water crosses it
    edges = [(0, 1), (1, 2), (2, 0)]            # the 3 edges as pairs of corner numbers: a-b, b-c, c-a
    for i, j in edges:                          # one round per edge
        p, q = vertices[i], vertices[j]         # name tags: p = start of this edge, q = end
        if labels[i] * labels[j] == -1:         # -1 only if one end is below and the other above
            frac = (z0 - p[2]) / (q[2] - p[2])  # how far along p->q the water sits (0 = at p, 1 = at q)
            x = p[0] + frac * (q[0] - p[0])     # start at p's x, move frac of the way to q's x
            y = p[1] + frac * (q[1] - p[1])     # same for y ([1] = y)
            points.append([x, y])               # save the crossing (2D: z is z0 anyway)

    # -- step 3: only exactly 2 points make a contour piece
    #    (0 = water misses, 1 = only touches a corner, 3 = flat triangle: neighbours provide the lines)
    if len(points) == 2:
        # -- step 4: orientation, so that higher ground is on the LEFT of the segment
        # (4a) find a "witness": any corner above the water (all of them lie on the same, higher side)
        witness = None                          # "none found yet"
        for k in range(3):                      # k = 0, 1, 2 -> the three corners
            if labels[k] == 1:                  # +1 = above the water
                witness = vertices[k]           # remember that corner [x, y, z]
        if witness is None:                     # no corner above: the edge lies on z0 and the third corner is below.
            return []                           # skip; the neighbouring triangle (third corner above) outputs this
                                                # edge correctly oriented, which also avoids a duplicate segment

        # (4b) short names, matching the orient formula
        a = points[0]                           # first end of the segment  [x, y]
        b = points[1]                           # second end of the segment [x, y]
        p = witness                             # the high corner           [x, y, z] (only x and y are used)

        # (4c) orient test (book: Orient predicate, ch. 4) = "blue rectangle minus orange rectangle"
        #      u = b - a (walking direction), v = p - a (towards the witness); orient = u_x * v_y - u_y * v_x
        #      + : witness on the LEFT of a->b    - : witness on the RIGHT    (0 would mean on the line)
        orient = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])

        # (4d) witness on the right -> we walk the wrong way -> turn around
        if orient < 0:
            points = [points[1], points[0]]     # swap the two ends
        return points                           # oriented contour piece

    else:
        return []                               # any other count -> nothing to draw in this triangle


def create_dummy_geojson() -> dict[str, Any]:
    mygeojson: dict[str, Any] = {}
    mygeojson["type"] = "FeatureCollection"
    mygeojson["features"] = []
    f: dict[str, Any] = {}
    f["type"] = "Feature"
    f["geometry"] = {"type": "LineString", "coordinates": [[0, 0], [10, 10]]}
    f["properties"] = {"height": 100, "azimuth": 45, "lightness": 0.75}
    mygeojson["features"].append(f)
    return mygeojson


if __name__ == "__main__":
    main()
