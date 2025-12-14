# Ummatics Impact Monitor

**Real-time social media and web analytics dashboard for tracking Ummatics' online presence and engagement.**

## 🎯 Overview

The Ummatics Impact Monitor is a comprehensive analytics platform that aggregates and visualizes data from multiple sources to track the organization's digital footprint, including Twitter mentions, Reddit discussions, website traffic, academic citations, and news coverage.

**Live Dashboard**: http://3.226.110.16:3000

## ✨ Key Features

### 📱 Social Media Monitoring
- **Twitter Integration**: Real-time mention tracking with sentiment analysis
- **Reddit Discovery**: RSS feeds + Google Custom Search for comprehensive coverage
- **Retweet Filtering**: Shows only original posts (retweet counts preserved on originals)
- **Sentiment Analysis**: AWS Lambda-based analysis (Comprehend + transformers)
- **Engagement Metrics**: Likes, retweets, replies, and engagement rates

### 📊 Multi-Source Analytics
- **Website Analytics**: Traffic trends and top pages
- **Academic Citations**: OpenAlex integration for scholarly impact
- **News Monitoring**: Google Alerts for media mentions
- **Weekly Trends**: 12-week historical data with trend analysis

### 🔄 Automated Operations
- **Scheduled Ingestion**: Hourly data collection (APScheduler)
- **Weekly Backups**: Automated S3 backups with lifecycle management
- **Cost Optimization**: S3 tiered storage (Standard → IA → Deep Archive)
- **Sentiment Processing**: Serverless Lambda functions (pay-per-use)

## 🚀 Quick Start

### Local Development
```bash
# Clone repository
git clone https://github.com/husains1/ummatics-impact-monitor.git
cd ummatics-impact-monitor

# Set up environment
cp .env.example .env
# Edit .env with your API credentials

# Start services
docker-compose up -d

# Run ingestion
docker-compose exec api python ingestion.py

# Access dashboard
open http://localhost:3000
```

### Production Deployment (AWS)
See [AWS_DEPLOYMENT_GUIDE.md](AWS_DEPLOYMENT_GUIDE.md) for complete instructions.

**Current Production**: http://3.226.110.16:3000

## 🏗️ Architecture

### Technology Stack
- **Frontend**: React 18 + Vite + Tailwind CSS + Recharts
- **Backend**: Python 3.11 + Flask + Gunicorn
- **Database**: PostgreSQL 15
- **Scheduler**: APScheduler (hourly ingestion)
- **Deployment**: Docker Compose + AWS ECR
- **Sentiment Analysis**: AWS Lambda (Comprehend + transformers)
- **Backups**: AWS S3 with lifecycle policies

### System Components
```
┌─────────────────────┐
│   React Frontend    │  Port 3000 (nginx)
│   (Dashboard UI)    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│    Flask API        │  Port 5000 (gunicorn)
│   (REST endpoints)  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   PostgreSQL DB     │  Port 5432
│  (ummatics_monitor) │
└─────────────────────┘

External Services:
- Twitter API v2 (mentions)
- Reddit RSS (posts)
- Google Custom Search (Reddit discovery)
- AWS Lambda (sentiment analysis)
- OpenAlex API (citations)
- Google Alerts RSS (news)
```

## 📖 Documentation

### Getting Started
- **[AWS_DEPLOYMENT_GUIDE.md](AWS_DEPLOYMENT_GUIDE.md)** - Complete AWS deployment
- **[AWS_QUICK_START.md](AWS_QUICK_START.md)** - Quick reference guide
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Detailed system architecture

### Feature Documentation
- **[GOOGLE_CSE_SETUP.md](GOOGLE_CSE_SETUP.md)** - Google Custom Search setup
- **[LAMBDA_DEPLOYMENT_SUMMARY.md](LAMBDA_DEPLOYMENT_SUMMARY.md)** - Lambda sentiment setup
- **[SERVERLESS_SENTIMENT_ARCHITECTURE.md](SERVERLESS_SENTIMENT_ARCHITECTURE.md)** - Sentiment architecture

### Reference
- **[LESSONS_LEARNED.md](LESSONS_LEARNED.md)** - Comprehensive troubleshooting guide
  - Deployment architecture
  - Database backup/restore
  - Twitter retweet handling
  - Reddit discovery methods
  - Common issues and solutions

## 🔧 Key Operations

### Database Backups
```bash
# Manual backup to S3
python3 backup_db_to_s3.py

# Restore from S3
python3 restore_db_from_s3.py --force

# Automated: Weekly backups every Sunday at 2 AM UTC
# S3 lifecycle: 30d → Standard-IA, 60d → Deep Archive, 365d → Delete
```

### Data Ingestion
```bash
# Manual ingestion (all sources)
docker exec ummatics_api python ingestion.py

# Automated: Runs hourly via APScheduler
```

### Sentiment Analysis
```bash
# Regenerate sentiment for all records
python3 backend/regenerate_historical_metrics.py

# Lambda function handles new mentions automatically
```

## 🔐 Environment Variables

Required in `.env` file:
```bash
# Database
DB_HOST=db
DB_PORT=5432
DB_NAME=ummatics_monitor
DB_USER=ummatics_user
DB_PASSWORD=your_secure_password

# Twitter API
TWITTER_BEARER_TOKEN=your_bearer_token

# Optional: Google Custom Search (for Reddit comment discovery)
GOOGLE_API_KEY=your_api_key
GOOGLE_CSE_ID=your_cse_id

# Optional: Apify (Twitter scraping fallback)
APIFY_API_TOKEN=your_token

# Optional: Google Alerts
GOOGLE_ALERTS_RSS_URL=your_feed_url

# AWS (for Lambda sentiment + S3 backups)
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_DEFAULT_REGION=us-east-1
```

## 📊 Dashboard Tabs

1. **Overview** - Weekly summary with trend indicators
2. **Social** - Twitter/Reddit mentions, sentiment, engagement
3. **Website** - Traffic metrics and top pages
4. **Citations** - Academic references from OpenAlex
5. **News** - Media coverage from Google Alerts

## 🛠️ Development

### Project Structure
```
ummatics-impact-monitor/
├── backend/
│   ├── api.py              # Flask REST API
│   ├── ingestion.py        # Data collection
│   ├── scheduler.py        # APScheduler config
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx         # Main React app
│   │   └── index.css
│   └── package.json
├── lambda/                 # AWS Lambda functions
│   ├── sentiment_function.py
│   └── template.yaml
├── backup_db_to_s3.py      # S3 backup script
├── restore_db_from_s3.py   # S3 restore script
├── docker-compose.yml
└── schema.sql
```

### Adding New Data Sources
1. Add ingestion function to `backend/ingestion.py`
2. Create database table in `schema.sql`
3. Add API endpoint in `backend/api.py`
4. Update frontend UI in `frontend/src/App.jsx`
5. Add to scheduler in `backend/scheduler.py`

## 📈 Current Stats (Dec 2025)

- **Twitter Mentions**: 3,936 original tweets analyzed
- **Reddit Posts**: 4 relevant posts discovered
- **Database Size**: ~0.49 MB (compressed)
- **Sentiment Coverage**: 100% (4,015 records analyzed)
- **Backups**: Automated weekly to S3
- **Uptime**: EC2 t2.micro (free tier)

## 🆘 Troubleshooting

### Common Issues

**Dashboard not loading?**
```bash
# Check if containers are running
docker ps

# Restart services
docker-compose restart
```

**No data showing?**
```bash
# Run manual ingestion
docker exec ummatics_api python ingestion.py

# Check logs
docker-compose logs api
```

**Sentiment values missing?**
```bash
# Regenerate sentiment analysis
python3 backend/regenerate_historical_metrics.py
```

**AWS CLI broken on EC2?**
- Use boto3 (Python SDK) instead
- See LESSONS_LEARNED.md for details

For detailed troubleshooting, see [LESSONS_LEARNED.md](LESSONS_LEARNED.md).

## 📝 License

This project is proprietary software for Ummatics organization.

## 🤝 Contributing

This is a private project. For questions or issues, contact the development team.

---

**Last Updated**: December 14, 2025  
**Version**: 2.0  
**Deployment**: AWS EC2 (3.226.110.16)  
**Status**: ✅ Production
