# cli/run_inference.py

import argparse,os
from landcover_pipeline.inference.runner import run_inference

from landcover_pipeline.storage.s3 import clear_running

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--model", required=True)
    
    args = parser.parse_args()

    bucket=None
    bucket = bucket or os.environ.get("S3_BUCKET")
    if not bucket:
        raise EnvironmentError("S3_BUCKET environment variable not set")
    
    clear_running(args.project,bucket,"inference")
    run_inference(args.project,bucket,args.model)

if __name__ == "__main__":
    main()

