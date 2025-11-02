# Deployment Checklist

Use this checklist to ensure your Ummatics Impact Monitor is properly configured and deployed.

## ✅ Pre-Deployment Checklist

### 1. Environment Setup
- [ ] Docker installed and running
- [ ] Docker Compose installed
- [ ] Git installed (for version control)
- [ ] Port 3000 available (frontend)
- [ ] Port 5000 available (backend)
- [ ] Port 5432 available (database)

### 2. Credentials Obtained
- [ ] Google Alerts RSS feed URL created
- [ ] Twitter API Bearer Token obtained
- [ ] Google Analytics 4 Property ID noted
- [ ] Google service account JSON file downloaded
- [ ] Chosen secure database password
- [ ] Chosen secure dashboard password

### 3. File Configuration
- [ ] `.env` file created from `.env.example`
- [ ] All environment variables filled in `.env`
- [ ] Google credentials placed in `credentials/google-credentials.json`
- [ ] Credentials file has correct permissions (readable by Docker)

## 🔧 Configuration Checklist

### Environment Variables (.env)
```bash
# Check these are all set:
- [ ] DB_PASSWORD=<strong_password>
- [ ] DASHBOARD_PASSWORD=<secure_password>
- [ ] GOOGLE_ALERTS_RSS_URL=<valid_rss_url>
- [ ] TWITTER_BEARER_TOKEN=<valid_token>
- [ ] GA4_PROPERTY_ID=<property_id>
- [ ] CONTACT_EMAIL=<your_email>
```

### Google Analytics Setup
- [ ] Service account created in Google Cloud Console
- [ ] Service account granted "Viewer" role in GA4
- [ ] Property ID matches your GA4 property
- [ ] JSON credentials file is valid

### Twitter API Setup
- [ ] Developer account approved
- [ ] App created with appropriate permissions
- [ ] Bearer token generated and valid
- [ ] Rate limits understood (180 requests per 15 min)

### Google Alerts Setup
- [ ] Alert created for your search terms
- [ ] Delivery method set to "RSS feed"
- [ ] RSS URL copied correctly
- [ ] Feed accessible and returning results

### OpenAlex Configuration
- [ ] Contact email set in `.env`
- [ ] Institution ROR ID updated in `backend/ingestion.py` (if applicable)
- [ ] Search filter customized for your works

## 🚀 Deployment Steps

### Step 1: Initial Setup
```bash
- [ ] cd ummatics-impact-monitor
- [ ] cp .env.example .env
- [ ] nano .env  # Fill in all values
- [ ] mkdir -p credentials
- [ ] cp path/to/google-credentials.json credentials/
```

### Step 2: Launch Application
```bash
- [ ] ./setup.sh
      # or
- [ ] docker-compose up -d
```

### Step 3: Verify Services
```bash
- [ ] docker-compose ps  # All services "Up"
- [ ] curl http://localhost:5000/api/health  # Returns healthy status
- [ ] Open http://localhost:3000  # Dashboard loads
```

### Step 4: Test Authentication
```bash
- [ ] Can login with dashboard password
- [ ] Token stored in browser localStorage
- [ ] Can access all dashboard tabs
```

### Step 5: Run Initial Data Collection
```bash
- [ ] docker-compose exec api python ingestion.py
- [ ] Check logs for errors: docker-compose logs
- [ ] Verify data appears in dashboard
```

## 🧪 Testing Checklist

### API Testing
- [ ] Health endpoint responds: `curl http://localhost:5000/api/health`
- [ ] Auth endpoint works: Test with correct/incorrect password
- [ ] Overview endpoint returns data (after ingestion)
- [ ] All 6 endpoints accessible with valid token

### Data Collection Testing
```bash
- [ ] Google Alerts: News mentions collected
- [ ] Twitter: Social mentions recorded
- [ ] Google Analytics: Website metrics captured
- [ ] OpenAlex: Citations tracked
- [ ] Weekly snapshot created
```

### Database Testing
```bash
- [ ] Connect to database: docker-compose exec db psql -U postgres -d ummatics_monitor
- [ ] Check tables exist: \dt
- [ ] Verify data in tables: SELECT COUNT(*) FROM weekly_snapshots;
- [ ] Indexes created: SELECT * FROM pg_indexes WHERE schemaname = 'public';
```

### Frontend Testing
- [ ] Dashboard loads without errors
- [ ] All 5 tabs render correctly
- [ ] Charts display data properly
- [ ] Responsive design works on mobile
- [ ] No console errors in browser DevTools

## 📊 Post-Deployment Validation

### Day 1 Checks
- [ ] All containers running: `docker-compose ps`
- [ ] No error logs: `docker-compose logs`
- [ ] Dashboard accessible remotely (if deployed)
- [ ] Data collection successful
- [ ] Scheduler service running

### Week 1 Checks
- [ ] Automatic weekly ingestion ran on Monday
- [ ] Email notifications working (if configured)
- [ ] Performance acceptable
- [ ] No memory/disk issues
- [ ] Database backups running

### Month 1 Checks
- [ ] Data trends showing correctly
- [ ] No data gaps or missing weeks
- [ ] API rate limits not exceeded
- [ ] Storage usage acceptable
- [ ] User feedback incorporated

## 🔒 Security Checklist

### Configuration Security
- [ ] `.env` file not committed to git
- [ ] `.gitignore` includes sensitive files
- [ ] Strong passwords used (12+ characters)
- [ ] Credentials files have restricted permissions
- [ ] No API keys hardcoded in source

### Deployment Security
- [ ] Dashboard password different from database password
- [ ] HTTPS enabled (production)
- [ ] Firewall rules configured
- [ ] Database not exposed to internet
- [ ] Regular security updates planned

### Access Control
- [ ] Only authorized personnel have credentials
- [ ] Credentials stored securely (password manager)
- [ ] Service account has minimal permissions
- [ ] API tokens can be rotated if compromised

## 🔄 Maintenance Checklist

### Daily Tasks
- [ ] Check service status: `make status`
- [ ] Review error logs if issues occur

### Weekly Tasks
- [ ] Verify data collection completed
- [ ] Check scheduler logs: `docker-compose logs scheduler`
- [ ] Review dashboard for anomalies
- [ ] Backup database: `make backup`

### Monthly Tasks
- [ ] Review system performance
- [ ] Check disk space usage
- [ ] Update dependencies if needed
- [ ] Review and update documentation
- [ ] Test disaster recovery

### Quarterly Tasks
- [ ] Review and rotate credentials
- [ ] Performance optimization review
- [ ] User feedback review
- [ ] Feature enhancement planning

## 📝 Documentation Checklist

- [ ] README.md reviewed and updated
- [ ] QUICKSTART.md tested by new user
- [ ] TROUBLESHOOTING.md covers common issues
- [ ] ARCHITECTURE.md reflects current setup
- [ ] CHANGELOG.md updated with changes
- [ ] API documentation current

## 🚨 Emergency Procedures

### If Dashboard Goes Down
1. [ ] Check container status: `docker-compose ps`
2. [ ] Review logs: `docker-compose logs frontend`
3. [ ] Restart service: `docker-compose restart frontend`
4. [ ] Check browser console for client-side errors

### If API Stops Responding
1. [ ] Check container status: `docker-compose ps api`
2. [ ] Review logs: `docker-compose logs api`
3. [ ] Check database connection
4. [ ] Restart API: `docker-compose restart api`

### If Database Issues
1. [ ] Check disk space: `df -h`
2. [ ] Review database logs: `docker-compose logs db`
3. [ ] Check connections: `docker-compose exec db pg_isready`
4. [ ] Restart if needed: `docker-compose restart db`

### If Data Not Collecting
1. [ ] Run manual ingestion: `make ingest`
2. [ ] Check API credentials are valid
3. [ ] Review ingestion logs for specific errors
4. [ ] Verify external APIs are accessible

## ✨ Success Criteria

Your deployment is successful when:
- [ ] All services running without errors
- [ ] Dashboard accessible and displaying data
- [ ] Automatic data collection working
- [ ] All charts and visualizations rendering
- [ ] Authentication working properly
- [ ] Database backups configured
- [ ] Monitoring in place
- [ ] Documentation complete

## 📞 Support Contacts

- **Technical Issues**: Check TROUBLESHOOTING.md first
- **Feature Requests**: GitHub Issues
- **Security Concerns**: contact@ummatics.org (immediate response)
- **General Questions**: contact@ummatics.org

---

**Last Updated**: October 26, 2025  
**Version**: 1.0.0  
**Status**: Ready for Production ✅

---

## Quick Command Reference

```bash
# Start everything
make start

# Stop everything
make stop

# View all logs
make logs

# Run data collection
make ingest

# Backup database
make backup

# Check health
make health

# Open database shell
make shell-db

# View specific logs
make logs-api
make logs-frontend
make logs-scheduler
```

**Remember**: The first data collection will populate your dashboard. Run `make ingest` immediately after setup to see data!
