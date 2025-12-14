#!/usr/bin/env python3
"""
PostgreSQL Database Backup to AWS S3

This script creates a compressed backup of the PostgreSQL database
and uploads it to AWS S3 with versioning enabled.

Uses boto3 to avoid AWS CLI version issues on EC2.
"""

import os
import sys
import subprocess
import gzip
from datetime import datetime
from pathlib import Path
import boto3
from botocore.exceptions import ClientError

# Configuration
BACKUP_DIR = Path("/tmp/db_backups")
DB_NAME = os.environ.get("DB_NAME", "ummatics_monitor")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_CONTAINER = os.environ.get("DB_CONTAINER", "ummatics_db")
S3_BUCKET = os.environ.get("S3_BUCKET", "ummatics-db-backups")
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")


def log(message):
    """Print timestamped log message"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")


def error(message):
    """Print timestamped error message"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ERROR: {message}", file=sys.stderr)


def check_docker_container():
    """Check if database container is running"""
    log("Checking database container...")
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={DB_CONTAINER}", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            check=True
        )
        if DB_CONTAINER not in result.stdout:
            error(f"Database container '{DB_CONTAINER}' is not running")
            return False
        log(f"Database container '{DB_CONTAINER}' is running")
        return True
    except subprocess.CalledProcessError as e:
        error(f"Failed to check Docker container: {e}")
        return False


def check_s3_access():
    """Verify S3 access"""
    log("Checking S3 access...")
    try:
        s3_client = boto3.client('s3', region_name=AWS_REGION)
        # Try to access our specific bucket instead of listing all buckets
        try:
            s3_client.head_bucket(Bucket=S3_BUCKET)
            log("S3 bucket access verified")
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                log("S3 bucket doesn't exist yet (will be created)")
            elif e.response['Error']['Code'] == '403':
                log("S3 bucket exists but we don't have permissions yet")
            else:
                raise
        return True
    except Exception as e:
        error(f"S3 access check failed: {e}")
        return False


def create_s3_bucket(s3_client):
    """Create S3 bucket if it doesn't exist"""
    log(f"Checking S3 bucket: {S3_BUCKET}...")
    
    try:
        s3_client.head_bucket(Bucket=S3_BUCKET)
        log("S3 bucket already exists")
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            log(f"Creating S3 bucket: {S3_BUCKET}...")
            try:
                if AWS_REGION == 'us-east-1':
                    s3_client.create_bucket(Bucket=S3_BUCKET)
                else:
                    s3_client.create_bucket(
                        Bucket=S3_BUCKET,
                        CreateBucketConfiguration={'LocationConstraint': AWS_REGION}
                    )
                
                # Enable versioning
                log("Enabling versioning on bucket...")
                s3_client.put_bucket_versioning(
                    Bucket=S3_BUCKET,
                    VersioningConfiguration={'Status': 'Enabled'}
                )
                
                # Set lifecycle policy
                log("Setting lifecycle policy (tiered storage + 1 year retention)...")
                s3_client.put_bucket_lifecycle_configuration(
                    Bucket=S3_BUCKET,
                    LifecycleConfiguration={
                        'Rules': [{
                            'ID': 'StorageTieringAndCleanup',
                            'Filter': {'Prefix': ''},
                            'Status': 'Enabled',
                            'Transitions': [
                                {
                                    'Days': 30,
                                    'StorageClass': 'STANDARD_IA'  # Infrequent Access after 1 month
                                },
                                {
                                    'Days': 60,
                                    'StorageClass': 'DEEP_ARCHIVE'  # Deep Archive after 2 months
                                }
                            ],
                            'Expiration': {
                                'Days': 365  # Delete after 1 year
                            },
                            'NoncurrentVersionExpiration': {'NoncurrentDays': 90}
                        }]
                    }
                )
                
                log("S3 bucket created and configured successfully")
                return True
            except ClientError as create_error:
                error(f"Failed to create S3 bucket: {create_error}")
                return False
        else:
            error(f"Failed to check S3 bucket: {e}")
            return False


def create_backup():
    """Create PostgreSQL backup"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"ummatics_db_backup_{timestamp}.sql.gz"
    backup_path = BACKUP_DIR / backup_filename
    
    log(f"Creating backup directory: {BACKUP_DIR}...")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    log(f"Creating database backup: {backup_filename}...")
    log(f"Database: {DB_NAME}, Container: {DB_CONTAINER}")
    
    try:
        # Run pg_dump in container
        pg_dump_cmd = [
            "docker", "exec", DB_CONTAINER,
            "pg_dump", "-U", DB_USER, DB_NAME
        ]
        
        result = subprocess.run(
            pg_dump_cmd,
            capture_output=True,
            check=True
        )
        
        # Compress the output
        with gzip.open(backup_path, 'wb') as f:
            f.write(result.stdout)
        
        # Get file size
        file_size = backup_path.stat().st_size
        file_size_mb = file_size / (1024 * 1024)
        
        log(f"Backup created successfully: {backup_path} ({file_size_mb:.2f} MB)")
        return backup_path, backup_filename
        
    except subprocess.CalledProcessError as e:
        error(f"Failed to create database backup: {e}")
        error(f"stderr: {e.stderr.decode() if e.stderr else 'N/A'}")
        return None, None
    except Exception as e:
        error(f"Unexpected error during backup: {e}")
        return None, None


def upload_to_s3(s3_client, backup_path, backup_filename):
    """Upload backup to S3"""
    log(f"Uploading backup to S3: s3://{S3_BUCKET}/{backup_filename}...")
    
    try:
        s3_client.upload_file(
            str(backup_path),
            S3_BUCKET,
            backup_filename,
            ExtraArgs={
                'Metadata': {
                    'database': DB_NAME,
                    'timestamp': datetime.now().isoformat()
                }
            }
        )
        log("Backup uploaded successfully")
        return True
    except ClientError as e:
        error(f"Failed to upload backup to S3: {e}")
        return False


def cleanup_old_backups():
    """Cleanup old local backups (keep last 3)"""
    log("Cleaning up old local backups...")
    
    backups = sorted(BACKUP_DIR.glob("ummatics_db_backup_*.sql.gz"))
    
    if len(backups) > 3:
        log(f"Found {len(backups)} local backups, keeping only the 3 most recent...")
        for old_backup in backups[:-3]:
            old_backup.unlink()
            log(f"Deleted: {old_backup.name}")
        log("Old local backups cleaned up")
    else:
        log(f"Only {len(backups)} local backups found, no cleanup needed")


def list_s3_backups(s3_client):
    """List recent backups in S3"""
    log("Recent backups in S3:")
    try:
        response = s3_client.list_objects_v2(Bucket=S3_BUCKET)
        if 'Contents' in response:
            for obj in sorted(response['Contents'], key=lambda x: x['LastModified'], reverse=True)[:10]:
                size_mb = obj['Size'] / (1024 * 1024)
                log(f"  {obj['Key']} - {size_mb:.2f} MB - {obj['LastModified']}")
        else:
            log("  No backups found in S3")
    except ClientError as e:
        error(f"Failed to list S3 backups: {e}")


def main():
    """Main execution"""
    log("=" * 50)
    log("Starting PostgreSQL backup to S3")
    log("=" * 50)
    
    # Check prerequisites
    if not check_docker_container():
        sys.exit(1)
    
    if not check_s3_access():
        sys.exit(1)
    
    # Initialize S3 client
    s3_client = boto3.client('s3', region_name=AWS_REGION)
    
    # Create S3 bucket
    if not create_s3_bucket(s3_client):
        sys.exit(1)
    
    # Create backup
    backup_path, backup_filename = create_backup()
    if not backup_path:
        sys.exit(1)
    
    # Upload to S3
    if not upload_to_s3(s3_client, backup_path, backup_filename):
        sys.exit(1)
    
    # Cleanup
    cleanup_old_backups()
    list_s3_backups(s3_client)
    
    log("=" * 50)
    log("Backup completed successfully!")
    log(f"Backup file: {backup_filename}")
    log(f"S3 location: s3://{S3_BUCKET}/{backup_filename}")
    log("=" * 50)


if __name__ == "__main__":
    main()
