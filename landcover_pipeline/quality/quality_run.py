from landcover_pipeline.quality.get_tiles import tiles_containing_points
from landcover_pipeline.inference.flair import run_flair_single
from landcover_pipeline.storage.path import (
    imagery_dir,
)

project_id="IT/veneto/2021"

points_file="points.gpkg"

model="small"


listRaster=tiles_containing_points(
    points_file,
    project_id,
) 


#listRaster=['029041w_RGB_lc', '029042w_RGB_lc', '029081w_RGB_lc', '029082w_RGB_lc', '029121w_RGB_lc', '029122w_RGB_lc', '030011w_RGB_lc', '030012w_RGB_lc', '030013w_RGB_lc', '030014w_RGB_lc', '030021w_RGB_lc', '030022w_RGB_lc', '030023w_RGB_lc', '030024w_RGB_lc', '030031w_RGB_lc', '030032w_RGB_lc', '030033w_RGB_lc', '030034w_RGB_lc', '030051w_RGB_lc', '030052w_RGB_lc', '030053w_RGB_lc', '030054w_RGB_lc', '030061w_RGB_lc', '030062w_RGB_lc', '030063w_RGB_lc', '030071w_RGB_lc', '030072w_RGB_lc', '030073w_RGB_lc', '030074w_RGB_lc', '030091w_RGB_lc', '030092w_RGB_lc', '030093w_RGB_lc', '030101w_RGB_lc', '030102w_RGB_lc', '030103w_RGB_lc', '030104w_RGB_lc', '030111w_RGB_lc', '030113w_RGB_lc', '030114w_RGB_lc']
print(listRaster)

 #['029041w_RGB_lc', '029042w_RGB_lc', '029081w_RGB_lc', '029082w_RGB_lc', '029121w_RGB_lc', '029122w_RGB_lc', '030011w_RGB_lc', '030012w_RGB_lc', '030013w_RGB_lc', '030014w_RGB_lc', '030021w_RGB_lc', '030022w_RGB_lc', '030023w_RGB_lc', '030024w_RGB_lc', '030031w_RGB_lc', '030032w_RGB_lc', '030033w_RGB_lc', '030034w_RGB_lc', '030051w_RGB_lc', '030052w_RGB_lc', '030053w_RGB_lc', '030054w_RGB_lc', '030061w_RGB_lc', '030062w_RGB_lc', '030063w_RGB_lc', '030071w_RGB_lc', '030072w_RGB_lc', '030073w_RGB_lc', '030074w_RGB_lc', '030091w_RGB_lc', '030092w_RGB_lc', '030093w_RGB_lc', '030101w_RGB_lc', '030102w_RGB_lc', '030103w_RGB_lc', '030104w_RGB_lc', '030111w_RGB_lc', '030113w_RGB_lc', '030114w_RGB_lc']
# per ogni tile nella listaRaster:
# il comando è quality assestment --project it/veneto/2021 --points points.gpkg
# genero i raster prob
#   lancio inferenza e in output aggiungo suffisso prob
# il progesso di inferenza puo essere lasciato cosi
# lo stato viene scritto nelle stesse cartelle di inferenza
# devo modificare il nome del file di output aggiungendo l'argomento prob
# lancio i comandi di quality 
#   - conversione
#   - probability
#   - meausure  
# 

imagery_prefix = imagery_dir(project_id)

for tile_id in listRaster:
    input_key=imagery_prefix+tile_id+".tif"
    run_flair_single(project_id,input_key,tile_id,model,output_class="prob")
    break
