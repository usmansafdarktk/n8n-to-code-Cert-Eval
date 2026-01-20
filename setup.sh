#!/bin/bash
set -e

echo "🚀 NebrasAI Certificate Validation Agent - Setup Script"
echo "========================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -eq 0 ]; then
   echo -e "${RED}❌ Please do not run as root${NC}"
   exit 1
fi

echo "📋 Step 1: Checking prerequisites..."
echo "-----------------------------------"

# Check Docker
if command -v docker &> /dev/null; then
    echo -e "${GREEN}✅ Docker is installed:${NC} $(docker --version)"
else
    echo -e "${YELLOW}⚠️  Docker not found. Installing...${NC}"
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    echo -e "${YELLOW}⚠️  Docker installed. Please logout and login again, then re-run this script${NC}"
    exit 0
fi

# Check Docker Compose
if docker compose version &> /dev/null; then
    echo -e "${GREEN}✅ Docker Compose is installed:${NC} $(docker compose version)"
else
    echo -e "${RED}❌ Docker Compose not found. Please install Docker Compose plugin${NC}"
    exit 1
fi

# Check Python
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    echo -e "${GREEN}✅ Python is installed:${NC} Python $PYTHON_VERSION"
else
    echo -e "${RED}❌ Python 3 not found. Please install Python 3.11+${NC}"
    exit 1
fi

# Check Poetry
if command -v poetry &> /dev/null; then
    echo -e "${GREEN}✅ Poetry is installed:${NC} $(poetry --version)"
else
    echo -e "${YELLOW}⚠️  Poetry not found. Installing...${NC}"
    curl -sSL https://install.python-poetry.org | python3 -
    export PATH="$HOME/.local/bin:$PATH"
fi

echo ""
echo "🐳 Step 2: Starting PostgreSQL and Redis..."
echo "-------------------------------------------"

# Stop any existing containers
docker compose down 2>/dev/null || true

# Start PostgreSQL and Redis
docker compose up -d postgres redis

# Wait for services to be healthy
echo "⏳ Waiting for services to be ready..."
sleep 5

# Check PostgreSQL
echo -n "Checking PostgreSQL... "
if docker compose exec -T postgres pg_isready -U certuser &> /dev/null; then
    echo -e "${GREEN}✅ Running${NC}"
else
    echo -e "${RED}❌ Failed to start${NC}"
    docker compose logs postgres
    exit 1
fi

# Check Redis
echo -n "Checking Redis... "
if docker compose exec -T redis redis-cli ping | grep -q PONG; then
    echo -e "${GREEN}✅ Running${NC}"
else
    echo -e "${RED}❌ Failed to start${NC}"
    docker compose logs redis
    exit 1
fi

echo ""
echo "🐍 Step 3: Installing Python dependencies..."
echo "--------------------------------------------"

# Install dependencies
poetry install

echo ""
echo "📦 Step 4: Setting up database..."
echo "---------------------------------"

# Create PGVector extension
docker compose exec -T postgres psql -U certuser -d cert_validation -c "CREATE EXTENSION IF NOT EXISTS vector;" &> /dev/null || true

# Create logs directory
mkdir -p logs

echo ""
echo "🔐 Step 5: Checking configuration..."
echo "------------------------------------"

# Check .env file
if [ ! -f .env ]; then
    echo -e "${RED}❌ .env file not found!${NC}"
    echo "Please copy .env.example to .env and configure it"
    exit 1
fi

# Check GCP key
if [ ! -f gcp-key.json ]; then
    echo -e "${YELLOW}⚠️  gcp-key.json not found${NC}"
    echo "Please download your GCP service account key and save it as gcp-key.json"
    echo "See SETUP_GUIDE.md for instructions"
else
    echo -e "${GREEN}✅ GCP service account key found${NC}"
    chmod 600 gcp-key.json
fi

# Check .env values
if grep -q "your-super-secret-key-change-in-production" .env; then
    echo -e "${YELLOW}⚠️  JWT_SECRET_KEY needs to be changed in .env${NC}"
    echo "Generating a secure key..."
    JWT_SECRET=$(openssl rand -hex 32)
    sed -i "s/JWT_SECRET_KEY=.*/JWT_SECRET_KEY=$JWT_SECRET/" .env
    echo -e "${GREEN}✅ JWT secret key updated${NC}"
fi

# Update database URL to use port 5433
if grep -q "localhost:5432" .env; then
    sed -i 's/localhost:5432/localhost:5433/g' .env
    echo -e "${GREEN}✅ Database URL updated to use port 5433${NC}"
fi

echo ""
echo "✅ Step 6: Testing connections..."
echo "---------------------------------"

# Test database connection
echo -n "Testing PostgreSQL connection... "
if docker compose exec -T postgres psql -U certuser -d cert_validation -c "SELECT 1;" &> /dev/null; then
    echo -e "${GREEN}✅ Success${NC}"
else
    echo -e "${RED}❌ Failed${NC}"
    exit 1
fi

# Test Redis connection
echo -n "Testing Redis connection... "
if docker compose exec -T redis redis-cli ping | grep -q PONG; then
    echo -e "${GREEN}✅ Success${NC}"
else
    echo -e "${RED}❌ Failed${NC}"
    exit 1
fi

# Test GCP credentials (if key exists)
if [ -f gcp-key.json ]; then
    echo -n "Testing GCP credentials... "
    if poetry run python -c "from google.cloud import storage; from google.oauth2 import service_account; credentials = service_account.Credentials.from_service_account_file('./gcp-key.json'); print('OK')" 2>/dev/null | grep -q OK; then
        echo -e "${GREEN}✅ Success${NC}"
    else
        echo -e "${YELLOW}⚠️  GCP credentials test failed (might be OK if not configured yet)${NC}"
    fi
fi

echo ""
echo "========================================================"
echo -e "${GREEN}✅ Setup completed successfully!${NC}"
echo "========================================================"
echo ""
echo "📚 Next steps:"
echo ""
echo "1. Configure GCP credentials (if not done):"
echo "   - Download service account key from GCP Console"
echo "   - Save as: gcp-key.json"
echo "   - See SETUP_GUIDE.md for detailed instructions"
echo ""
echo "2. Review and update .env file:"
echo "   nano .env"
echo ""
echo "3. Start the application:"
echo "   poetry run uvicorn app.main:app --reload"
echo ""
echo "4. Access the API documentation:"
echo "   http://localhost:8000/docs"
echo ""
echo "5. Read the implementation guide:"
echo "   cat IMPLEMENTATION_GUIDE.md"
echo ""
echo "🎉 Happy coding!"
echo ""
