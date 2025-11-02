# Changelog

All notable changes to the Ummatics Impact Monitor will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned Features
- LinkedIn API integration
- YouTube metrics tracking
- Email notifications for significant changes
- Export reports to PDF
- Custom date range selection
- Multi-user support with roles
- API rate limiting

## [1.0.0] - 2024-01-26

### Added
- Initial release of Ummatics Impact Monitor
- Google Alerts integration for news monitoring
- Twitter/X API integration for social media tracking
- Google Analytics 4 integration for website analytics
- OpenAlex API integration for academic citation tracking
- Password-protected React dashboard
- 5 interactive tabs (Overview, Social, Website, Citations, News)
- Flask REST API with authentication
- PostgreSQL database with comprehensive schema
- Automated weekly data ingestion with APScheduler
- Docker containerized deployment
- Recharts visualizations for all metrics
- 12-week trend analysis
- Geographic distribution tracking
- Top pages analytics
- Citation growth tracking
- Responsive design with Tailwind CSS

### Backend Features
- RESTful API with 6 endpoints
- Bearer token authentication
- Database connection pooling
- Error handling and logging
- Health check endpoint
- Automated scheduler service

### Frontend Features
- Modern React 18 application
- Login/authentication flow
- Interactive data visualizations
- Responsive layout
- Real-time data fetching
- Tab-based navigation
- Metric cards with color coding
- Line charts for trends
- Bar charts for comparisons
- Tables for detailed data

### Infrastructure
- Docker Compose orchestration
- Multi-container setup (DB, API, Scheduler, Frontend)
- Volume persistence for database
- Health checks for all services
- Automatic restart policies
- Network isolation

### Documentation
- Comprehensive README with setup instructions
- API endpoint documentation
- Contributing guidelines
- Environment variable templates
- Makefile for common tasks
- Setup script for easy initialization

### Security
- Password-protected dashboard
- Environment-based configuration
- No hardcoded credentials
- .gitignore for sensitive files
- Bearer token authentication for API

## Version History

### Version Numbering
- **Major version**: Breaking changes
- **Minor version**: New features (backward compatible)
- **Patch version**: Bug fixes and small improvements

---

[Unreleased]: https://github.com/husains1/ummatics-impact-monitor/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/husains1/ummatics-impact-monitor/releases/tag/v1.0.0
