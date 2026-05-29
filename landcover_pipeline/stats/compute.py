from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask, geometry_window
from shapely.geometry import box
from shapely.ops import polygonize, unary_union
from tqdm import tqdm


from landcover_pipeline.storage.s3 import (
    download_file,
    get_bucket,
    list_objects,
    upload_file,
)

from landcover_pipeline.storage.path import (
    landcover_stats_path,
    raster_output_dir,
)


# ============================================================
# 1. BUILD RASTER FOOTPRINTS
# ============================================================

def build_tile_footprints(project_id: str) -> gpd.GeoDataFrame:
    """
    Costruisce i footprint leggendo SOLO i metadati
    dei raster su S3 (nessun pixel viene letto).
    """

    bucket = get_bucket()
    prefix = raster_output_dir(project_id)

    keys = [
        k for k in list_objects(bucket, prefix)
        if k.lower().endswith("lc.tif")
    ]

    records = []
    crs = None

    for key in tqdm(keys,
                    total=len(keys),
                    desc="Reading raster metadata",
                    unit="raster"):

        s3_path = f"/vsis3/{bucket}/{key}"

        # Apertura: legge solo header
        with rasterio.open(s3_path) as ds:

            # CRS salvato una sola volta
            if crs is None:
                crs = ds.crs

            # Calcolo bounds da metadati
            left, bottom, right, top = ds.bounds

            records.append({
                "tile": key.split("/")[-1],
                "geometry": box(left, bottom, right, top)
            })

    return gpd.GeoDataFrame(records, crs=crs)



# ============================================================
# 2. BUILD OVERLAP CELLS
# ============================================================

def build_overlap_cells(gdf_fp: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Costruisce una partizione spaziale disgiunta (celle atomiche)
    derivata dall'overlay di tutti i footprint raster.

    Output:
        - una riga per cella disgiunta
        - elenco dei raster che coprono quella cella
        - numero di intersezioni (n)
    
    Strategia:
        1) estrai tutti i bordi dei footprint
        2) unisci il linework
        3) polygonize → ottieni celle non sovrapposte
        4) assegna a ogni cella i raster che la coprono
    """

    # --------------------------------------------------------
    # 0. Validazione input
    # --------------------------------------------------------
    if gdf_fp.empty:
        raise ValueError("Footprint vuoti")

    # Manteniamo solo colonne necessarie
    gdf_fp = gdf_fp[["tile", "geometry"]].copy()

    # buffer(0) forza la validità topologica (ripara self-intersections)
    gdf_fp["geometry"] = gdf_fp.geometry.buffer(0)

    # --------------------------------------------------------
    # 1. Costruzione linework globale
    # --------------------------------------------------------
    # Estraggo solo i confini dei poligoni (boundary)
    # Ottengo MultiLineString di tutti i bordi
    boundaries = unary_union(gdf_fp.geometry.boundary)

    # --------------------------------------------------------
    # 2. Polygonize
    # --------------------------------------------------------
    # polygonize crea poligoni chiusi da quel linework
    # Risultato: suddivisione atomica dello spazio
    # Nessuna cella si sovrappone ad un'altra
    cells = list(polygonize(boundaries))

    # Creo GeoDataFrame base delle celle
    base = gpd.GeoDataFrame({"geometry": cells}, crs=gdf_fp.crs)

    # ID stabile per join e aggregazioni successive
    base["cell_id"] = base.index

    # --------------------------------------------------------
    # 3. Assegnazione raster a ciascuna cella
    # --------------------------------------------------------
    # Uso representative_point invece di intersects:
    # - evita ambiguità topologiche sui bordi
    # - garantisce 1 punto interno per cella
    base["pt"] = base.geometry.representative_point()

    # Spatial join:
    # Per ogni punto, trovo quale footprint lo contiene
    # "within" è più robusto di intersects in questo contesto
    join = gpd.sjoin(
        base.set_geometry("pt"),
        gdf_fp,
        how="left",
        predicate="within"
    )

    # --------------------------------------------------------
    # 4. Aggregazione raster per cella
    # --------------------------------------------------------
    # Ora abbiamo una tabella dove:
    # - ogni riga = (cell_id, tile)
    # - se una cella è coperta da 3 raster, appare 3 volte
    grouped = join.groupby("cell_id")["tile"]

    agg_records = []

    for cell_id, group in tqdm(
        grouped,
        total=len(grouped),
        desc="Aggregating cells",
        unit="cell"
    ):
        # Elimino duplicati e valori null
        # Ordino per avere risultato deterministico
        files = tuple(sorted(pd.unique(group.dropna())))

        agg_records.append((cell_id, files))

    # Costruisco DataFrame aggregato
    agg = pd.DataFrame(agg_records, columns=["cell_id", "files"])

    # --------------------------------------------------------
    # 5. Merge finale
    # --------------------------------------------------------
    out = base.merge(agg, on="cell_id", how="left")

    # Celle non coperte → tuple vuota
    out["files"] = out["files"].apply(
        lambda x: x if isinstance(x, tuple) else tuple()
    )

    # Numero di raster che coprono la cella
    out["n"] = out["files"].apply(len)

    # --------------------------------------------------------
    # 6. Serializzazione per GPKG
    # --------------------------------------------------------
    # GeoPackage non supporta liste/tuple → serializziamo JSON
    out["files_json"] = out["files"].apply(
        lambda t: json.dumps(list(t))
    )

    # Rimuoviamo colonne tecniche temporanee
    return out.drop(columns=["files", "pt"])



import geopandas as gpd
from shapely.ops import unary_union


def mask_overlap_cells_with_aoi(
    overlap_gpkg: str,
    aoi_gpkg: str,
    output_gpkg: str,
    overlap_layer: str = "cells",
    aoi_layer: str | None = None,
    clip: bool = True,
) -> gpd.GeoDataFrame:
    """
    Filtra le overlap cells usando una Area Of Interest (AOI).

    Parametri
    ----------
    overlap_gpkg : path al file overlap_cells.gpkg
    aoi_gpkg     : path al geopackage contenente l'area di interesse
    output_gpkg  : path di output
    overlap_layer: layer delle celle (default: "cells")
    aoi_layer    : layer AOI (None = primo layer)
    clip         : se True taglia le celle sui bordi AOI,
                   se False mantiene geometria originale ma filtra

    Output
    ------
    GeoDataFrame filtrato e salvato su file.
    """

    # --------------------------------------------------------
    # 1. Lettura dati
    # --------------------------------------------------------
    cells = gpd.read_file(overlap_gpkg)
    aoi = gpd.read_file(aoi_gpkg, layer=aoi_layer)

    if cells.empty:
        raise ValueError("Overlap cells vuoto")

    if aoi.empty:
        raise ValueError("AOI vuoto")

    # --------------------------------------------------------
    # 2. CRS check
    # --------------------------------------------------------
    if cells.crs != aoi.crs:
        aoi = aoi.to_crs(cells.crs)

    # --------------------------------------------------------
    # 3. Unione AOI in unica geometria
    # --------------------------------------------------------
    aoi_union = unary_union(aoi.geometry)

    # --------------------------------------------------------
    # 4. Filtro spaziale
    # --------------------------------------------------------
    # Mantengo solo celle che intersecano AOI
    cells = cells[cells.geometry.intersects(aoi_union)].copy()

    # --------------------------------------------------------
    # 5. Clip opzionale
    # --------------------------------------------------------
    if clip:
        cells["geometry"] = cells.geometry.intersection(aoi_union)
        cells = cells[cells.geometry.is_empty == False]

    # --------------------------------------------------------
    # 6. Salvataggio
    # --------------------------------------------------------
    cells.to_file(output_gpkg, layer="cells_masked", driver="GPKG")

    return cells



# ============================================================
# 3. INDEX CELLS BY RASTER
# ============================================================

def index_cells_by_file(cells: gpd.GeoDataFrame) -> Dict[str, List[Tuple[object, int]]]:
    """
    Mappa raster -> [(geometry, n_intersections)]
    """
    index = defaultdict(list)

    for _, row in tqdm(cells.iterrows(),
                       total=len(cells),
                       desc="Indexing cells",
                       unit="cell"):

        files = json.loads(row["files_json"])
        n = len(files)

        if n == 0:
            continue

        for f in tqdm(files,
                      desc="Assigning cell to raster",
                      leave=False,
                      unit="file"):

            index[f].append((row.geometry, n))

    return index


# ============================================================
# 4. PIXEL COUNTING
# ============================================================

def count_pixels_in_geom(raster_path: str,
                         geom,
                         weight: float) -> Dict[int, float]:
    """
    Conta pixel per classe dentro la geometria
    applicando peso.
    """
    with rasterio.open(raster_path) as ds:

        win = geometry_window(ds, [geom])
        arr = ds.read(1, window=win)

        mask = geometry_mask(
            [geom],
            arr.shape,
            ds.window_transform(win),
            invert=True
        )

        data = arr[mask]

        if ds.nodata is not None:
            data = data[data != ds.nodata]

        if data.size == 0:
            return {}

        counts = np.bincount(data.astype(np.int64))
        weighted = counts * weight

        return {i: float(v) for i, v in enumerate(weighted) if v > 0}


def compute_weighted_counts(project_id: str,
                            cells_gpkg: str) -> Dict[int, float]:
    """
    Calcola pixel count globale pesato.
    """
    cells = gpd.read_file(cells_gpkg)
    index = index_cells_by_file(cells)
    #print(index)
    #exit(0)
    bucket = get_bucket()
    prefix = raster_output_dir(project_id)

    global_counts = defaultdict(float)

    for raster_file, geoms in tqdm(index.items(),
                                   total=len(index),
                                   desc="Processing rasters",
                                   unit="raster"):

        s3_key = f"{prefix}/{raster_file}"
        local_path = Path("cache") / raster_file
        local_path.parent.mkdir(exist_ok=True)

        if not local_path.exists():
            download_file(bucket, s3_key, str(local_path))

        for geom, n in geoms:
            #tqdm(geoms,
            #                desc="Processing cells",
            #                leave=False,
            #                unit="cell"):

            counts = count_pixels_in_geom(
                str(local_path),
                geom,
                weight=1.0 / n
            )

            for cls, val in counts.items():

                global_counts[cls] += val

    return dict(global_counts)


def compute_weighted_counts2(
    project_id: str,
    overlap_gpkg: str,
    
    
) -> dict[int, float]:
    """
    Versione ottimizzata della strategia 2.

    - Nessuna cache su disco
    - Parsing JSON una sola volta
    - Nessun filtro O(N_raster × N_cells)
    - Complessità lineare
    """

    # --------------------------------------------------------
    # 1. Lettura celle
    # --------------------------------------------------------
    cells = gpd.read_file(overlap_gpkg)

    if cells.empty:
        raise ValueError("Overlap cells vuoto")

    # --------------------------------------------------------
    # 2. Parsing JSON UNA SOLA VOLTA
    # --------------------------------------------------------
    cells["files_list"] = cells["files_json"].apply(
        lambda x: json.loads(x) if x else []
    )
    cells["n"] = cells["files_list"].apply(len)

    # --------------------------------------------------------
    # 3. Costruzione mappa raster → geometrie
    # --------------------------------------------------------
    raster_map = defaultdict(list)

    for _, row in tqdm(
        cells.iterrows(),
        total=len(cells),
        desc="Building raster index",
        unit="cell"
    ):
        geom = row.geometry
        n = row["n"]

        if n == 0:
            continue

        for fr in row["files_list"]:
            raster_map[fr].append((geom, n))

    bucket = get_bucket()
    prefix = raster_output_dir(project_id)

    global_counts = defaultdict(float)

    # --------------------------------------------------------
    # 4. Loop sui raster
    # --------------------------------------------------------
    for fr, geom_list in tqdm(
        raster_map.items(),
        total=len(raster_map),
        desc="Processing rasters",
        unit="raster"
    ):

        s3_path = f"/vsis3/{bucket}/{prefix}/{fr}"

        with rasterio.open(s3_path) as ds:

            for geom, n_intersections in tqdm(
                geom_list,
                desc=f"Counting in {fr}",
                leave=False,
                unit="geom"
            ):

                win = geometry_window(ds, [geom])
                arr = ds.read(1, window=win)

                mask = geometry_mask(
                    [geom],
                    out_shape=arr.shape,
                    transform=ds.window_transform(win),
                    invert=True,
                    all_touched=False,  # centroid rule fissata
                )

                data = arr[mask]

                if ds.nodata is not None:
                    data = data[data != ds.nodata]

                if data.size == 0:
                    continue

                counts = np.bincount(data.astype(np.int64))

                weight = 1.0 / n_intersections
                weighted = counts * weight

                for cls, val in enumerate(weighted):
                    if val > 0:
                        global_counts[cls] += float(val)

    return dict(global_counts)


# ============================================================
# MAIN
# Unit test
# ============================================================

if __name__ == "__main__":

    project = "IT/veneto/2021"
    resolution=0.2
    classes=["building","greenhouse","swimming_pool","impervious surface",
            "pervious surface","bare soil","water","snow","herbaceous vegetation",
            "agricultural land","plowed land","vineyard","deciduous","coniferous","brushwood"]

    #footprints = build_tile_footprints(project)
    #footprints.to_file("tile_footprints.gpkg", driver="GPKG")
    footprints=gpd.read_file("tile_footprints.gpkg")
    cells = build_overlap_cells(footprints)
    cells.to_file("overlap_cells.gpkg", driver="GPKG")

    aoi_gpkg=overlap_gpkg="overlap_cells.gpkg"
    aoi_gpkg="mirano2021.gpkg"
    #aoi_gpkg="veneto2021.gpkg"
    output_gpkg="overlap_cells_aoi.gpkg"
    mask_overlap_cells_with_aoi( overlap_gpkg,aoi_gpkg,output_gpkg)   

    counts = compute_weighted_counts2(project, "overlap_cells_aoi.gpkg")

    outTableLandcover=[]
    for k in tqdm(sorted(counts), desc="Printing results", unit="class"):
        outTableLandcover.append((k, counts[k]))
    tableLC=pd.DataFrame(outTableLandcover,columns=["class","pixel"])
    
    tableLC["Area LC"]=tableLC.pixel * resolution**2
    tableLC["LC%"]=tableLC.pixel/tableLC.pixel.sum()
    tableLC.index=classes
    tableLC.to_csv("outTableLandcover.csv",sep=";")
    
    aio_name="".join(aoi_gpkg.split(".gpkg")[:-1])
    s3_key = landcover_stats_path(project,aio_name)

    print("⬆ Uploading land cover statistics to S3...")
    upload_file(
        local_path="outTableLandcover.csv",
        bucket=get_bucket(),
        s3_path=s3_key,
    )

    print(f"✔ Statistics uploaded to: {s3_key}")

