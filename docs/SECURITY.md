# Security Best Practices

## Overview

This document outlines security best practices for deploying and operating the Lore Management System (LMS). Following these guidelines will help protect your data, credentials, and system integrity.

---

## Environment Variables

### Required Credentials

The LMS requires the following environment variables to be configured:

#### Neo4j Database
- **`NEO4J_URI`**: Connection URI for your Neo4j database
  - Local: `bolt://localhost:7687`
  - Neo4j Aura (SSL): `neo4j+s://your-instance.databases.neo4j.io`
  - Neo4j Aura (Self-signed cert): `neo4j+ssc://your-instance.databases.neo4j.io`
  
- **`NEO4J_USER`**: Neo4j username (default: `neo4j`)
  
- **`NEO4J_PASSWORD`**: Neo4j password
  - **⚠️ CRITICAL**: Never use default passwords in production
  - Use a strong, unique password (minimum 12 characters)
  - Include uppercase, lowercase, numbers, and special characters

#### API Security
- **`API_SECRET_KEY`**: Secret key for API authentication and session management
  - **Minimum 32 characters required**
  - Generate using: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
  - Rotate periodically (recommended: every 90 days)

#### Optional Services
- **`GEMINI_API_KEY`**: Google Gemini API key for AI-powered features
  - Required for: Entity extraction, contradiction detection, query agents
  - If not set, the application runs with AI features disabled
  - Obtain from: https://makersuite.google.com/app/apikey

- **`EMBEDDING_API_KEY`**: API key for embedding service (if using separate service)

---

## Setting Up Credentials Securely

### Step 1: Copy the Template
```bash
cp .env.production.template .env
```

### Step 2: Generate Secure Keys
```bash
# Generate API secret key (32+ characters)
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Set a strong Neo4j password
# Use a password manager to generate a random password
```

### Step 3: Edit Your .env File
Open `.env` in a secure text editor and replace ALL placeholder values:

```bash
# Example .env (with your actual values)
NEO4J_URI=neo4j+s://abc123.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=YourSecurePassword123!WithSpecialChars

API_SECRET_KEY=q4f8x9vN_3Jh7pLmK2sT5uW8yZ1aE6dH9cG4bF7jI0
GEMINI_API_KEY=AIzaSyD-actual-key-here-with-many-characters

# Optional
EMBEDDING_API_KEY=your_embedding_key_if_needed
```

### Step 4: Secure the File
```bash
# Restrict file permissions (Unix/Linux/Mac)
chmod 600 .env

# Verify it's not tracked by git
git status  # Should not show .env
```

---

## Credential Security Checklist

- [ ] All credentials are unique and randomly generated
- [ ] No credentials are hardcoded in source files
- [ ] `.env` file has restricted permissions (600 or stricter)
- [ ] `.env` is listed in `.gitignore` (verified)
- [ ] API keys are rotated periodically
- [ ] Passwords meet complexity requirements (12+ chars, mixed case, numbers, symbols)
- [ ] Production credentials are different from development/test credentials
- [ ] Credentials are stored in a secure password manager
- [ ] Old/expired credentials are revoked, not just replaced

---

## Production Deployment

### Environment-Specific Configuration

Use separate `.env` files for different environments:

```
.env.development  # Local development
.env.test         # Testing environment
.env.production   # Production (never commit!)
```

Load the appropriate file based on your environment:
```bash
# Development
cp .env.development .env

# Production
cp .env.production .env
```

### Docker Deployment

When deploying with Docker, use Docker secrets or environment variables:

```bash
# Using Docker run
docker run -d \
  --env-file .env \
  --name lms-app \
  lms:latest

# Using docker-compose with env_file
# See docker-compose.yml for configuration
```

### Cloud Deployment (Heroku, Fly.io, etc.)

**Never** commit `.env` to version control. Use the platform's secret management:

```bash
# Fly.io
fly secrets set NEO4J_PASSWORD="YourSecurePassword"
fly secrets set API_SECRET_KEY="YourSecretKey"

# Heroku
heroku config:set NEO4J_PASSWORD="YourSecurePassword"
heroku config:set API_SECRET_KEY="YourSecretKey"
```

---

## SSL/TLS Configuration

For production deployments, enable SSL/TLS:

### Neo4j Aura (Managed)
- Uses SSL by default
- Use `neo4j+s://` or `neo4j+ssc://` URI scheme
- Certificate validation is handled automatically

### Self-Hosted Neo4j
- Configure SSL certificates in Neo4j configuration
- Mount certificates in Docker containers
- Use environment variables for cert paths:
  ```
  SSL_CERT_PATH=/etc/letsencrypt/live/your_domain/fullchain.pem
  SSL_KEY_PATH=/etc/letsencrypt/live/your_domain/privkey.pem
  ```

---

## Input Validation

The LMS includes built-in input validation to prevent injection attacks:

### Using Sanitization Functions

```python
from src.core.utils import sanitize_user_input, validate_canon_id, validate_env_var

# Sanitize user input before processing
user_query = sanitize_user_input(request.query, max_length=500)

# Validate entity IDs
entity_id = validate_canon_id(request.id)

# Validate environment variables at startup
db_password = validate_env_var("NEO4J_PASSWORD", os.getenv("NEO4J_PASSWORD"))
```

### Security Features
- Maximum input length enforcement
- Character whitelist validation
- Automatic SQL/Cypher injection prevention
- Environment variable validation at startup

---

## Database Security

### Neo4j Best Practices

1. **Authentication**: Always require authentication (never use `NEO4J_AUTH=none`)
2. **Network Security**: 
   - Use SSL/TLS for all connections
   - Restrict network access to database ports (7474, 7687)
   - Use firewall rules or VPC security groups
3. **Backup**: Regular automated backups of your Neo4j database
4. **Updates**: Keep Neo4j updated to the latest stable version
5. **Audit Logs**: Enable Neo4j audit logging in production

---

## Monitoring and Incident Response

### Application Logs

The LMS logs all security-relevant events:
- Failed authentication attempts
- Invalid input validation
- Database connection failures
- API errors

Review logs regularly for suspicious activity:
```bash
# Check application logs
tail -f logs/lms.log

# Search for security events
grep -i "validation failed\|authentication failed" logs/lms.log
```

### Incident Response

If you suspect a security breach:

1. **Immediate Actions**:
   - Rotate all credentials immediately
   - Check audit logs for unauthorized access
   - Disable compromised API keys
   - Review database for unauthorized changes

2. **Investigation**:
   - Review application logs for the time period
   - Check Neo4j audit logs
   - Identify the source and scope of the breach

3. **Recovery**:
   - Restore from a clean backup if needed
   - Patch any vulnerabilities
   - Update security documentation

---

## Reporting Security Issues

If you discover a security vulnerability in the LMS:

**DO NOT** open a public GitHub issue.

Instead, please report security issues privately to:
- **Email**: [Project maintainer email - to be configured]
- **Subject**: "SECURITY: [Brief description]"

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if available)

We will respond within 48 hours and work with you to address the issue.

---

## Security Checklist for New Deployments

Before deploying LMS to production:

- [ ] All placeholder credentials replaced with secure values
- [ ] `.env` file is not committed to version control
- [ ] SSL/TLS enabled for all external connections
- [ ] Neo4j authentication enabled and secured
- [ ] API keys are generated with sufficient entropy
- [ ] File permissions are restricted appropriately
- [ ] Firewall rules configured to limit access
- [ ] Logging and monitoring configured
- [ ] Backup and recovery procedures tested
- [ ] Security documentation reviewed by team
- [ ] Incident response plan established

---

## References

- [Neo4j Security Checklist](https://neo4j.com/docs/operations-manual/current/security/)
- [OWASP Top Ten](https://owasp.org/www-project-top-ten/)
- [FastAPI Security Best Practices](https://fastapi.tiangolo.com/tutorial/security/)
- [Python Security Best Practices](https://python.readthedocs.io/en/stable/library/security_warnings.html)

---

## Version History

- **2025-12-12**: Initial security documentation created
- Security hardening: Credential validation, input sanitization, environment validation

---

**Remember**: Security is an ongoing process, not a one-time setup. Regularly review and update your security practices.
