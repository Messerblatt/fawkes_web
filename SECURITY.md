# Security Considerations

## Implemented Security Measures

### 1. Rate Limiting
- **Flask-Limiter**: Prevents abuse and DoS attacks
- Default limits: 200 requests/day, 50 requests/hour
- Endpoint-specific limits:
  - `/upload`: 10 requests/minute
  - `/cloak`: 5 requests/minute
  - `/download`: 10 requests/minute
  - `/`: 30 requests/minute

### 2. Content Security Policy (CSP)
- Restricts resource loading to trusted sources
- Prevents XSS attacks
- Configured via Flask-Talisman

### 3. Security Headers
- `Strict-Transport-Security` (HSTS)
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: SAMEORIGIN`
- `X-XSS-Protection: 1; mode=block`

### 4. Input Validation
- File type whitelist (PNG, JPG, JPEG, GIF, BMP)
- File size limit (16MB)
- Image content validation using PIL
- Protection against decompression bombs
- Filename sanitization
- Path traversal prevention
- Mode validation (low/mid/high only)

### 5. Session Security
- Secure session cookies (HTTPS only)
- HttpOnly cookies (prevents XSS)
- SameSite=Lax (CSRF protection)
- 1-hour session lifetime
- Concurrent session limiting (max 5)

### 6. Command Injection Prevention
- Subprocess calls use list format (no shell)
- Mode parameter validation
- Path validation and sanitization
- No user input directly in commands

### 7. Cross-Site Scripting (XSS) Prevention
- Output sanitization in JavaScript
- Content-Type headers properly set
- CSP prevents inline script execution

### 8. File Upload Security
- Secure filename generation
- File content validation
- Temporary file cleanup
- Upload directory isolation
- File size restrictions

### 9. WebSocket Security
- CORS restrictions
- Session validation
- Connection rate limiting
- Automatic timeout (60s)

### 10. Error Handling
- Generic error messages to users
- Detailed logging for administrators
- No stack traces exposed
- Custom error pages

## Configuration for Production

### Environment Variables

Create a `.env` file:

\`\`\`bash
SECRET_KEY=<generate-with-secrets-token-hex-32>
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
FORCE_HTTPS=True
FLASK_ENV=production
\`\`\`

Generate SECRET_KEY:
\`\`\`bash
python -c "import secrets; print(secrets.token_hex(32))"
\`\`\`

### Gunicorn Configuration

Update `gunicorn_config.py`:

\`\`\`python
# Limit request sizes
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190

# Timeouts
timeout = 120
keepalive = 5
\`\`\`

### Nginx Security Headers

Add to `nginx.conf`:

\`\`\`nginx
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "no-referrer-when-downgrade" always;
\`\`\`

## Monitoring and Logging

### Enable Logging

\`\`\`python
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
\`\`\`

### Monitor for Attacks

Watch for:
- Repeated 429 (rate limit) errors
- Failed upload attempts
- Unusual file sizes or types
- Excessive WebSocket connections

### Log Analysis

\`\`\`bash
# Monitor rate limiting
sudo journalctl -u fawkes-web | grep "429"

# Monitor errors
sudo journalctl -u fawkes-web | grep "ERROR"

# Monitor uploads
sudo journalctl -u fawkes-web | grep "upload"
\`\`\`

## Firewall Configuration

\`\`\`bash
# UFW example
sudo ufw enable
sudo ufw allow 22/tcp  # SSH
sudo ufw allow 80/tcp  # HTTP
sudo ufw allow 443/tcp # HTTPS
sudo ufw deny 5000/tcp # Block direct app access
\`\`\`

## Regular Security Tasks

### Weekly
- Review logs for suspicious activity
- Check disk usage in upload directory
- Verify SSL certificate validity

### Monthly
- Update dependencies: `pip list --outdated`
- Review and update firewall rules
- Test backup restoration

### Quarterly
- Security audit of code changes
- Penetration testing
- Review access controls

## Vulnerability Reporting

If you discover a security vulnerability:
1. Do NOT open a public issue
2. Email: security@yourdomain.com
3. Include: description, impact, reproduction steps
4. Allow 90 days for fix before public disclosure

## Additional Hardening

### 1. Implement Authentication
Consider adding user authentication for production use.

### 2. Add Request Signing
Implement HMAC signatures for API requests.

### 3. Enhanced Monitoring
Use tools like:
- Fail2ban (ban IPs with failed requests)
- ModSecurity (WAF)
- OSSEC (HIDS)

### 4. Regular Backups
Implement automated backups of:
- Application code
- Configuration files
- Logs (if needed)

### 5. Keep Dependencies Updated
\`\`\`bash
pip install --upgrade pip
pip list --outdated
pip install --upgrade <package>
\`\`\`

## Known Limitations

1. Rate limiting is in-memory (resets on restart)
2. Session tracking is in-memory (not distributed)
3. File storage is local (not suitable for multi-server setups)

## Future Security Enhancements

- [ ] Database-backed rate limiting
- [ ] Distributed session management
- [ ] Object storage for uploaded files
- [ ] API authentication tokens
- [ ] Request signing/verification
- [ ] Enhanced audit logging
- [ ] Automatic malware scanning
