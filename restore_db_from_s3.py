#!/usr/bin/env python3
"""
PostgreSQL Database Restore from AWS S3

This script downloads a database backup from S3 and restores it
to a PostgreSQL database (optionally a new database).

Uses boto3 for S3 operations.
"""

import os
import sys
import subprocess
import gzip
import tempfile
from datetime import datetime
from pathlib import Path
import boto3
from botocore.exceptions import ClientError

# Configuration
RESTORE_DIR = Path("/tmp/db_restore")
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


def get_latest_backup(s3_client):
    """Get latest backup filename from S3"""
    log("Fetching latest backup from S3...")
    
    try:
        response = s3_client.list_objects_v2(Bucket=S3_BUCKET)
        
        if 'Contents' not in response:
            error(f"No backups found in S3 bucket: {S3_BUCKET}")
            return None
        
        backups = [obj for obj in response['Contents'] if obj['Key'].startswith('ummatics_db_backup_') and obj['Key'].endswith('.sql.gz')]
        
        if not backups:
            error(f"No valid backup files found in S3 bucket: {S3_BUCKET}")
            return None
        
        # Sort by last modified, get latest
        latest = sorted(backups, key=lambda x: x['LastModified'], reverse=True)[0]
        log(f"Latest backup: {latest['Key']} ({latest['Size'] / (1024*1024):.2f} MB)")
        return latest['Key']
        
    except ClientError as e:
        error(f"Failed to list S3 backups: {e}")
        return None


def download_backup(s3_client, backup_filename):
    """Download backup from S3"""
    local_path = RESTORE_DIR / backup_filename
    
    log(f"Creating restore directory: {RESTORE_DIR}...")
    RESTORE_DIR.mkdir(parents=True, exist_ok=True)
    
    log(f"Downloading backup from S3: {backup_filename}...")
    
    try:
        s3_client.download_file(S3_BUCKET, backup_filename, str(local_path))
        
        file_size = local_path.stat().st_size
        file_size_mb = file_size / (1024 * 1024)
        log(f"Backup downloaded successfully: {local_path} ({file_size_mb:.2f} MB)")
        return local_path
        
    except ClientError as e:
        error(f"Failed to download backup from S3: {e}")
        return None


def database_exists(db_name):
    """Check if database exists"""
    try:
        result = subprocess.run(
            ["docker", "exec", DB_CONTAINER, "psql", "-U", DB_USER, "-lqt"],
            capture_output=True,
            text=True,
            check=True
        )
        return db_name in result.stdout
    except subprocess.CalledProcessError as e:
        error(f"Failed to check if database exists: {e}")
        return False


def create_database(db_name, force=False):
    """Create new database"""
    if database_exists(db_name):
        log(f"WARNING: Database '{db_name}' already exists")
        if not force:
            response = input("Do you want to DROP and recreate it? (yes/no): ")
            if response.lower() != 'yes':
                error("Restore cancelled by user")
                return False
        
        log(f"Dropping existing database: {db_name}...")
        try:
            subprocess.run(
                ["docker", "exec", DB_CONTAINER, "psql", "-U", DB_USER, "-c", f"DROP DATABASE {db_name};"],
                check=True,
                capture_output=True
            )
        except subprocess.CalledProcessError as e:
            error(f"Failed to drop database: {e}")
            return False
    
    log(f"Creating database: {db_name}...")
    try:
        subprocess.run(
            ["docker", "exec", DB_CONTAINER, "psql", "-U", DB_USER, "-c", f"CREATE DATABASE {db_name};"],
            check=True,
            capture_output=True
        )
        log("Database created successfully")
        return True
    except subprocess.CalledProcessError as e:
        error(f"Failed to create database: {e}")
        return False


def restore_database(backup_path, db_name):
    """Restore database from backup"""
    log(f"Restoring database '{db_name}' from backup...")
    log(f"Backup file: {backup_path}")
    
    try:
        # Decompress and restore using pipe
        with gzip.open(backup_path, 'rb') as f:
            restore_proc = subprocess.Popen(
                ["docker", "exec", "-i", DB_CONTAINER, "psql", "-U", DB_USER, "-d", db_name],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Feed data to psql
            stdout, stderr = restore_proc.communicate(input=f.read())
            
            if restore_proc.returncode == 0:
                log("Database restored successfully")
                return True
            else:
                error(f"Failed to restore database")
                if stderr:
                    error(f"stderr: {stderr.decode()}")
                return False
                
    except Exception as e:
        error(f"Unexpected error during restore: {e}")
        return False


def verify_restore(db_name):
    """Verify restored database"""
    log("Verifying restored database...")
    
    try:
        # Count tables
        result = subprocess.run(
            ["docker", "exec", DB_CONTAINER, "psql", "-U", DB_USER, "-d", db_name, "-t", "-c",
             "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';"],
            capture_output=True,
            text=True,
            check=True
        )
        table_count = int(result.stdout.strip())
        log(f"Tables found: {table_count}")
        
        # Count rows in key tables
        social_result = subprocess.run(
            ["docker", "exec", DB_CONTAINER, "psql", "-U", DB_USER, "-d", db_name, "-t", "-c",
             "SELECT COUNT(*) FROM social_mentions;"],
            capture_output=True,
            text=True
        )
        social_count = int(social_result.stdout.strip()) if social_result.returncode == 0 else 0
        
        news_result = subprocess.run(
            ["docker", "exec", DB_CONTAINER, "psql", "-U", DB_USER, "-d", db_name, "-t", "-c",
             "SELECT COUNT(*) FROM news_mentions;"],
            capture_output=True,
            text=True
        )
        news_count = int(news_result.stdout.strip()) if news_result.returncode == 0 else 0
        
        log(f"Social mentions: {social_count}")
        log(f"News mentions: {news_count}")
        
        if table_count > 0:
            log("Verification passed")
            return True, {"tables": table_count, "social_mentions": social_count, "news_mentions": news_count}
        else:
            error("Verification failed: No tables found")
            return False, {}
            
    except Exception as e:
        error(f"Verification failed: {e}")
        return False, {}


def cleanup(restore_dir):
    """Cleanup downloaded backup"""
    log("Cleaning up downloaded backup...")
    try:
        if restore_dir.exists():
            import shutil
            shutil.rmtree(restore_dir)
        log("Cleanup complete")
    except Exception as e:
        error(f"Cleanup failed: {e}")


def main():
    """Main execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Restore PostgreSQL database from S3')
    parser.add_argument('--backup', default='latest', help='Backup filename or "latest" (default: latest)')
    parser.add_argument('--database', default='ummatics_monitor_restored', help='Target database name (default: ummatics_monitor_restored)')
    parser.add_argument('--force', action='store_true', help='Force overwrite without confirmation')
    
    args = parser.parse_args()
    
    log("=" * 50)
    log("Starting PostgreSQL restore from S3")
    log("=" * 50)
    
    # Check prerequisites
    if not check_docker_container():
        sys.exit(1)
    
    # Initialize S3 client
    s3_client = boto3.client('s3', region_name=AWS_REGION)
    
    # Determine backup file
    backup_filename = args.backup
    if backup_filename == 'latest':
        backup_filename = get_latest_backup(s3_client)
        if not backup_filename:
            sys.exit(1)
    
    # Download backup
    local_backup = download_backup(s3_client, backup_filename)
    if not local_backup:
        sys.exit(1)
    
    # Create and restore database
    if not create_database(args.database, args.force):
        cleanup(RESTORE_DIR)
        sys.exit(1)
    
    if not restore_database(local_backup, args.database):
        cleanup(RESTORE_DIR)
        sys.exit(1)
    
    success, stats = verify_restore(args.database)
    if not success:
        cleanup(RESTORE_DIR)
        sys.exit(1)
    
    # Cleanup
    cleanup(RESTORE_DIR)
    
    log("=" * 50)
    log("Restore completed successfully!")
    log(f"Database: {args.database}")
    log(f"Source backup: {backup_filename}")
    log(f"Statistics: {stats}")
    log("=" * 50)
    log("")
    log("To connect to restored database:")
    log(f"  docker exec -it {DB_CONTAINER} psql -U {DB_USER} -d {args.database}")


if __name__ == "__main__":
    main()
