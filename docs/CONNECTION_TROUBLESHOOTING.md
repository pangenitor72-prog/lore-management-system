# Neo4j Connection Troubleshooting Guide

## Overview
This guide addresses connection issues between the LMS application and Neo4j, particularly when dealing with both Neo4j Aura (cloud) and local Neo4j instances.

---

## Common Connection Scenarios

### Scenario 1: Local Neo4j (Docker)
**URI Format:** `bolt://localhost:7687`

**Setup:**
```bash
# 1. Start Neo4j via Docker Compose
docker-compose up -d

# 2. Verify container is running
docker ps | grep neo4j

# 3. Check logs
docker logs airpg_brain

# 4. Configure .env file
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password  # From docker-compose.yml
```

**Test Connection:**
```bash
# Using cypher-shell
cypher-shell -a bolt://localhost:7687 -u neo4j -p password

# Or using Python
python -c "from neo4j import GraphDatabase; driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'password')); driver.verify_connectivity(); print('Connected!')"
```

---

### Scenario 2: Neo4j Aura (Cloud)
**URI Format:** `neo4j+s://xxxxx.databases.neo4j.io`

**Setup:**
```bash
# 1. Get connection details from Aura console
# - Connection URI (starts with neo4j+s://)
# - Username (usually 'neo4j')
# - Password (from Aura setup)

# 2. Configure .env file
NEO4J_URI=neo4j+s://your-instance-id.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_aura_password_here
```

**Important Notes:**
- Aura uses SSL by default (`neo4j+s://` scheme)
- Connection timeout is 30 seconds (configurable in code)
- Aura instances may take a few seconds to wake up if paused

**Test Connection:**
```bash
# Using cypher-shell
cypher-shell -a "neo4j+s://xxxxx.databases.neo4j.io" -u neo4j -p "your_password"

# Or check Aura console for connectivity status
```

---

## Migration: Local → Aura or Vice Versa

### Partial Migration Issue
If you started with local Neo4j and then created an Aura instance (or vice versa), you may have:
- **Data in local instance** that hasn't been migrated to Aura
- **Different URIs** in different config files
- **Confusion** about which database the app is connecting to

### How to Diagnose

**Check your .env file:**
```bash
cat .env | grep NEO4J_URI
```

**Check what the app sees:**
```bash
# Start the app and look at startup logs
uvicorn src.api.routes:app --reload

# Look for lines like:
# "Neo4j Aura/Secure scheme detected"  # Aura
# "Neo4j driver connected"              # Any connection
```

**Verify connection in Neo4j adapter:**
The adapter logs the scheme it detects:
- `bolt://` = Local instance
- `neo4j+s://` = Aura with SSL
- `neo4j+ssc://` = Aura with self-signed cert

---

### Resolution Steps

#### Option A: Commit to Local Neo4j
```bash
# 1. Update .env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password  # From docker-compose.yml

# 2. Start local Neo4j
docker-compose up -d

# 3. Restart application
uvicorn src.api.routes:app --reload
```

#### Option B: Commit to Neo4j Aura
```bash
# 1. Update .env with Aura credentials
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_aura_password

# 2. Migrate data (if needed)
# Export from local:
docker exec airpg_brain neo4j-admin database dump neo4j --to-path=/dumps
docker cp airpg_brain:/dumps/neo4j.dump ./

# Import to Aura:
# Use Aura console import feature or push command

# 3. Restart application
uvicorn src.api.routes:app --reload
```

#### Option C: Use Both (Development Pattern)
```bash
# Use .env.local for local development
cat > .env.local << EOF
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
EOF

# Use .env.production for Aura
cat > .env.production << EOF
NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_aura_password
EOF

# Switch between them:
cp .env.local .env    # For local dev
cp .env.production .env  # For production/Aura
```

---

## Debugging Connection Issues

### Issue: "Connection Refused"
**Symptoms:** Application fails to start, logs show connection errors

**Possible Causes:**
1. Neo4j not running (local)
2. Wrong URI in .env
3. Firewall blocking port 7687
4. Aura instance paused/suspended

**Solutions:**
```bash
# For local:
docker-compose ps  # Check if neo4j is running
docker-compose up -d  # Start if not running

# For Aura:
# Check Aura console - instance may be paused
# Resume instance if needed
# Check if your IP is whitelisted (Aura firewall)

# Test basic connectivity:
telnet localhost 7687  # Local
# or
ping your-instance.databases.neo4j.io  # Aura DNS
```

---

### Issue: "Authentication Failed"
**Symptoms:** Connection attempted but rejected

**Possible Causes:**
1. Wrong password in .env
2. Password changed in Neo4j but not updated in .env
3. Using wrong username (should be 'neo4j' usually)

**Solutions:**
```bash
# Verify credentials match:
# Local: Check docker-compose.yml
# Aura: Check Aura console

# Reset local Neo4j password if needed:
docker-compose down
docker volume rm lore-management-system_neo4j_data
docker-compose up -d
# Initial password is from docker-compose.yml NEO4J_AUTH setting
```

---

### Issue: "Wrong Database Being Queried"
**Symptoms:** Data exists but queries return empty results

**Possible Causes:**
1. Connected to wrong Neo4j instance (local vs Aura)
2. Data in different database than configured
3. URI environment variable not loaded

**Solutions:**
```bash
# 1. Verify which URI is being used
# Add debug logging to startup:
echo "Debug: NEO4J_URI=${NEO4J_URI}" >> /tmp/debug.log

# 2. Check database name
# Default is 'neo4j' - verify in .env if you have:
# NEO4J_DATABASE=neo4j  (or other name)

# 3. Query current connection in Neo4j Browser
# Visit http://localhost:7474 (local)
# Or Aura console query interface
# Run: CALL dbms.components() YIELD name, versions, edition
```

---

## URL/URI Confusion

### Common Mistakes

**Wrong:** Mixing HTTP and Bolt URLs
```bash
# These are for Browser access, NOT for app connection:
NEO4J_URI=http://localhost:7474  # ❌ Wrong
NEO4J_URI=https://console.neo4j.io  # ❌ Wrong

# Use Bolt protocol for app connection:
NEO4J_URI=bolt://localhost:7687  # ✅ Correct (local)
NEO4J_URI=neo4j+s://xxx.databases.neo4j.io  # ✅ Correct (Aura)
```

**Wrong:** Missing scheme
```bash
NEO4J_URI=localhost:7687  # ❌ Missing bolt://
NEO4J_URI=bolt://localhost  # ❌ Missing port
```

---

## Environment Variable Priority

The application loads environment variables in this order:
1. `.env` file (if present)
2. System environment variables
3. Defaults in code (for NEO4J_USER only)

**Best Practice:**
```bash
# Always use .env file for local development
cp .env.production.template .env
# Edit .env with your credentials
# .env is in .gitignore and won't be committed
```

---

## Validation Added (Security Update)

As of the recent security hardening PR, the application now:

1. **Validates credentials at startup** - Won't start with empty/missing values
2. **Logs clear error messages** - Tells you exactly what's wrong
3. **Supports both local and Aura** - Auto-detects scheme

**Example startup error:**
```
RuntimeError: Environment validation failed: Required environment variable NEO4J_URI is not set or is empty
```

This prevents silent failures and makes connection issues obvious.

---

## Quick Checklist

- [ ] `.env` file exists in project root
- [ ] `NEO4J_URI` is set correctly (bolt:// or neo4j+s://)
- [ ] `NEO4J_USER` is set (default: neo4j)
- [ ] `NEO4J_PASSWORD` matches actual database password
- [ ] Neo4j is running (docker ps or Aura console)
- [ ] Port 7687 is accessible (not blocked by firewall)
- [ ] Application started from project root
- [ ] Environment variables loaded (check logs)

---

## Still Having Issues?

1. **Check application logs** - Look for connection errors at startup
2. **Test connection manually** - Use cypher-shell or Python driver directly
3. **Verify Neo4j is accessible** - Use Neo4j Browser (port 7474)
4. **Check firewall settings** - Especially for Aura
5. **Review SECURITY.md** - For detailed setup instructions
6. **See TROUBLESHOOTING.md** - For other common issues

---

## Additional Resources

- **Neo4j Aura Setup:** https://neo4j.com/cloud/aura/
- **Neo4j Driver Docs:** https://neo4j.com/docs/python-manual/current/
- **LMS Security Guide:** `/docs/SECURITY.md`
- **LMS Architecture:** `/docs/ARCHITECTURE.md`

---

**Last Updated:** 2025-12-12  
**Related PRs:** Security hardening (credential validation)
