# Ummatics Impact Monitor

A comprehensive monitoring dashboard that tracks Ummatics' visibility and influence across news mentions, social media, website analytics, and academic citations.

![Dashboard Preview](https://via.placeholder.com/800x400?text=Ummatics+Impact+Monitor)

## 🌟 Features

- **📰 News Tracking**: Monitor media mentions via Google Alerts RSS feeds
- **📱 Social Media Analytics**: Track Twitter/X mentions, engagement, and follower growth
- **🌐 Website Analytics**: Google Analytics 4 integration for traffic insights
- **📚 Academic Citations**: OpenAlex API integration for citation tracking
- **📊 Interactive Visualizations**: Beautiful charts with Recharts
- **🔒 Password Protection**: Secure dashboard access
- **⏰ Automated Collection**: Weekly scheduled data ingestion
- **🐳 Docker Containerized**: Easy deployment with Docker Compose

## 📋 Prerequisites

- Docker and Docker Compose
- Google Alerts RSS feed URL
- Twitter API Bearer Token
- Google Analytics 4 Property ID and service account credentials
- PostgreSQL (handled by Docker)

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/husains1/ummatics-impact-monitor.git
cd ummatics-impact-monitor
```

### 2. Configure Environment Variables

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` with your actual credentials:

```env
DB_PASSWORD=your_secure_db_password
DASHBOARD_PASSWORD=your_dashboard_password
GOOGLE_ALERTS_RSS_URL=https://www.google.com/alerts/feeds/your_feed_id
TWITTER_BEARER_TOKEN=your_twitter_bearer_token
GA4_PROPERTY_ID=your_ga4_property_id
CONTACT_EMAIL=contact@ummatics.org
```

### 3. Add Google Analytics Credentials

Place your Google service account JSON credentials file:

```bash
mkdir -p credentials
cp path/to/your-service-account.json credentials/google-credentials.json
```

### 4. Start the Application

```bash
docker-compose up -d
```

This will:
- Initialize the PostgreSQL database
- Start the Flask API backend
- Start the scheduler for automated data collection
- Start the React frontend

### 5. Access the Dashboard

Open your browser and navigate to:
```
http://localhost:3000
```

Login with the password you set in `.env` file.

## 📁 Project Structure

```
ummatics-impact-monitor/
├── backend/
│   ├── api.py              # Flask REST API
│   ├── ingestion.py        # Data collection scripts
│   ├── scheduler.py        # Automated weekly tasks
│   ├── requirements.txt    # Python dependencies
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx        # Main React dashboard
│   │   ├── main.jsx       # React entry point
│   │   └── index.css      # Global styles
│   ├── package.json
│   ├── vite.config.js
│   └── Dockerfile
├── schema.sql              # Database schema
├── docker-compose.yml      # Container orchestration
├── .env.example            # Environment template
├── .gitignore
└── README.md
```

## 🔧 Configuration

### Google Alerts Setup

1. Go to [Google Alerts](https://www.google.com/alerts)
2. Create an alert for "Ummatics" or your search terms
3. Choose "RSS feed" as delivery method
4. Copy the RSS feed URL to your `.env` file

### Twitter API Setup

1. Create a developer account at [Twitter Developer Portal](https://developer.twitter.com/)
2. Create a new app
3. Generate a Bearer Token
4. Add token to your `.env` file

### Google Analytics 4 Setup

1. Go to Google Analytics Admin
2. Create a service account with Analytics Viewer role
3. Download the JSON credentials file
4. Place it in `credentials/google-credentials.json`
5. Add your GA4 Property ID to `.env`

### OpenAlex Setup

OpenAlex requires no API key, but you should:
1. Set your contact email in `.env`
2. Customize the search filter in `ingestion.py` to match your institution/authors

## 🔌 API Endpoints

All endpoints require Bearer token authentication.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check (no auth required) |
| `/api/auth` | POST | Authenticate and get token |
| `/api/overview` | GET | Weekly summary and trends |
| `/api/social` | GET | Social media metrics and mentions |
| `/api/website` | GET | Website analytics data |
| `/api/citations` | GET | Academic citation data |
| `/api/news` | GET | News mentions from Google Alerts |

### Example API Call

```bash
# Login
curl -X POST http://localhost:5000/api/auth \
  -H "Content-Type: application/json" \
  -d '{"password":"your_password"}'

# Get overview data
curl http://localhost:5000/api/overview \
  -H "Authorization: Bearer your_password"
```

## 📊 Dashboard Tabs

### 1. Overview
- Current week metrics across all categories
- 12-week trend visualization
- Quick summary cards

### 2. Social
- Platform-specific metrics (Twitter, LinkedIn, etc.)
- Engagement rates over time
- Recent mentions with engagement data

### 3. Website
- Traffic trends (sessions, users, pageviews)
- Top performing pages
- Geographic distribution of visitors

### 4. Citations
- Citation growth over time
- Most cited works
- Recent citation updates

### 5. News
- Weekly news mention counts
- Recent news articles
- Source and publication dates

## ⏰ Automated Scheduling

The scheduler runs weekly data collection every Monday at 9:00 AM. You can customize this in `backend/scheduler.py`:

```python
scheduler.add_job(
    scheduled_ingestion,
    trigger=CronTrigger(day_of_week='mon', hour=9, minute=0),
)
```

## 🛠️ Development

### Run Backend Locally

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python api.py
```

### Run Frontend Locally

```bash
cd frontend
npm install
npm run dev
```

### Manual Data Ingestion

```bash
docker-compose exec api python ingestion.py
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f scheduler
```

## 🗄️ Database Management

### Access PostgreSQL

```bash
docker-compose exec db psql -U postgres -d ummatics_monitor
```

### Backup Database

```bash
docker-compose exec db pg_dump -U postgres ummatics_monitor > backup.sql
```

### Restore Database

```bash
docker-compose exec -T db psql -U postgres ummatics_monitor < backup.sql
```

## 🚢 Deployment

### Production Considerations

1. **Change default passwords** in `.env`
2. **Use HTTPS** with a reverse proxy (nginx/Caddy)
3. **Set up backups** for PostgreSQL
4. **Configure firewall** rules
5. **Monitor logs** for errors
6. **Set resource limits** in docker-compose.yml

### Example Nginx Configuration

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    location /api {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 🧪 Testing

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm run test
```

## 🐛 Troubleshooting

### Database Connection Issues

```bash
# Check database health
docker-compose ps db

# Restart database
docker-compose restart db
```

### API Not Responding

```bash
# Check API logs
docker-compose logs api

# Restart API
docker-compose restart api
```

### Frontend Build Errors

```bash
# Clear node_modules and rebuild
cd frontend
rm -rf node_modules
npm install
```

## 📝 License

This project is proprietary and confidential.

## 👥 Contributors

- Husain Saqib - Initial Development

## 📧 Support

For issues and questions, please contact: contact@ummatics.org

## 🔮 Future Enhancements

- [ ] LinkedIn API integration
- [ ] YouTube metrics tracking
- [ ] Email notifications for significant changes
- [ ] Export reports to PDF
- [ ] Custom date range selection
- [ ] Multi-user support with roles
- [ ] API rate limiting
- [ ] Advanced filtering and search

## 📚 Resources

- [Flask Documentation](https://flask.palletsprojects.com/)
- [React Documentation](https://react.dev/)
- [Recharts Documentation](https://recharts.org/)
- [Google Analytics Data API](https://developers.google.com/analytics/devguides/reporting/data/v1)
- [Twitter API Documentation](https://developer.twitter.com/en/docs)
- [OpenAlex API Documentation](https://docs.openalex.org/)

---

**Built with ❤️ for Ummatics**
