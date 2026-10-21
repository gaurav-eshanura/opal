# Security Policy

## Reporting a vulnerability

If you find a security issue in Opal, please report it privately rather than
opening a public issue.

**Email:** security@opal.local *(replace with a monitored address before publishing)*
**GitHub:** use the repository's *Security → Report a vulnerability* tab.

Please include:

- what the issue is and what an attacker could do with it
- the version, operating system and how to reproduce it
- any proof-of-concept code or screenshots

You can expect an acknowledgement within 72 hours and an assessment within
seven days. We will keep you informed as we work on the fix, and we will
credit you in the release notes unless you would rather we did not.

## What Opal does and does not do with your files

Opal is built so that it *cannot* upload your documents:

- Every conversion, edit, OCR run and AI model runs in your own process, on
  your own machine.
- There is no telemetry, no analytics, no crash reporting and no account
  system. There is nowhere for your files to go.
- The only network request Opal ever makes is to download an optional AI
  model. Those downloads are constrained:
  - the host must be on a fixed allow-list (`github.com` and
    `*.githubusercontent.com`),
  - the connection is pinned to a validated, public IP address, so a DNS
    record cannot be changed underneath the app to redirect it,
  - redirects are followed manually and re-checked at every step, and the
    scheme must be `http` or `https`,
  - the download path is reduced to a single filename with no `..` component,
    so it cannot escape the model cache directory,
  - the file must look like a model and, where a fingerprint is known, must
    match its pinned SHA-256. Anything else is deleted rather than cached.

## Scope

In scope: the Opal source in this repository, the build scripts, the model
downloader, the certificate handling, and the Windows context-menu and
autostart installers.

Out of scope: vulnerabilities in the third-party libraries Opal uses. Please
report those to their own maintainers.

## Notes for reviewers

- The private key of a DSC never leaves the machine. Opal loads the
  certificate, shows its details, and signs locally.
- The Windows context-menu and autostart entries are written to the
  registry under `HKEY_CURRENT_USER`, never `HKEY_LOCAL_MACHINE`, so no
  administrator rights are needed and the entries are per-user.
- The `portable.txt` marker keeps all state inside the application folder and
  is the recommended way to run Opal on a shared or counter machine.
