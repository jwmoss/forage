# Security Policy

## Session Data

**Never commit session data.** The `forage login` command stores browser session data (including cookies) in `~/.config/forage/session/`. This directory contains sensitive authentication tokens.

If you accidentally commit session data:
1. Immediately revoke your Facebook session by logging out of all devices
2. Change your Facebook password
3. Remove the sensitive data from your git history

## Scraped Data

Scraped data may contain personal information from group members. Handle it responsibly:
- Don't share scraped data publicly without consent
- Store it securely
- Delete it when no longer needed
- Consider local privacy regulations (GDPR, CCPA, etc.)

## Reporting Vulnerabilities

If you discover a security vulnerability, please report it by opening a GitHub issue or contacting the maintainer directly. Do not disclose security vulnerabilities publicly until they have been addressed.

## Best Practices

1. **Use environment isolation**: Run forage in a dedicated virtual environment
2. **Limit scraping scope**: Only scrape what you need
3. **Respect rate limits**: The built-in delays help avoid triggering Facebook's anti-automation
4. **Review output**: Check scraped data before storing or sharing
