# This script extracts the sampled coordinates for a specific NUTS2 region from its .gpkg file amd stpres them into a .txt file
# author: JOC

import geopandas as gpd

# Load the GeoPackage file (replace with your actual file path)
gdf = gpd.read_file("/AIML4OS/WP7/analysis/data/random_points_nuts2vaerdi=DK01_fid=17_seed=4.gpkg")

# Open a .txt file to write the output
with open("/AIML4OS/WP7/analysis/data/random_points_nuts2vaerdi=DK01_fid=17_seed=4_coord.txt", "w") as f:
    for geom in gdf.geometry:
        def format_coord(x, y):
            return f"{x}\t{y}\n" #round coordinates to three decimals and fill with 0s
        
        if geom.geom_type == "Point":
            f.write(format_coord(geom.x, geom.y))
        elif geom.geom_type in ["LineString", "Polygon"]:
            for x, y in geom.coords:
                f.write(format_coord(x, y))
        elif geom.geom_type in ["MultiLineString", "MultiPolygon", "GeometryCollection"]:
            for part in geom.geoms:
                if hasattr(part, "coords"):
                    for x, y in part.coords:
                        f.write(format_coord(x, y))

