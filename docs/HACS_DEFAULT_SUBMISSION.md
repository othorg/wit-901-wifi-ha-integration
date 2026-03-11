## HACS Default Submission (Integration)

Repository: `othorg/wit-901-wifi-ha-integration`
Category: `integration`

### 1. Preconditions

- Integration files exist under `custom_components/wit_901_wifi/`.
- `manifest.json` includes required metadata (domain, name, version, docs, issue tracker, codeowners, config_flow).
- `hacs.json` exists in repo root.
- CI passes:
  - Python lint/tests
  - `hacs/action` (`category: integration`)
  - `hassfest`
- At least one tagged release exists (`vX.Y.Z`).

### 2. Manual GitHub setup (required)

- Set repository description.
- Add topics:
  - `hacs`
  - `home-assistant`
  - `home-assistant-integration`
  - `wit-motion`
  - `wt901wifi`

### 3. Add to HACS default list

1. Fork `https://github.com/hacs/default`
2. Edit file `integration` in your fork.
3. Add line:

```text
othorg/wit-901-wifi-ha-integration
```

4. Keep alphabetical order.
5. Open PR against `hacs/default`.

### 4. Suggested PR notes

- Integration type: local push (`iot_class: local_push`)
- Config Flow and Options Flow supported
- Branded assets included
- HACS validation, hassfest, and tests are green
