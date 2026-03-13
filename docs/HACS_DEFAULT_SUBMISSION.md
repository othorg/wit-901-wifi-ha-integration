# HACS Default Submission Checklist (WIT 901 WIFI)

Use this checklist before submitting to the official HACS default repository list.

## Repository readiness

- Public repository on GitHub
- Default branch: `main`
- Valid `hacs.json` in repo root
- Integration code under `custom_components/wit_901_wifi/`
- Valid `manifest.json` with matching version in `const.py`
- `README.md` with install instructions and at least one image
- License file present
- GitHub Releases created from semver tags (`vX.Y.Z`)

## CI/Validation readiness

- HACS validation workflow green
- Hassfest workflow green
- Test and lint workflows green

## Branding readiness

- Local integration brand assets:
  - `custom_components/wit_901_wifi/brand/icon.png`
  - `custom_components/wit_901_wifi/brand/icon@2x.png`
  - `custom_components/wit_901_wifi/brand/dark_icon.png`
  - `custom_components/wit_901_wifi/brand/dark_icon@2x.png`
  - `custom_components/wit_901_wifi/brand/logo.png`
  - `custom_components/wit_901_wifi/brand/logo@2x.png`
  - `custom_components/wit_901_wifi/brand/dark_logo.png`
  - `custom_components/wit_901_wifi/brand/dark_logo@2x.png`
- Optional HACS/repo fallback assets:
  - `hacs.png`
  - `icon.png`
  - `brand/*`

## Manual submission steps (maintainer)

1. Submit integration to HACS default list:
   - Open: <https://github.com/hacs/default>
   - Add repo in category **integration** (via PR).
2. Submit domain branding to Home Assistant brands:
   - Open: <https://github.com/home-assistant/brands>
   - Add branding for domain `wit_901_wifi` (via PR).
3. Wait for both PRs to be merged.
4. Re-run HACS and clear frontend cache if icon/metadata is delayed.

