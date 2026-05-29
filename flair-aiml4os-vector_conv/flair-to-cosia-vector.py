import argparse
import sqlite3
from pathlib import Path

import numpy as np
import rasterio
import shapely
import yaml
from geopandas import GeoDataFrame
from rasterio.features import sieve, shapes
from shapely.geometry import shape


# --------------------------- Config & parsing ---------------------------

def parse_color(val):
    """Accept '#rrggbb' or [r,g,b] or 'r,g,b' -> (r,g,b)."""
    if isinstance(val, (list, tuple)) and len(val) == 3:
        return tuple(int(x) for x in val)
    if isinstance(val, str):
        s = val.strip()
        if s.startswith("#") and len(s) == 7:
            return (int(s[1:3], 16), int(s[3:5], 16), int(s[5:7], 16))
        parts = [p.strip() for p in s.split(",")]
        if len(parts) == 3:
            return tuple(int(x) for x in parts)
    raise ValueError(f"Unrecognized color format: {val!r}")


def _coalesce(cfg, *keys, default=None):
    """Return the first present key from cfg, else default."""
    for k in keys:
        if k in cfg and cfg[k] is not None:
            return cfg[k]
    return default


def load_config(cfg_path, cli_input_override=None, cli_output_override=None):
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    if "classes" not in cfg or not cfg["classes"]:
        raise ValueError("Config must include a non-empty 'classes' list (each item is [code, name, color]).")

    # Read new keys, fall back to old names for backward compatibility
    sieve_px = int(_coalesce(cfg, "sieve_pixels", "sieve", default=0))
    simplify_tol = float(_coalesce(cfg, "simplify_tolerance", "simplify", default=0.0))
    debug_flag = bool(_coalesce(cfg, "save_debug_raster", "debug", default=False))
    add_label_field = bool(_coalesce(cfg, "include_class_label", "add_label_field", default=True))
    class_attr = _coalesce(cfg, "out_class_column_name", "class_attr", default="classes")

    input_path = (
        cli_input_override
        or _coalesce(cfg, "input_file", "input")
    )
    if not input_path:
        raise ValueError("No input provided. Set 'input_file' in config or pass --input-file/-i.")
    input_path = Path(input_path)

    if cli_output_override:
        output_path = Path(cli_output_override)
    else:
        output_path = Path(_coalesce(cfg, "output_file", "output", default=None) or input_path.with_suffix(".gpkg"))
    if output_path.suffix.lower() != ".gpkg":
        output_path = output_path.with_suffix(".gpkg")
    output_path = output_path.expanduser()

    # Parse classes (support list of [code, name, color] or list of dicts with keys code/name/color)
    cls_map = {}
    cls_list = cfg["classes"]
    if not isinstance(cls_list, list):
        raise ValueError("'classes' must be a list.")
    for item in cls_list:
        if isinstance(item, (list, tuple)):
            if len(item) != 3:
                raise ValueError("Each list item in 'classes' must be [code, name, color].")
            cid, name, color = item
        elif isinstance(item, dict):
            # more verbose form: {code: 0, name: "building", color: "#ce7079"}
            if not {"code", "name", "color"} <= set(item.keys()):
                raise ValueError("Dict items in 'classes' must have keys: code, name, color.")
            cid, name, color = item["code"], item["name"], item["color"]
        else:
            raise ValueError("Each item in 'classes' must be either a list [code, name, color] or a dict.")

        cid = int(cid)
        if cid in cls_map:
            raise ValueError(f"Duplicate class id in config: {cid}")
        rgb = parse_color(color)
        cls_map[cid] = {"name": str(name), "color": rgb}

    return {
        "input_path": input_path,
        "output_path": output_path,
        "sieve_pixels": sieve_px,
        "simplify_tolerance": simplify_tol,
        "save_debug_raster": debug_flag,
        "include_class_label": add_label_field,
        "classes": cls_map,
        "class_attr": class_attr,  # attribute name in output; default 'classes'
    }


# --------------------------- QML style & GPKG ---------------------------

def build_qml_from_mapping(class_map, attr_name="classes",
                           outline_rgba=(35, 35, 35, 255), outline_width=0.2, outline_unit="MM"):
    """Build a QGIS categorized QML from class_map with a subtle outline."""
    cats, syms = [], []
    for cid in sorted(class_map.keys()):
        info = class_map[cid]
        r, g, b = info["color"]
        label = f"({cid:02d}) {info['name']}"
        cats.append(f'      <category symbol="{cid}" value="{cid}" label="{label}" render="true"/>\n')
        syms.append(f"""    <symbol name="{cid}" type="fill" clip_to_extent="1" alpha="1">
      <layer class="SimpleFill" pass="0" enabled="1" locked="0">
        <prop k="color" v="{r},{g},{b},255"/>
        <prop k="style" v="solid"/>

        <!-- Outline -->
        <prop k="outline_color" v="{outline_rgba[0]},{outline_rgba[1]},{outline_rgba[2]},{outline_rgba[3]}"/>
        <prop k="outline_style" v="solid"/>
        <prop k="outline_width" v="{outline_width}"/>
        <prop k="outline_width_unit" v="{outline_unit}"/>
      </layer>
    </symbol>
""")
    return f"""<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3" styleCategories="Symbology">
  <renderer-v2 type="categorizedSymbol" attr="{attr_name}" symbollevels="0" forceraster="0" enableorderby="0">
    <categories>
{''.join(cats)}    </categories>
    <symbols>
{''.join(syms)}    </symbols>
  </renderer-v2>
  <layerGeometryType>2</layerGeometryType>
</qgis>
"""


def write_default_style_to_gpkg(gpkg_path, layer_name, qml_text, style_name="default"):
    conn = sqlite3.connect(gpkg_path)
    try:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS layer_styles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            f_table_catalog VARCHAR(256),
            f_table_schema VARCHAR(256),
            f_table_name VARCHAR(256),
            f_geometry_column VARCHAR(256),
            styleName VARCHAR(30),
            styleQML TEXT,
            styleSLD TEXT,
            useAsDefault INTEGER,
            description TEXT,
            owner VARCHAR(30),
            ui VARCHAR(30),
            update_time DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cur.execute("SELECT column_name FROM gpkg_geometry_columns WHERE table_name=?", (layer_name,))
        row = cur.fetchone()
        if row and row[0]:
            geom_col = row[0]
        else:
            cur.execute(f"PRAGMA table_info({layer_name})")
            cols = cur.fetchall()
            names = [c[1] for c in cols] if cols else []
            geom_col = 'geom' if 'geom' in names else ('geometry' if 'geometry' in names else (names[0] if names else 'geom'))

        # Unset previous defaults
        cur.execute("""UPDATE layer_styles
                       SET useAsDefault=0
                       WHERE f_table_schema='' AND f_table_name=? AND f_geometry_column=?""",
                    (layer_name, geom_col))

        # Upsert our style
        cur.execute("""SELECT id FROM layer_styles
                       WHERE f_table_schema='' AND f_table_name=? AND f_geometry_column=? AND styleName=?""",
                    (layer_name, geom_col, style_name))
        r = cur.fetchone()
        if r:
            cur.execute("""UPDATE layer_styles
                           SET styleQML=?, useAsDefault=1, update_time=CURRENT_TIMESTAMP
                           WHERE id=?""", (qml_text, r[0]))
        else:
            cur.execute("""INSERT INTO layer_styles
                (f_table_catalog,f_table_schema,f_table_name,f_geometry_column,
                 styleName,styleQML,styleSLD,useAsDefault,description,owner,ui,update_time)
                 VALUES('','',?,?,?,?,1,'','','','',CURRENT_TIMESTAMP)""",
                (layer_name, geom_col, style_name, qml_text))
        conn.commit()
    finally:
        conn.close()


def print_config_summary(cfg):
    print("\n========== CONFIGURATION ==========")
    print(f"{'Input file':22}: {cfg['input_path']}")
    print(f"{'Output file':22}: {cfg['output_path']}")
    print(f"{'Sieve (pixels)':22}: {cfg['sieve_pixels']}")
    print(f"{'Simplify tol.':22}: {cfg['simplify_tolerance']}")
    print(f"{'Save debug raster':22}: {cfg['save_debug_raster']}")
    print(f"{'Add label column':22}: {cfg['include_class_label']}")
    print(f"{'Class column name':22}: {cfg['class_attr']}")
    print(f"{'Number of classes':22}: {len(cfg['classes'])}")
    print("===================================\n")


# --------------------------- Main pipeline ---------------------------

def main():
    args = parse_args()
    cfg = load_config(args.config, cli_input_override=args.input_file, cli_output_override=args.output_file)
    print_config_summary(cfg)

    in_path = cfg["input_path"]
    out_path = cfg["output_path"]
    sieve_px = cfg["sieve_pixels"]
    simplify_tol = cfg["simplify_tolerance"]
    debug_flag = cfg["save_debug_raster"]
    add_label_field = cfg["include_class_label"]
    class_map = cfg["classes"]
    class_attr = cfg["class_attr"]

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(in_path) as src:
        profile = src.profile
        profile.update(dtype=rasterio.uint8, count=1, compress='lzw')

        if src.count > 1:
            array = src.read()
            array = array.argmax(axis=0).astype(np.uint8)
        else:
            array = src.read(1).astype(np.uint8)

        if sieve_px and sieve_px > 0:
            array = sieve(array, size=int(sieve_px))

        if debug_flag:
            image_path = out_path.with_suffix(".tif")
            with rasterio.open(image_path, 'w', **profile) as dst:
                dst.write(array.astype(rasterio.uint8), 1)

        present = set(np.unique(array).tolist())
        defined = set(class_map.keys())
        missing = sorted(present - defined)
        if missing:
            raise ValueError(
                f"The raster contains class id(s) with no definition in config: {missing}. "
                f"Add entries to 'classes' in your YAML."
            )

        shape_gen = ((shape(s), int(v)) for s, v in shapes(array, transform=src.transform))
        data = list(shape_gen)
        geoms = [s for (s, v) in data]
        cls_vals = [v for (s, v) in data]

        if simplify_tol and simplify_tol > 0.0:
            geoms = shapely.coverage_simplify(geoms, simplify_tol)

        data_dict = {"geometry": geoms, class_attr: cls_vals}

        if add_label_field:
            data_dict["label"] = [f"({cid:02d}) {class_map[cid]['name']}" for cid in cls_vals]

        gdf = GeoDataFrame(data_dict, geometry="geometry", crs=src.crs)

        layer_name = out_path.stem.replace(" ", "_")
        gdf.to_file(filename=str(out_path), driver="GPKG", layer=layer_name)

        qml = build_qml_from_mapping(class_map, attr_name=class_attr)
        write_default_style_to_gpkg(str(out_path), layer_name, qml_text=qml, style_name="default")

    print(f"✅ {out_path} file written with style (attribute name: '{class_attr}').\n")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("-c", "--config", required=True, help="YAML configuration file")
    p.add_argument("-i", "--input-file", required=False, help="Override 'input_file' from YAML")
    p.add_argument("-o", "--output-file", required=False, help="Override 'output_file' from YAML")
    return p.parse_args()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
