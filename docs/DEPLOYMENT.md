# Deployment Guide

> **Note:** For the current production environment on DigitalOcean (Ubuntu 22.04), please refer to [DIGITAL_OCEAN_DEPLOYMENT.md](DIGITAL_OCEAN_DEPLOYMENT.md). The guide below primarily covers Fly.io deployment.

## Prerequisites
- Fly.io CLI installed: `curl -L https://fly.io/install.sh | sh`
- Fly.io account with app created: `fly launch` (if not done)
- GitHub repository with Fly.io secret configured

## Automatic Deployment (Recommended)

### Setup GitHub Actions
1. Get Fly.io API token: `fly auth token`
2. Add to GitHub Secrets:
   - Go to: Settings → Secrets and variables → Actions
   - Create: `FLY_API_TOKEN` with your token
3. Push to main or airpg-runtime-minimal branch - deployment happens automatically

### How It Works
The `.github/workflows/deploy.yml` workflow automatically:
1. Generates a version number based on timestamp: `v1.5.YYYYMMDD-HHMM`
2. Updates `data/deployed_version.txt` with the version
3. Commits the version file back to the repository
4. Deploys to Fly.io with the updated version

## Manual Deployment

### Using Deployment Script
```bash
./scripts/deploy.sh
```

This script will:
1. Generate a version number
2. Update `data/deployed_version.txt`
3. Commit and push changes
4. Deploy to Fly.io

### Using Fly CLI Directly
```bash
# Generate version
echo "v1.5.$(date +%Y%m%d-%H%M)" > data/deployed_version.txt

# Commit the version
git add data/deployed_version.txt
git commit -m "Deploy version v1.5.$(date +%Y%m%d-%H%M)"

# Deploy
fly deploy --remote-only
```

## Verify Deployment
```bash
# Check health endpoint
curl https://lore-management-system.fly.dev/health | jq

# Expected output should include:
# {
#   "status": "healthy",
#   "version": "v1.5.20260117-1234",
#   "deployed_at": "v1.5.20260117-1234",
#   "timestamp": "2026-01-17T12:34:56.789Z",
#   "checks": {
#     "neo4j": "connected",
#     "vector_index": "exists",
#     ...
#   },
#   "features": {
#     "ai_enabled": true,
#     ...
#   }
# }
```

## Version Display

The deployed version is displayed in the frontend:
- Bottom-right corner of the page
- Shows version from the health endpoint
- Styled with Obsidian & Gold theme

## Rollback

If you need to rollback to a previous version:

```bash
# List recent releases
fly releases

# Rollback to previous version
fly releases rollback <release-id>
```

Note: After rollback, you should update the `data/deployed_version.txt` file to reflect the rolled-back version.

## Troubleshooting

### Deployment Fails
1. Check Fly.io status: `fly status`
2. View logs: `fly logs`
3. Check secrets are set: `fly secrets list`

### Version Not Updating
1. Ensure `data/deployed_version.txt` exists and is tracked in git
2. Check GitHub Actions logs for commit errors
3. Verify FLY_API_TOKEN secret is set correctly

### Health Check Fails
1. Check app is running: `fly status`
2. View detailed logs: `fly logs`
3. Verify Neo4j connection is configured
