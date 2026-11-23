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
    myrange: range = range(tmp[0], tmp[1], tmp[2])
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
            if (z != d.nodatavals) and (random.randint(0, 100) == 5): #Why random?
                pts.append([x, y, z]) # Adds to the list of centre coordinates, including the z coordinate.

    # -- create the TIN
    # -- full docs: https://startinpy.readthedocs.io
    dt = startinpy.DT()
    dt.insert(pts, insertionstrategy="BBox")

    # -- visit the triangles
    trs = dt.triangles
    # Polyscope uses 0-based indexing, and startinpy returns 1-based indices for triangles.
    # We need to adjust the indices to be 0-based. # What impact does this have downstream?
    trs = trs - 1 # NOTE: remove before getting out. Solved with pts[0] = pts[1] before triangulation in the 3D vis example.
    
    one_triangle = trs[0]
    first_vertex = one_triangle[0]
    print("z-coordinate of first vertex: ", dt.points[first_vertex][2])
    
    # -- Add visualisation
    ps.init()
    ps.set_program_name("mydt")
    ps.set_up_dir("z_up")
    ps.set_ground_plane_mode("shadow_only")
    ps.set_ground_plane_height_factor(0.01, is_relative=True)
    ps.set_autocenter_structures(True)
    ps.set_autoscale_structures(True)
    pc = ps.register_point_cloud(
        "mypoints", pts[1:], radius=0.0015, point_render_mode="sphere"
    )
    ps_mesh = ps.register_surface_mesh("mysurface", pts, trs)
    ps_mesh.reset_transform()
    pc.reset_transform()
    ps.show()

    # -- create a dummy GeoJSON file
    mygeojson: dict[str, Any] = create_dummy_geojson()

    # -- write the triangulation to a PLY file
    dt.write_ply("mydt.ply")
    print("File 'mydt.ply' created.")
    

    # -- write the contours to a GeoJSON file
    with open("mycontours.geojson", "w") as file:
        file.write(json.dumps(mygeojson, indent=2))
        print("File 'mycontour.geojson' created.")


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
