from pathlib import Path
from landcover_pipeline.template.yml_config import update_yaml_config
def run_vector_engine(input_raster: Path, output_vector: Path) -> None:
    """
    Execute raster-to-vector conversion.
    """
    # TODO: call real vectorization logic

    modify_yml={"input_file":str(input_raster.absolute()),
                "output_file":str(output_vector.absolute())}

    update_yaml_config(str(r"./landcover_pipeline/template/template_vector.yml"),str(r"./landcover_pipeline/postprocessing/vector_conf.yml"),modify_yml)

    print("input_raster:",input_raster)
    print("output_vector:",output_vector)
    
    import subprocess
    CONFIG_FILE="./landcover_pipeline/postprocessing/vector_conf.yml"
    subprocess.run(["python", "flair-aiml4os-vector_conv/flair-to-cosia-vector.py", "-c", CONFIG_FILE], check=True)
