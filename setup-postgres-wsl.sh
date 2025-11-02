#!/bin/bash
# Quick PostgreSQL Setup for Ubuntu WSL - Ummatics Impact Monitor

echo "========================================="
echo "PostgreSQL Setup for WSL Ubuntu"
echo "========================================="

# Update and install PostgreSQL
echo "📦 Installing PostgreSQL..."
sudo apt update
sudo apt install -y postgresql postgresql-contrib

# Start PostgreSQL service
echo "🚀 Starting PostgreSQL service..."
sudo service postgresql start

# Get password from user
read -sp "Enter password for postgres user: " DB_PASSWORD
echo ""

# Create database and user
echo "🗄️  Creating database..."
sudo -u postgres psql << EOF
CREATE DATABASE ummatics_monitor;
ALTER USER postgres PASSWORD '$DB_PASSWORD';
\q
EOF

# Find schema.sql file
SCHEMA_PATH=""
if [ -f "schema.sql" ]; then
    SCHEMA_PATH="schema.sql"
elif [ -f "../schema.sql" ]; then
    SCHEMA_PATH="../schema.sql"
else
    echo "⚠️  schema.sql not found in current or parent directory"
    echo "   Please run this script from the project directory"
    exit 1
fi

# Initialize schema
echo "📊 Initializing database schema..."
sudo -u postgres psql -d ummatics_monitor -f "$SCHEMA_PATH"

# Update .env if it exists
if [ -f ".env" ]; then
    echo "⚙️  Updating .env configuration..."
    sed -i 's/DB_HOST=.*/DB_HOST=localhost/' .env
    sed -i "s/DB_PASSWORD=.*/DB_PASSWORD=$DB_PASSWORD/" .env
    echo "   ✅ .env updated with new settings"
fi

# Auto-start PostgreSQL on WSL launch (optional)
read -p "Make PostgreSQL start automatically with WSL? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if ! grep -q "service postgresql start" ~/.bashrc; then
        echo "" >> ~/.bashrc
        echo "# Auto-start PostgreSQL" >> ~/.bashrc
        echo "sudo service postgresql start > /dev/null 2>&1" >> ~/.bashrc
        echo "   ✅ Auto-start configured in ~/.bashrc"
    fi
fi

echo ""
echo "========================================="
echo "✅ PostgreSQL Setup Complete!"
echo "========================================="
echo ""
echo "📋 Connection Details:"
echo "   Host: localhost"
echo "   Port: 5432"
echo "   Database: ummatics_monitor"
echo "   User: postgres"
echo "   Password: (the one you just entered)"
echo ""
echo "🔧 Useful Commands:"
echo "   Start:   sudo service postgresql start"
echo "   Stop:    sudo service postgresql stop"
echo "   Status:  sudo service postgresql status"
echo "   Connect: sudo -u postgres psql -d ummatics_monitor"
echo ""
echo "▶️  Next Steps:"
echo "   1. Update your .env file (if not done automatically)"
echo "   2. Install Python dependencies: pip install -r backend/requirements.txt"
echo "   3. Run the backend: python backend/api.py"
echo ""
