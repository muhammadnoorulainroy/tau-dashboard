#!/bin/bash

# Script to create .env file from JSON
echo "Creating .env file from turing-genai-ws-58339643dd3f.json..."

python3 << 'EOF'
import json
from pathlib import Path

# Read the JSON file
json_file = Path('turing-genai-ws-58339643dd3f.json')
if not json_file.exists():
    print("❌ Error: turing-genai-ws-58339643dd3f.json not found!")
    exit(1)

with open(json_file, 'r') as f:
    creds = json.load(f)

# Create .env content
env_content = f"""# Database Configuration (UPDATE THESE!)
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your_password_here
DB_NAME=tau_dashboard

# GitHub Configuration (UPDATE THESE!)
GITHUB_TOKEN=your_github_token_here
GITHUB_REPO=owner/repo

# Security (UPDATE THIS!)
SECRET_KEY=your_secret_key_here

# Google Service Account Configuration
GOOGLE_SERVICE_ACCOUNT_TYPE={creds['type']}
GOOGLE_PROJECT_ID={creds['project_id']}
GOOGLE_PRIVATE_KEY_ID={creds['private_key_id']}
GOOGLE_PRIVATE_KEY="{creds['private_key']}"
GOOGLE_CLIENT_EMAIL={creds['client_email']}
GOOGLE_CLIENT_ID={creds['client_id']}
GOOGLE_AUTH_URI={creds['auth_uri']}
GOOGLE_TOKEN_URI={creds['token_uri']}
GOOGLE_AUTH_PROVIDER_CERT_URL={creds['auth_provider_x509_cert_url']}
GOOGLE_CLIENT_CERT_URL={creds['client_x509_cert_url']}
GOOGLE_UNIVERSE_DOMAIN={creds['universe_domain']}
"""

# Write to .env
with open('.env', 'w') as f:
    f.write(env_content)

print("✅ .env file created successfully!")
print("")
print("⚠️  IMPORTANT: Update the following values in .env:")
print("   - DB_PASSWORD")
print("   - GITHUB_TOKEN")
print("   - GITHUB_REPO")
print("   - SECRET_KEY")
print("")
print("Then restart the backend server.")
EOF
