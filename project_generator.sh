#!/bin/bash

# Ummatics Impact Monitor - Complete Project Generator
# This script creates all project files in the current directory

set -e

echo "🚀 Generating Ummatics Impact Monitor Project"
echo "=============================================="
echo ""

# Create directory structure
echo "📁 Creating directory structure..."
mkdir -p backend frontend credentials logs .github/workflows

# Create .gitignore
echo "📝 Creating .gitignore..."
cat > .gitignore << 'EOF'
# Environment variables
.env
.env.local
.env.production

# Credentials
credentials/*.json
credentials/*.pem

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
*.egg-info/
.pytest_cache/

# Node
node_modules/
dist/
build/
*.log
.parcel-cache/

# Database
*.sql.gz
*.dump
postgres_data/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Logs
logs/*.log
!logs/.gitkeep

# Docker
.docker/
EOF

# Create .env.example
echo "📝 Creating .env.example..."
cat > .env.example << 'EOF'
# Database Configuration
DB_HOST=localhost
DB_NAME=ummatics_monitor
DB_USER=ummatics_user
DB_PASSWORD=your_secure_password_here

# Dashboard Authentication
DASHBOARD_PASSWORD=your_dashboard_password

# Google Alerts (News Monitoring)
GOOGLE_ALERTS_RSS_URL=https://google.com/alerts/feeds/YOUR_FEED_ID_HERE

# Twitter/X API
TWITTER_BEARER_TOKEN=your_twitter_bearer_token_here

# Google Analytics 4
# GA4_PROPERTY_ID=your_property_id
# GOOGLE_APPLICATION_CREDENTIALS=./credentials/ga4-credentials.json

# OpenAlex (Academic Citations)
CONTACT_EMAIL=your-email@example.com

# Optional: Run ingestion on startup (for testing)
RUN_ON_STARTUP=false

# Optional: LinkedIn API
# LINKEDIN_ACCESS_TOKEN=your_linkedin_token

# Optional: YouTube API
# YOUTUBE_API_KEY=your_youtube_api_key
EOF

# Copy to .env
cp .env.example .env

# Create README.md
echo "📝 Creating README.md..."
cat > README.md << 'EOF'
# Ummatics Impact Monitor 📊

A comprehensive monitoring dashboard that tracks Ummatics' visibility and influence across news, social media, website traffic, and academic citations.

## Features ✨

- 📰 **News Monitoring**: Track mentions via Google Alerts
- 📱 **Social Media Analytics**: Monitor Twitter, LinkedIn, YouTube
- 🌐 **Website Analytics**: Google Analytics 4 integration
- 📚 **Academic Citations**: OpenAlex API tracking
- 📈 **Trend Visualization**: Interactive charts
- 🔄 **Automated Updates**: Weekly data ingestion
- 🔐 **Secure Access**: Password-protected dashboard

## Quick Start 🚀

### Prerequisites
- Docker & Docker Compose
- API credentials (see Configuration section)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/ummatics-impact-monitor.git
   cd ummatics-impact-monitor
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   nano .env
   ```

3. **Add Google Analytics credentials**
   ```bash
   cp /path/to/ga4-credentials.json credentials/
   ```

4. **Start with Docker**
   ```bash
   chmod +x setup.sh
   ./setup.sh
   # Or manually:
   docker-compose up -d
   ```

5. **Access the dashboard**
   - Dashboard: http://localhost:3000
   - API: http://localhost:5000

## Configuration ⚙️

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed setup instructions.

## Project Structure 📁

```
ummatics-impact-monitor/
├── backend/
│   ├── api.py              # Flask API server
│   ├── ingestion.py        # Data collection
│   ├── scheduler.py        # Automation
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   └── App.jsx        # React dashboard
│   ├── package.json
│   └── vite.config.js
├── credentials/           # API credentials (not in git)
├── schema.sql            # Database schema
├── docker-compose.yml    # Docker orchestration
├── setup.sh             # Quick setup script
└── README.md
```

## Documentation 📚

- [Deployment Guide](DEPLOYMENT.md)
- [API Documentation](docs/API.md)
- [Contributing Guidelines](CONTRIBUTING.md)

## License 📄

MIT License - see [LICENSE](LICENSE) file

## Support 💬

For issues or questions, please open an issue on GitHub.

---

**Built with ❤️ for Ummatics**
EOF

# Create LICENSE (MIT)
echo "📝 Creating LICENSE..."
cat > LICENSE << 'EOF'
MIT License

Copyright (c) 2024 Ummatics

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
EOF

# Create placeholder files in logs and credentials
touch logs/.gitkeep
touch credentials/.gitkeep

# Create a credentials README
cat > credentials/README.md << 'EOF'
# Credentials Directory

Place your API credentials in this directory:

- `ga4-credentials.json` - Google Analytics 4 service account credentials

**Important**: Never commit actual credentials to version control!
EOF

# Create GitHub Actions workflow
echo "📝 Creating GitHub Actions workflow..."
cat > .github/workflows/ci.yml << 'EOF'
name: CI/CD Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
      - name: Run linting
        run: |
          cd backend
          pip install flake8
          flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Node
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      - name: Install dependencies
        run: |
          cd frontend
          npm install
      - name: Build
        run: |
          cd frontend
          npm run build
EOF

# Create CONTRIBUTING.md
cat > CONTRIBUTING.md << 'EOF'
# Contributing to Ummatics Impact Monitor

We welcome contributions! Here's how you can help:

## Getting Started

1. Fork the repository
2. Clone your fork
3. Create a feature branch
4. Make your changes
5. Test thoroughly
6. Submit a pull request

## Development Setup

```bash
# Backend
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend
npm install
```

## Code Style

- Python: Follow PEP 8
- JavaScript: Use ESLint configuration
- Add comments for complex logic
- Write meaningful commit messages

## Pull Request Process

1. Update README.md if needed
2. Update documentation
3. Ensure all tests pass
4. Request review from maintainers

Thank you for contributing!
EOF

echo ""
echo "✅ Project structure created successfully!"
echo ""
echo "📋 Next steps:"
echo "1. cd into the project directory"
echo "2. Review and edit .env file with your credentials"
echo "3. Copy the code from the artifacts into their respective files:"
echo "   - backend/api.py"
echo "   - backend/ingestion.py"
echo "   - backend/scheduler.py"
echo "   - backend/requirements.txt"
echo "   - schema.sql"
echo "   - docker-compose.yml"
echo "   - frontend/src/App.jsx"
echo "   - frontend/package.json"
echo "4. Initialize git: git init"
echo "5. Add files: git add ."
echo "6. Commit: git commit -m 'Initial commit'"
echo "7. Push to GitHub!"
echo ""
echo "🎉 Happy coding!"

chmod +x project_generator.sh
echo "✅ Project generator created successfully!"
echo ""
echo "Run this script to generate the complete project structure:"
echo "./project_generator.sh"
