# -- geo1015.2026.hw01
# -- Lukas Beuster
# -- 924055

import argparse
import json
import random
import sys
from typing import Any

import rasterio
import startinpy
import polyscope as ps


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
    print(band1)
    t = d.transform # Gets the local transformation.
    print(f'Transform 2 (Origin x?): {t[2]}, Transform 5 (Origin y?): {t[5]} and Transform 0 (cell size x?): {t[0]}, and Transform 4 (pixel size y?): {t[4]}') # What is transform 2? Coordinate?
    pts = [] #Empty pt list to fill
    print(band1.shape[0])
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
    
    features = []                              # empty "bag" that will hold one GeoJSON feature per contour segment
    for z0 in myrange:                         # OUTER loop: each contour height, eg 100, 200, 300 ...
        for tr in dt.triangles:                # INNER loop: each triangle; tr = 3 row numbers into dt.points, eg [17, 4, 230]
            a = dt.points[tr[0]]               # look up row tr[0] -> the actual corner [x, y, z] (no -1: row 0 is the infinite vertex)
            b = dt.points[tr[1]]               # second corner
            c = dt.points[tr[2]]               # third corner
            seg = intersect_triangle(a, b, c, z0)   # [] or [[x1, y1], [x2, y2]] for this triangle at this height
            if seg:                            # an empty list counts as False, a list with points as True
                f = {}                         # one GeoJSON feature = a Python dict
                f["type"] = "Feature"
                f["geometry"] = {"type": "LineString",       # a line through the two points
                                 "coordinates": [[float(seg[0][0]), float(seg[0][1])],   # float(): numpy numbers -> plain Python numbers for json
                                                 [float(seg[1][0]), float(seg[1][1])]]}
                f["properties"] = {"height": z0, "azimuth": 0, "lightness": 0}   # attributes; azimuth/lightness are placeholders for now
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
    Where does the flat plane at height z0 cut the triangle abc?

    Returns:
      - [] if there is no contour piece in this triangle
      - [[x1, y1], [x2, y2]] the two ends of the contour piece (2D, no z needed:
        we already know z = z0). Order does not matter yet.

    Hints, in the order you might need them:
      1. For each corner: is it above, below, or exactly at z0? # Loop through the corners, check against z0
      2. Which edges are crossed? (corners on opposite sides) # If z0 is between corners, then that edge between is crossed
      3. Where on a crossed edge? (how far z0 is between the two corner heights) # proportionally between
      4. Then deal with corners exactly at z0 (see the special-case tests). # No idea how. 
    """
    # -- quick exit: water entirely above or below the triangle
    z_vals = [a[2], b[2], c[2]]                 # the three corner heights
    if z0 > max(z_vals) or z0 < min(z_vals):    # z0 outside their range
        return []                               # -> no contour piece here

    # -- step 1: label each corner relative to the water level
    vertices = [a, b, c]                        # corners in a list, so we can use index 0, 1, 2
    labels = []                                 # will hold one label per corner
    points = []                                 # crossing points found so far
    for v in vertices:                          # visit each corner
        z = v[2]                                # [2] = height (z) of this corner
        if z > z0:
            labels.append(1)                    # +1 = above the water
        elif z < z0:
            labels.append(-1)                   # -1 = below the water
        else:
            labels.append(0)
            points.append(v[0:2])                    #  0 = exactly on the water line
    # print("labels:", labels)

    # -- step 2: walk along each edge, find where the water crosses it
    # points = []                                 # crossing points found so far
    edges = [(0, 1), (1, 2), (2, 0)]            # the 3 edges as pairs of corner numbers: a-b, b-c, c-a
    for i, j in edges:                          # one round per edge
        p, q = vertices[i], vertices[j]         # name tags: p = start of this edge, q = end
        if labels[i] * labels[j] == -1:         # -1 only if one end is below and the other above
            frac = (z0 - p[2]) / (q[2] - p[2])  # how far along p->q the water sits (0 = at p, 1 = at q)
            # print(frac)
            x = p[0] + frac * (q[0] - p[0])     # start at p's x, move frac of the way to q's x
            y = p[1] + frac * (q[1] - p[1])     # same for y ([1] = y)
            points.append([x, y])               # save the crossing (2D: z is z0 anyway)
    
    if len(points) == 2: # 2 points = one contour piece; 0 = nothing
        return points
        
    else:
        return []    

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
