#!/bin/bash
#
# LMS / MANTLE - Production Deployment Setup Script (v1.0.0)
#
# This script automates the full setup of the Lore Management System
# on a clean Ubuntu 22.04 LTS server. It is designed to be idempotent,
# meaning it can be run multiple times without causing issues.
#
# Maintainer: Shawn King
#
#==============================================================================
# SCRIPT CONFIGURATION
#==============================================================================

set -e  # Exit immediately if a command exits with a non-zero status.
set -o pipefail # Return the exit status of the last command in the pipe that failed.
set -u # Treat unset variables as an error when substituting.

#==============================================================================
# GLOBAL VARIABLES
#==============================================================================

# Directory structure
LMS_BASE_DIR="/opt/lms"
LMS_APP_DIR="$LMS_BASE_DIR/lore-management-system"
NEO4J_DATA_DIR="$LMS_BASE_DIR/neo4j_data"
FRONTEND_DIR="$LMS_BASE_DIR/frontend"

#==============================================================================
# HELPER FUNCTIONS
#==============================================================================

log_step() {
    echo ""
    echo "----------------------------------------------------"
    echo "$1"
    echo "----------------------------------------------------"
}

#==============================================================================
# MAIN LOGIC
#==============================================================================

install_dependencies() {
    log_step "1. Installing System Dependencies"
    
    # Update package list
    sudo apt-get update
    
    # Install dependencies
    sudo apt-get install -y \
        docker.io \
        nginx \
        python3-venv \
        certbot \
        python3-certbot-nginx
        
    echo "System dependencies installed."
}

setup_directories() {
    log_step "2. Setting Up Directory Structure"
    
    # Create base directories if they don't exist
    sudo mkdir -p $LMS_BASE_DIR
    sudo mkdir -p $LMS_APP_DIR
    sudo mkdir -p $NEO4J_DATA_DIR
    sudo mkdir -p $FRONTEND_DIR
    
    echo "Directory structure verified/created."
}

configure_neo4j() {
    log_step "3. Configuring and Running Neo4j"
    
    # Prompt for Neo4j password if not already set
    if [ -z "${NEO4J_PASSWORD-}" ]; then
        echo "Please enter a password for the Neo4j database:"
        read -s NEO4J_PASSWORD
        export NEO4J_PASSWORD
    fi

    # Pull the Docker image
    sudo docker pull neo4j:5.12
    
    # Stop and remove existing container to ensure a clean start
    if [ "$(sudo docker ps -q -f name=neo4j_db)" ]; then
        log_step "Stopping existing neo4j_db container..."
    sudo docker stop neo4j_db
    fi
    if [ "$(sudo docker ps -aq -f status=exited -f name=neo4j_db)" ]; then
        log_step "Removing existing neo4j_db container..."
        sudo docker rm neo4j_db
    fi
    
    # Run the Neo4j container
    log_step "Starting Neo4j container..."
    sudo docker run -d \
        --name neo4j_db \
        -p 7474:7474 -p 7687:7687 \
        -v $NEO4J_DATA_DIR:/data \
        -e NEO4J_AUTH=neo4j/${NEO4J_PASSWORD} \
        -e NEO4J_PLUGINS='["apoc"]' \
        -e NEO4J_apoc_export_file_enabled=true \
        -e NEO4J_apoc_import_file_enabled=true \
        -e NEO4J_apoc_import_file_use__neo4j__config=true \
        --user=$(id -u):$(id -g) \
        neo4j:5.12

    # Wait for Neo4j to be ready
    log_step "Waiting for Neo4j to be ready..."
    until sudo docker exec neo4j_db cypher-shell "RETURN 'Neo4j is ready' AS message" &> /dev/null; do
        echo "Waiting for Neo4j..."
        sleep 5
    done
    
    echo "Neo4j is running and ready."
}

setup_backend() {
    log_step "4. Setting Up Backend"
    
    # Copy application files
    log_step "Copying application files to $LMS_APP_DIR"
    sudo rsync -a --exclude='.git' --exclude='setup.sh' ./ $LMS_APP_DIR/
    
    # Create virtualenv
    log_step "Creating Python virtual environment"
    sudo python3 -m venv $LMS_APP_DIR/venv
    
    # Install dependencies
    log_step "Installing Python dependencies"
    sudo $LMS_APP_DIR/venv/bin/pip install -r $LMS_APP_DIR/requirements.txt
    
    # Create systemd service file
    log_step "Creating systemd service for LMS API"
    sudo bash -c "cat > /etc/systemd/system/lms-api.service" <<'EOF'
[Unit]
Description=LMS API Service
After=network.target

[Service]
EnvironmentFile=$LMS_APP_DIR/.env.production
User=root
Group=www-data
WorkingDirectory=$LMS_APP_DIR
ExecStart=$LMS_APP_DIR/venv/bin/uvicorn src.api:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd, enable and start the service
    log_step "Enabling and starting LMS API service"
    sudo systemctl daemon-reload
    sudo systemctl enable lms-api.service
    sudo systemctl start lms-api.service
    
    echo "Backend setup complete."
}

setup_frontend() {
    log_step "5. Setting Up Frontend"
    
    # Install npm if not already installed
    if ! command -v npm &> /dev/null
    then
        log_step "npm not found, installing..."
        sudo apt-get install -y npm
    fi
    
    # Build frontend
    log_step "Building frontend..."
    (cd frontend && npm install && npm run build)
    
    # Copy built files
    log_step "Copying frontend files to $FRONTEND_DIR"
    sudo rsync -a frontend/dist/ $FRONTEND_DIR/
    
    echo "Frontend setup complete."
}

configure_nginx() {
    log_step "6. Configuring NGINX"
    
    # Create NGINX site configuration
    sudo bash -c "cat > /etc/nginx/sites-available/lms-frontend" <<'EOF'
server {
    listen 80;
    server_name _;

    root $FRONTEND_DIR;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
EOF

    # Remove default site and enable new site
    if [ -f /etc/nginx/sites-enabled/default ]; then
        sudo rm /etc/nginx/sites-enabled/default
    fi
    sudo ln -sf /etc/nginx/sites-available/lms-frontend /etc/nginx/sites-enabled/
    
    # Restart NGINX
    sudo systemctl restart nginx
    
    echo "NGINX configured and restarted."
}

setup_security() {
    log_step "7. Setting Up Firewall and SSL"
    
    # Configure UFW
    log_step "Configuring UFW firewall"
    sudo ufw allow 22/tcp
    sudo ufw allow 80/tcp
    sudo ufw allow 443/tcp
    sudo ufw --force enable
    
    # Obtain and install SSL certificate
    log_step "Obtaining and installing SSL certificate with Certbot"
    if [ -z "${DOMAIN_NAME-}" ]; then
        echo "Please enter your domain name for the SSL certificate (e.g., example.com):"
        read DOMAIN_NAME
        export DOMAIN_NAME
    fi
    sudo certbot --nginx -d $DOMAIN_NAME --non-interactive --agree-tos --email webmaster@$DOMAIN_NAME
    
    echo "Firewall and SSL setup complete."
}

finalize_setup() {
    log_step "8. Finalizing and Clean Up"
    echo "LMS / MANTLE setup is complete."
    echo "To run this script again, you can make it executable with:"
    echo "chmod +x setup.sh"
}


setup_env_file() {
    log_step "Create and Configure .env.production file"
    
    ENV_FILE="$LMS_APP_DIR/.env.production"
    TEMPLATE_FILE="$LMS_APP_DIR/.env.production.template"

    # Copy template to .env.production if it doesn't exist
    if [ ! -f "$ENV_FILE" ]; then
        log_step "Creating $ENV_FILE from template."
        sudo cp "$TEMPLATE_FILE" "$ENV_FILE"
        sudo chown $USER:$USER "$ENV_FILE" # Ensure current user can edit
    fi

    # Prompt user to fill in missing values if they are empty
    # We will only process the variables we know should be filled by the user.
    # NEO4J_PASSWORD is handled by the neo4j setup.
    # LMS_ENV is set to production.
    # NEO4J_URI is fixed.
    # SSL_CERT_PATH and SSL_KEY_PATH are handled by certbot.

    # API_SECRET_KEY
    if grep -q "^API_SECRET_KEY=\s*$" "$ENV_FILE"; then
        echo "Please enter a value for API_SECRET_KEY:"
        read -s API_SECRET_KEY_VALUE
        sudo sed -i "s/^API_SECRET_KEY=\s*$/API_SECRET_KEY=$API_SECRET_KEY_VALUE/" "$ENV_FILE"
    fi

    # EMBEDDING_API_KEY
    if grep -q "^EMBEDDING_API_KEY=\s*$" "$ENV_FILE"; then
        echo "Please enter a value for EMBEDDING_API_KEY:"
        read -s EMBEDDING_API_KEY_VALUE
        sudo sed -i "s/^EMBEDDING_API_KEY=\s*$/EMBEDDING_API_KEY=$EMBEDDING_API_KEY_VALUE/" "$ENV_FILE"
    fi

    echo ".env.production file checked and configured."
}

install_dependencies
setup_directories
setup_env_file
configure_neo4j
setup_backend
setup_frontend
configure_nginx
setup_security
finalize_setup


echo "LMS / MANTLE - Production Deployment Setup Script"
echo "================================================="
echo ""
echo "This script will install and configure the entire LMS application stack."
echo "It is safe to run this script multiple times."
echo ""