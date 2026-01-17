#!/bin/bash
# scripts/deploy.sh - Manual deployment script

set -e  # Exit on error

echo "🚀 Starting deployment process..."

# Generate version
VERSION="v1.5.$(date +%Y%m%d-%H%M)"
echo "📦 Version: $VERSION"

# Update version file
echo "$VERSION" > data/deployed_version.txt

# Commit version
git add data/deployed_version.txt
git commit -m "Deploy version $VERSION" || echo "No version changes to commit"

# Push to remote (triggers GitHub Actions if configured)
echo "📤 Pushing to GitHub..."
git push origin $(git branch --show-current)

# Alternative: Direct Fly.io deployment
echo "🛫 Deploying to Fly.io..."
flyctl deploy --remote-only

echo "✅ Deployment complete!"
echo "🔍 Check status: https://lore-management-system.fly.dev/health"
