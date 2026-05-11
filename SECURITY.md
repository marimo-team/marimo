# Security Policy

marimo is committed to providing a secure environment for notebook development and application deployment. For a comprehensive overview of marimo's security model and features, see our [Security documentation](https://docs.marimo.io/security/).

## Supported Versions

We provide security patches for the latest stable release only. We encourage all users to stay on the latest version.

## Reporting a Vulnerability

To report a security vulnerability, [please draft an advisory through
GitHub](https://github.com/marimo-team/marimo/security/advisories/new), or
email the marimo team; security [at] marimo [dot] io.

Please include:
- A description of the vulnerability and its potential impact
- Steps to reproduce or a proof-of-concept
- Any suggested mitigations if known

### What to Expect

- **Acknowledgement**: We will respond within 3 business days to confirm receipt
- **Triage**: We will assess severity and scope within 7 days
- **Patch & disclosure**: We aim to release a fix and publish a CVE/advisory simultaneously, typically within 90 days of the initial report

We will keep you informed throughout the process and credit you in the advisory unless you prefer to remain anonymous.

### What Warrants a Security Advisory

We issue CVEs and security advisories when:

- A vulnerability could affect long-running app deployments
- End-users are directly impacted
- The issue has security implications beyond normal bug fixes

General safety improvements and hardening work are documented in our [release notes](https://github.com/marimo-team/marimo/releases) without formal advisories.

Advisories will be escalated to a CVE and/or a general advisory issued if end-users
are directly impacted. Attribution for any actionable report will be provided
in the section below (unless anonymity is preferred).

### molab Security

For security issues affecting [molab](https://docs.marimo.io/guides/molab/) (our hosted platform):

- Reports can be submitted through the same channels above
- We handle disclosure on a case-by-case basis
- General security improvements are disclosed publicly when applicable
- User-specific issues are handled privately through direct notification

## Recognition and Thanks

We deeply appreciate the security research community's efforts to improve marimo's security. Responsible disclosure helps protect all marimo users, and we recognize the time and expertise that goes into security research.

We would like to acknowledge and thank the following individuals for their responsible disclosure of security issues:

 - @AlexanderBarabanov
 - @pwntester
 - @s-celles
 - @acepace
 - @devgi
 - @W-M-T (Ward Theunisse)
 - @doredry
 - @q1uf3ng from OneKey Anzen Lab
 - @Fushuling @RacerZ-fighting
 - @GCXWLP
 - @Vincent550102
 - @l3tchupkt
 - @wooseokdotkim
 - @Jvr2022
 - @offset
 - @jeremysommerfeld8910-cpu
 - @jinyimeng01 @boom-dy @zz-yy

Your contributions help keep marimo safe for the entire community. We encourage security researchers to report issues and welcome your help in making marimo more secure.
