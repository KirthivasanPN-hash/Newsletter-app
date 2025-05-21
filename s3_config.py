import boto3
from botocore.exceptions import ClientError
import os
from dotenv import load_dotenv

# procedure
'''
loat environment variables
s3 client setting up

'''


# Load environment variables
load_dotenv()

# S3 Configuration
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
S3_REGION = os.getenv('AWS_REGION')

# Initialize S3 client
s3_client = boto3.client(
    's3',
    region_name=S3_REGION,
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
)

def upload_file_to_s3(file_obj, file_name):
    """
    Upload a file to S3 bucket
    """
    try:
        s3_client.upload_fileobj(
            file_obj,
            S3_BUCKET_NAME,
            file_name,
            ExtraArgs={"ContentType": "image/jpeg"}
        )
        return f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/{file_name}"
    except ClientError as e:
        print(f"Error uploading to S3: {e}")
        return None

def delete_file_from_s3(file_name):
    """
    Delete a file from S3 bucket
    """
    try:
        s3_client.delete_object(
            Bucket=S3_BUCKET_NAME,
            Key=file_name
        )
        return True
    except ClientError as e:
        print(f"Error deleting from S3: {e}")
        return False 