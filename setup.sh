#!/bin/bash

echo "========================================="
echo "Ummatics Impact Monitor - Setup Script"
echo "========================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

echo "✅ Docker and Docker Compose are installed"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env file with your actual credentials before continuing."
    echo ""
    read -p "Press Enter after you've updated the .env file..."
else
    echo "✅ .env file already exists"
fi

# Check if credentials directory exists
if [ ! -d "credentials" ]; then
    mkdir -p credentials
    echo "📁 Created credentials directory"
fi

# Check if Google credentials exist
if [ ! -f "credentials/google-credentials.json" ]; then
    echo "⚠️  Google credentials not found at credentials/google-credentials.json"
    echo "   Please place your Google service account JSON file there."
    echo ""
    read -p "Press Enter after you've added the credentials file..."
else
    echo "✅ Google credentials found"
fi

echo ""
echo "🐳 Starting Docker containers..."
docker-compose up -d

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 10

echo ""
echo "🎉 Setup complete!"
echo ""
echo "📊 Dashboard: http://localhost:3000"
echo "🔌 API: http://localhost:5000"
echo "🗄️  Database: localhost:5432"
echo ""
echo "📝 Next steps:"
echo "  1. Open http://localhost:3000 in your browser"
echo "  2. Login with your dashboard password from .env"
echo "  3. Wait for the first data collection (runs every Monday at 9 AM)"
echo "  4. Or run manual ingestion: docker-compose exec api python ingestion.py"
echo ""
echo "📚 View logs: docker-compose logs -f"
echo "🛑 Stop services: docker-compose down"
echo ""
