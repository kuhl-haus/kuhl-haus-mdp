# Security Policy

## Supported Versions

The following table indicates which versions of the project are currently receiving security updates:

| Version | Supported          | End-of-Support |
| ------- | ------------------ | -------------- |
| 0.2.x   | :white_check_mark: | TBD - 0.x.x versions are Beta versions and will not be supported after the 1.x.x release. |
| < 0.2.0 | :x:                | Proof-of-concept - not supported |

We generally support:
- The most recent major version with with its latest minor release.
- Always update to the latest version of this patckage to keep up with security patches.  **Security patches will NOT be backported to earlier releases**. 

## Reporting a Vulnerability

**We take security vulnerabilities seriously**. We appreciate your efforts in responsibly disclosing your findings.

### Reporting Process

**Do NOT disclose security vulnerabilities publicly via GitHub issues, discussions, or pull requests.**

If you believe you've found a security-related bug, we prefer that you fill out a [vulnerability report on GitHub](https://github.com/kuhl-haus/kuhl-haus-mdp/security/advisories/new) directly.  

If you do not have a GitHub account, you may submit your report via email to `security` at `kuhl.haus` using our [PGP key](#pgp-key).  **UNENCRYPTED emails from UNVERIFIED senders are AUTOMATICALLY REJECTED.**  

Include the following details:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any suggested mitigation measures
   - Your contact information for follow-up

### What to Expect

- **Initial Response**: We will acknowledge your report within **48 hours**.
- **Assessment**: We aim to verify all reports within **7 days**.
- **Regular Updates**: You will receive updates on the status of your report at least once per week.
- **Resolution Timeline**: We aim to resolve critical vulnerabilities within **30 days** of verification.

### Disclosure Policy

We follow a **coordinated disclosure** process:

1. Report remains confidential during investigation and patching.
2. We develop and test a fix.
3. We release updated versions with appropriate CVE identifiers.
4. **Public disclosure occurs 30 days after the fix is released** unless otherwise agreed.

### Recognition

- We gladly acknowledge security researchers who report valid vulnerabilities.
- With your permission, we'll add your name to our security acknowledgments page.

## Security Best Practices Used in This Project

- **Automated Security Testing**: All commits to the mainline branch undergo [automated CodeQL scanning](https://github.com/kuhl-haus/kuhl-haus-mdp/actions/workflows/github-code-scanning/codeql).
- **Regular Dependency Updates**: We use Dependabot automation to keep dependencies updated. [Dependabot Updates](https://github.com/kuhl-haus/kuhl-haus-mdp/actions/workflows/dependabot/dependabot-updates)
- **Supply Chain Security**: We sign releases, use artifact verification, and publish to PyPI with a [Trusted Publisher](https://docs.pypi.org/trusted-publishers/).

## PGP Key

**UNENCRYPTED emails from UNVERIFIED senders are AUTOMATICALLY REJECTED.**

For encrypted communication, please use our PGP key.

Security Contact:  `security` at `kuhl.haus`  
Fingerprint: `74d6f5d19c1747729c4c4d8403262a29b12a7124`  
Key type: ECC (Curve25519)

```
-----BEGIN PGP PUBLIC KEY BLOCK-----

xjMEZ+2fChYJKwYBBAHaRw8BAQdAw0++7vPj84/uddoc/JHVnaTBt/I09qyL
C3vVXPgTsKLNJ3NlY3VyaXR5QGt1aGwuaGF1cyA8c2VjdXJpdHlAa3VobC5o
YXVzPsLAEQQTFgoAgwWCZ+2fCgMLCQcJkAMmKimxKnEkRRQAAAAAABwAIHNh
bHRAbm90YXRpb25zLm9wZW5wZ3Bqcy5vcmeXcJoftkrHP0VWWrn0zlM1FQB+
Hc1HfRxunlJPXidwHQMVCggEFgACAQIZAQKbAwIeARYhBHTW9dGcF0dynExN
hAMmKimxKnEkAABV+AD+MVmJCpxBmSKQ5MdKmCtgEVKr7k8yzquH3EDj3Vz9
XOgA+QFK1XGsUILLVEOGdwxWIeHMrA6Dj8RLMF6EQd3FwfMAzjgEZ+2fChIK
KwYBBAGXVQEFAQEHQB3vfOuClQ7ngePAoiDlQFZIVg73tv+C62T74EUL+hQl
AwEIB8K+BBgWCgBwBYJn7Z8KCZADJiopsSpxJEUUAAAAAAAcACBzYWx0QG5v
dGF0aW9ucy5vcGVucGdwanMub3JnlvCp9f7D/FoIx9d1c5+0TiEXJeY6KNQZ
bFYVFKQaTNQCmwwWIQR01vXRnBdHcpxMTYQDJiopsSpxJAAATIsBAO+ogDEw
+EgnBbrTHMyVG4BY1toSq+fiBg4l3erbEnIIAQC1vs+fTXhHQWfcWiTP4wwx
yTG23Z0wOxMxNx1qUdV9Bg==
=TXmO
-----END PGP PUBLIC KEY BLOCK-----
```

## Safe Harbor

We consider security research conducted in good faith to be:
- **Authorized and legal**
- **Exempt from legal action**

The following activities are prohibited:
- Denial of service testing
- Social engineering attacks
- Testing of physical security
- Accessing or modifying data of other users

## Security Updates

Security updates will be announced via:
- GitHub Security Advisories
- Our project newsletter or mailing list
- Release notes

Subscribe to these channels to stay informed about security updates.

---

*This security policy is based on industry best practices for responsible disclosure and vulnerability management in open-source software.*



