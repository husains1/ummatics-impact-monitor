# Quick Start Guide

Get your Ummatics Impact Monitor up and running in 5 minutes!

## Prerequisites Checklist

Before you start, make sure you have:

- [ ] Docker installed ([Get Docker](https://docs.docker.com/get-docker/))
- [ ] Docker Compose installed
- [ ] Google Alerts RSS feed URL
- [ ] Twitter API Bearer Token
- [ ] Google Analytics 4 Property ID
- [ ] Google service account credentials JSON file

## Step-by-Step Setup

### 1. Get the Code (1 min)

```bash
git clone https://github.com/husains1/ummatics-impact-monitor.git
cd ummatics-impact-monitor
```

### 2. Configure Credentials (2 min)

Create your environment file:
```bash
cp .env.example .env
```

Edit `.env` and add your credentials:
```env
DB_PASSWORD=my_secure_password123
DASHBOARD_PASSWORD=my_dashboard_pass456
GOOGLE_ALERTS_RSS_URL=https://www.google.com/alerts/feeds/YOUR_FEED_ID
TWITTER_BEARER_TOKEN=YOUR_TWITTER_TOKEN
GA4_PROPERTY_ID=123456789
CONTACT_EMAIL=contact@ummatics.org
```

Add Google credentials:
```bash
mkdir credentials
# Copy your google-credentials.json to the credentials folder
cp ~/path/to/your-service-account.json credentials/google-credentials.json
```

### 3. Launch! (2 min)

Run the setup script:
```bash
./setup.sh
```

Or manually:
```bash
docker-compose up -d
```

That's it! 🎉

## Access Your Dashboard

Open your browser:
```
http://localhost:3000
```

Login with your `DASHBOARD_PASSWORD` from the `.env` file.

## First Data Collection

The system automatically collects data every Monday at 9 AM. To run it immediately:

```bash
docker-compose exec api python ingestion.py
```

This will:
1. Fetch news mentions from Google Alerts
2. Collect Twitter mentions and metrics
3. Pull Google Analytics data
4. Update citation counts from OpenAlex
5. Generate weekly snapshots

Wait a few minutes, then refresh your dashboard!

## Quick Commands

| Action | Command |
|--------|---------|
| Start services | `make start` or `docker-compose up -d` |
| Stop services | `make stop` or `docker-compose down` |
| View logs | `make logs` or `docker-compose logs -f` |
| Manual ingestion | `make ingest` |
| Check status | `make status` |
| Backup database | `make backup` |

## Verify Installation

Check if all services are running:
```bash
docker-compose ps
```

You should see 4 services running:
- `ummatics_db` (PostgreSQL)
- `ummatics_api` (Flask API)
- `ummatics_scheduler` (Data collector)
- `ummatics_frontend` (React dashboard)

Test the API:
```bash
curl http://localhost:5000/api/health
```

Should return:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-26T12:00:00"
}
```

## Common First-Time Issues

### "Cannot connect to database"
Wait 30 seconds for the database to initialize, then try again.

### "Invalid password"
Check your `DASHBOARD_PASSWORD` in `.env` matches what you're entering.

### "No data showing"
Run manual ingestion: `docker-compose exec api python ingestion.py`

### "Port already in use"
Stop conflicting services or change ports in `docker-compose.yml`:
```yaml
ports:
  - "3001:3000"  # Change first number
```

## Next Steps

1. **Explore the Dashboard**: Click through all 5 tabs
2. **Customize Settings**: Edit ingestion schedule in `backend/scheduler.py`
3. **Set Up Backups**: Schedule regular database backups
4. **Monitor Logs**: Check for any errors or warnings
5. **Read Full Docs**: See README.md for complete documentation

## Getting Help

- **Documentation**: Check README.md
- **Troubleshooting**: See TROUBLESHOOTING.md
- **Issues**: GitHub Issues
- **Contact**: contact@ummatics.org

Happy monitoring! 📊
