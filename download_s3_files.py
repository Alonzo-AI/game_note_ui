import os
import boto3
from pathlib import Path
from dotenv import load_dotenv

def download_s3_folder(bucket_name, s3_folder, local_dir):
    """
    Download all files with certain extensions from an S3 folder to a local directory.
    """
    # Load credentials from .env
    load_dotenv()
    
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_REGION")
    
    if not all([aws_access_key, aws_secret_key, aws_region]):
        print("Error: AWS credentials not found in .env file.")
        return

    # Initialize S3 client
    s3 = boto3.client(
        "s3",
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name=aws_region
    )

    # Ensure local directory exists
    local_path = Path(local_dir)
    local_path.mkdir(parents=True, exist_ok=True)

    print(f"Listing objects in s3://{bucket_name}/{s3_folder} ...")
    
    try:
        paginator = s3.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bucket_name, Prefix=s3_folder)

        download_count = 0
        for page in pages:
            if "Contents" in page:
                for obj in page["Contents"]:
                    key = obj["Key"]
                    # Skip folders (keys ending in /)
                    if key.endswith("/"):
                        continue
                    
                    # Filter for .json and .md files
                    if key.lower().endswith((".json", ".md")):
                        # Determine local file path (flattened as requested or keeping filename)
                        filename = Path(key).name
                        target_file = local_path / filename
                        
                        print(f"Downloading {key} to {target_file} ...")
                        s3.download_file(bucket_name, key, str(target_file))
                        download_count += 1
            else:
                print("No contents found with the given prefix.")

        print(f"\nDownload complete. Total files downloaded: {download_count}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    # Settings
    BUCKET_NAME = "content-data-storage"
    S3_PREFIX = "mfb/Buffalo/game_notes/2025/processed/Buffalo_2025/"
    LOCAL_DATA_DIR = "output/MFB/Buffalo/2025"

    download_s3_folder(BUCKET_NAME, S3_PREFIX, LOCAL_DATA_DIR)
