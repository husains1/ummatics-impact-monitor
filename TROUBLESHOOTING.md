# Troubleshooting Guide

Common issues and their solutions for Ummatics Impact Monitor.

## Table of Contents
- [Installation Issues](#installation-issues)
- [Database Issues](#database-issues)
- [API Issues](#api-issues)
- [Frontend Issues](#frontend-issues)
- [Data Collection Issues](#data-collection-issues)
- [Docker Issues](#docker-issues)
- [Performance Issues](#performance-issues)

---

## Installation Issues

### Docker/Docker Compose Not Found

**Problem**: `command not found: docker` or `command not found: docker-compose`

**Solution**:
```bash
# Install Docker
# macOS/Windows: Download from https://www.docker.com/products/docker-desktop
# Linux (Ubuntu):
sudo apt-get update
sudo apt-get install docker.io docker-compose

# Verify installation
docker --version
docker-compose --version
```

### Permission Denied

**Problem**: `permission denied while trying to connect to the Docker daemon socket`

**Solution**:
```bash
# Add your user to docker group
sudo usermod -aG docker $USER

# Log out and back in, then test
docker ps
```

### Port Already in Use

**Problem**: `Bind for 0.0.0.0:3000 failed: port is already allocated`

**Solution**:
```bash
# Find what's using the port
lsof -i :3000
# or
sudo netstat -tulpn | grep :3000

# Kill the process or change port in docker-compose.yml
```

---

## Database Issues

### Database Connection Failed

**Problem**: `psycopg2.OperationalError: could not connect to server`

**Solution**:
```bash
# Check database container status
docker-compose ps db

# If not running, start it
docker-compose up -d db

# Check database logs
docker-compose logs db

# Wait for database to be ready
docker-compose exec db pg_isready -U postgres
```

### Database Not Initializing

**Problem**: Schema not created, tables missing

**Solution**:
```bash
# Stop all containers
docker-compose down -v

# Remove volume
docker volume rm ummatics-impact-monitor_postgres_data

# Start fresh
docker-compose up -d

# Manually run schema if needed
docker-compose exec db psql -U postgres -d ummatics_monitor -f /docker-entrypoint-initdb.d/schema.sql
```

### Database Permission Errors

**Problem**: `permission denied for table` or `role does not exist`

**Solution**:
```bash
# Connect to database
docker-compose exec db psql -U postgres -d ummatics_monitor

# Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;
```

### Database Disk Space Full

**Problem**: `No space left on device`

**Solution**:
```bash
# Check disk usage
df -h

# Clean up Docker
docker system prune -a

# Backup and clean database
make backup
docker-compose exec db vacuumdb -U postgres -d ummatics_monitor --full --analyze
```

---

## API Issues

### API Not Responding

**Problem**: Cannot reach http://localhost:5000

**Solution**:
```bash
# Check API container status
docker-compose ps api

# View API logs
docker-compose logs api

# Restart API
docker-compose restart api

# Check health endpoint
curl http://localhost:5000/api/health
```

### Authentication Failed

**Problem**: `401 Unauthorized` error

**Solution**:
```bash
# Verify your password in .env
cat .env | grep DASHBOARD_PASSWORD

# Test authentication
curl -X POST http://localhost:5000/api/auth \
  -H "Content-Type: application/json" \
  -d '{"password":"your_password"}'

# Clear browser cache and localStorage
# In browser console: localStorage.clear()
```

### Internal Server Error

**Problem**: `500 Internal Server Error`

**Solution**:
```bash
# Check detailed error in logs
docker-compose logs api | tail -50

# Common causes:
# 1. Database connection issue - check DB_PASSWORD in .env
# 2. Missing environment variable - verify .env is complete
# 3. Python dependency issue - rebuild container
docker-compose build --no-cache api
docker-compose up -d api
```

### Slow API Response

**Problem**: API endpoints taking too long

**Solution**:
```bash
# Check database indexes
docker-compose exec db psql -U postgres -d ummatics_monitor
SELECT * FROM pg_indexes WHERE schemaname = 'public';

# Analyze query performance
EXPLAIN ANALYZE SELECT * FROM weekly_snapshots ORDER BY week_start_date DESC LIMIT 12;

# Increase workers in backend/Dockerfile
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "8", "--timeout", "120", "api:app"]
```

---

## Frontend Issues

### White Screen / Blank Page

**Problem**: Frontend loads but shows nothing

**Solution**:
```bash
# Check browser console for errors
# Open DevTools (F12) and look at Console tab

# Check frontend logs
docker-compose logs frontend

# Rebuild frontend
docker-compose build --no-cache frontend
docker-compose up -d frontend

# Clear browser cache
# Hard refresh: Ctrl+Shift+R (Windows/Linux) or Cmd+Shift+R (Mac)
```

### Login Not Working

**Problem**: Password correct but can't login

**Solution**:
```javascript
// Open browser console and clear storage
localStorage.clear()
sessionStorage.clear()

// Check if API is reachable
fetch('/api/health').then(r => r.json()).then(console.log)

// Verify proxy configuration in vite.config.js
```

### Charts Not Rendering

**Problem**: Data loads but charts don't show

**Solution**:
```bash
# Check if data is being returned
curl http://localhost:5000/api/overview \
  -H "Authorization: Bearer your_password"

# Verify Recharts is installed
docker-compose exec frontend npm list recharts

# Reinstall dependencies
docker-compose exec frontend npm install
docker-compose restart frontend
```

### Responsive Design Issues

**Problem**: Layout broken on mobile/different screen sizes

**Solution**:
```bash
# Rebuild with latest Tailwind
cd frontend
npm install -D tailwindcss@latest
npm run build

# Check Tailwind config
cat tailwind.config.js
```

---

## Data Collection Issues

### No Data Appearing

**Problem**: Dashboard shows zeros or no data

**Solution**:
```bash
# Run manual ingestion
docker-compose exec api python ingestion.py

# Check ingestion logs
docker-compose logs api | grep -i "ingestion"

# Verify API credentials in .env
cat .env

# Test individual sources
docker-compose exec api python -c "
from ingestion import ingest_google_alerts
ingest_google_alerts()
"
```

### Google Alerts Not Working

**Problem**: No news mentions being collected

**Solution**:
```bash
# Verify RSS URL is correct
curl "YOUR_GOOGLE_ALERTS_RSS_URL"

# Should return XML feed
# If 404, regenerate the RSS feed at https://www.google.com/alerts

# Check for parsing errors
docker-compose exec api python -c "
import feedparser
feed = feedparser.parse('YOUR_RSS_URL')
print(f'Found {len(feed.entries)} entries')
"
```

### Twitter API Errors

**Problem**: `401 Unauthorized` or rate limit errors

**Solution**:
```bash
# Verify bearer token
# Test with curl
curl "https://api.twitter.com/2/tweets/search/recent?query=Ummatics" \
  -H "Authorization: Bearer YOUR_TWITTER_BEARER_TOKEN"

# If 401: Token is invalid, regenerate at developer.twitter.com
# If 429: Rate limited, wait 15 minutes

# Check rate limit status
curl "https://api.twitter.com/1.1/application/rate_limit_status.json" \
  -H "Authorization: Bearer YOUR_TWITTER_BEARER_TOKEN"
```

### Google Analytics Not Working

**Problem**: No website metrics

**Solution**:
```bash
# Verify credentials file exists
ls -la credentials/google-credentials.json

# Test credentials
docker-compose exec api python -c "
from google.oauth2 import service_account
credentials = service_account.Credentials.from_service_account_file(
    'credentials/google-credentials.json'
)
print('Credentials valid:', credentials.valid)
"

# Verify property ID is correct
# Check in Google Analytics Admin > Property Settings > Property ID

# Ensure service account has Viewer role
# Google Analytics Admin > Property > Property Access Management
```

### OpenAlex API Issues

**Problem**: Citations not updating

**Solution**:
```bash
# Test OpenAlex API
curl "https://api.openalex.org/works?filter=institutions.ror:your_ror_id" \
  -H "User-Agent: mailto:contact@ummatics.org"

# Update ROR ID in ingestion.py if needed
# Find your ROR at https://ror.org/

# Check for rate limiting
# OpenAlex allows 10 requests/second
```

### Scheduler Not Running

**Problem**: Automatic weekly collection not happening

**Solution**:
```bash
# Check scheduler status
docker-compose ps scheduler

# View scheduler logs
docker-compose logs scheduler

# Manually trigger ingestion
docker-compose exec scheduler python ingestion.py

# Verify cron schedule in scheduler.py
# Default: Every Monday at 9 AM
```

---

## Docker Issues

### Container Keeps Restarting

**Problem**: Container in restart loop

**Solution**:
```bash
# Check container logs
docker-compose logs [service_name]

# Common causes:
# 1. Application crash - fix code error
# 2. Missing dependency - rebuild image
# 3. Port conflict - change port
# 4. Resource limits - increase Docker resources

# Remove restart policy temporarily
docker-compose up [service_name]  # Without -d flag
```

### Out of Disk Space

**Problem**: Docker eating up disk space

**Solution**:
```bash
# Check Docker disk usage
docker system df

# Clean up
docker system prune -a
docker volume prune

# Remove old images
docker image prune -a

# Clean build cache
docker builder prune
```

### Network Issues

**Problem**: Containers can't communicate

**Solution**:
```bash
# Check network
docker network ls
docker network inspect ummatics-impact-monitor_ummatics_network

# Recreate network
docker-compose down
docker network prune
docker-compose up -d

# Test connectivity
docker-compose exec frontend ping api
docker-compose exec api ping db
```

---

## Performance Issues

### Slow Database Queries

**Problem**: API responses taking too long

**Solution**:
```sql
-- Connect to database
docker-compose exec db psql -U postgres -d ummatics_monitor

-- Analyze slow queries
SELECT query, mean_exec_time, calls 
FROM pg_stat_statements 
ORDER BY mean_exec_time DESC 
LIMIT 10;

-- Rebuild indexes
REINDEX DATABASE ummatics_monitor;

-- Vacuum database
VACUUM ANALYZE;
```

### High Memory Usage

**Problem**: Docker containers using too much RAM

**Solution**:
```bash
# Check memory usage
docker stats

# Limit memory in docker-compose.yml
services:
  api:
    mem_limit: 512m
    memswap_limit: 512m

# Restart with new limits
docker-compose down
docker-compose up -d
```

### Slow Frontend Loading

**Problem**: Dashboard takes long to load

**Solution**:
```bash
# Build production bundle
cd frontend
npm run build

# Serve production build instead of dev server
# Update frontend Dockerfile:
FROM nginx:alpine
COPY dist /usr/share/nginx/html

# Optimize images and assets
# Use lazy loading for heavy components
```

---

## General Debugging Tips

### Enable Debug Logging

```bash
# Backend - add to .env
FLASK_DEBUG=True

# View detailed logs
docker-compose logs -f --tail=100
```

### Check Container Health

```bash
# All containers
docker-compose ps

# Specific container
docker inspect ummatics_api

# Health check
docker-compose exec api curl http://localhost:5000/api/health
```

### Reset Everything

```bash
# Nuclear option - start fresh
docker-compose down -v
docker system prune -a
rm -rf node_modules
git clean -fdx
./setup.sh
```

---

## Still Having Issues?

1. **Check logs first**: `docker-compose logs -f`
2. **Search GitHub issues**: Existing solutions
3. **Create new issue**: With logs and error messages
4. **Contact support**: contact@ummatics.org

Include in your report:
- OS and Docker version
- Error messages and logs
- Steps to reproduce
- What you've already tried

---

**Remember**: Most issues are solved by:
1. Checking logs
2. Verifying configuration
3. Restarting containers
4. Rebuilding images
