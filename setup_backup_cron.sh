#!/bin/bash
#
# Setup Weekly Database Backup Cron Job
#
# This script installs a cron job to run database backups every Sunday at 2 AM UTC
#
# Usage: sudo ./setup_backup_cron.sh

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_SCRIPT="${SCRIPT_DIR}/backup_db_to_s3.sh"
LOG_DIR="/var/log/ummatics_backups"
CRON_SCHEDULE="0 2 * * 0"  # Every Sunday at 2 AM UTC

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2
}

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    error "This script must be run as root or with sudo"
    exit 1
fi

# Check if backup script exists
if [ ! -f "${BACKUP_SCRIPT}" ]; then
    error "Backup script not found: ${BACKUP_SCRIPT}"
    exit 1
fi

# Make backup script executable
log "Making backup script executable..."
chmod +x "${BACKUP_SCRIPT}"

# Create log directory
log "Creating log directory: ${LOG_DIR}..."
mkdir -p "${LOG_DIR}"
chown ubuntu:ubuntu "${LOG_DIR}"

# Load environment variables for cron
ENV_FILE="${SCRIPT_DIR}/.env"
if [ ! -f "${ENV_FILE}" ]; then
    error "Environment file not found: ${ENV_FILE}"
    exit 1
fi

# Create cron wrapper script
CRON_WRAPPER="${SCRIPT_DIR}/backup_cron_wrapper.sh"
log "Creating cron wrapper script: ${CRON_WRAPPER}..."

cat > "${CRON_WRAPPER}" <<'EOF'
#!/bin/bash
# Cron wrapper for database backup
# Loads environment variables and runs backup

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/var/log/ummatics_backups/backup_$(date +%Y%m%d_%H%M%S).log"

# Load environment variables
if [ -f "${SCRIPT_DIR}/.env" ]; then
    set -a
    source "${SCRIPT_DIR}/.env"
    set +a
fi

# Run backup and log output
{
    echo "=========================================="
    echo "Automated backup started at $(date)"
    echo "=========================================="
    
    "${SCRIPT_DIR}/backup_db_to_s3.sh"
    
    echo "=========================================="
    echo "Automated backup completed at $(date)"
    echo "=========================================="
} >> "${LOG_FILE}" 2>&1

# Keep only last 30 days of logs
find /var/log/ummatics_backups -name "backup_*.log" -mtime +30 -delete
EOF

chmod +x "${CRON_WRAPPER}"

# Add cron job for ubuntu user
log "Installing cron job for user 'ubuntu'..."

# Create temporary crontab
TEMP_CRON=$(mktemp)
crontab -u ubuntu -l 2>/dev/null > "${TEMP_CRON}" || true

# Remove existing backup cron jobs
grep -v "backup_cron_wrapper.sh" "${TEMP_CRON}" > "${TEMP_CRON}.tmp" || true
mv "${TEMP_CRON}.tmp" "${TEMP_CRON}"

# Add new cron job
echo "${CRON_SCHEDULE} ${CRON_WRAPPER} # Weekly database backup" >> "${TEMP_CRON}"

# Install crontab
crontab -u ubuntu "${TEMP_CRON}"
rm "${TEMP_CRON}"

log "=========================================="
log "Cron job installed successfully!"
log "=========================================="
log "Schedule: Every Sunday at 2 AM UTC"
log "Script: ${CRON_WRAPPER}"
log "Logs: ${LOG_DIR}/backup_*.log"
log ""
log "To view current crontab:"
log "  crontab -u ubuntu -l"
log ""
log "To view backup logs:"
log "  ls -lh ${LOG_DIR}/"
log "  tail -f ${LOG_DIR}/backup_*.log"
log ""
log "To run backup manually:"
log "  ${BACKUP_SCRIPT}"
log "=========================================="
