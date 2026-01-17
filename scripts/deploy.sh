#!/bin/bash
# scripts/deploy.sh - Manual deployment script

set -e  # Exit on error

echo "🚀 Starting deployment process..."

# Generate version using git commit count + short hash
COMMIT_COUNT=$(git rev-list --count HEAD)
SHORT_HASH=$(git rev-parse --short HEAD)
VERSION="v${COMMIT_COUNT}-${SHORT_HASH}"
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
