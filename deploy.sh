#!/bin/bash
# Quick Deploy Script for ingestion.py v2.1
# Run this script to automatically deploy the updated ingestion.py

set -e  # Exit on error

echo "================================================"
echo "  Ummatics Impact Monitor - ingestion.py v2.1"
echo "  Deployment Script"
echo "================================================"
echo ""

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Error: docker-compose.yml not found!"
    echo "   Please run this script from the ummatics-impact-monitor directory"
    exit 1
fi

# Step 1: Backup
echo "📦 Step 1/4: Backing up current ingestion.py..."
if [ -f "backend/ingestion.py" ]; then
    cp backend/ingestion.py backend/ingestion.py.backup.$(date +%Y%m%d_%H%M%S)
    echo "✅ Backup created: backend/ingestion.py.backup.$(date +%Y%m%d_%H%M%S)"
else
    echo "⚠️  No existing ingestion.py found (this might be a fresh install)"
fi

# Step 2: Copy new version
echo ""
echo "📝 Step 2/4: Deploying new ingestion.py..."
# You'll need to adjust this path to where you downloaded the file
NEW_INGESTION_PATH="../ingestion.py"  # Adjust this path!

if [ -f "$NEW_INGESTION_PATH" ]; then
    cp "$NEW_INGESTION_PATH" backend/ingestion.py
    echo "✅ New ingestion.py deployed"
else
    echo "❌ Error: New ingestion.py not found at $NEW_INGESTION_PATH"
    echo "   Please update the NEW_INGESTION_PATH variable in this script"
    exit 1
fi

# Step 3: Verify .env has required variables
echo ""
echo "🔍 Step 3/4: Checking environment variables..."
if grep -q "TWITTER_USERNAME" .env 2>/dev/null; then
    echo "✅ TWITTER_USERNAME found in .env"
else
    echo "⚠️  Adding TWITTER_USERNAME to .env"
    echo "TWITTER_USERNAME=ummatics" >> .env
    echo "✅ TWITTER_USERNAME added"
fi

# Step 4: Restart services
echo ""
echo "🔄 Step 4/4: Restarting services..."
docker-compose restart api scheduler

echo ""
echo "⏳ Waiting for services to restart..."
sleep 10

# Check if services are running
if docker-compose ps | grep -q "api.*Up" && docker-compose ps | grep -q "scheduler.*Up"; then
    echo "✅ Services restarted successfully"
else
    echo "⚠️  Services may not have restarted properly"
    echo "   Check status: docker-compose ps"
fi

echo ""
echo "================================================"
echo "  ✅ Deployment Complete!"
echo "================================================"
echo ""
echo "🧪 Next Steps:"
echo ""
echo "1. Test the update:"
echo "   docker-compose exec api python ingestion.py"
echo ""
echo "2. Check the logs for new output:"
echo "   Look for: 'Trying search strategy 1/4...'"
echo ""
echo "3. Verify in database:"
echo "   docker-compose exec db psql -U postgres -d ummatics_monitor -c \\"
echo "     \"SELECT platform, follower_count, mentions_count FROM social_media_metrics WHERE platform='Twitter' ORDER BY week_start_date DESC LIMIT 1;\""
echo ""
echo "4. Check dashboard:"
echo "   http://localhost:3000"
echo ""
echo "📚 Documentation:"
echo "   - Complete guide: COMPLETE_UPDATE_SUMMARY.md"
echo "   - Troubleshooting: TWITTER_ZERO_MENTIONS_GUIDE.md"
echo "   - Changelog: INGESTION_V2_CHANGELOG.md"
echo ""
echo "🔙 Rollback (if needed):"
echo "   cp backend/ingestion.py.backup.* backend/ingestion.py"
echo "   docker-compose restart api scheduler"
echo ""
