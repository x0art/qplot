# Pro Trial Claim via API

## Overview

After registering a Qoder account and creating a PAT, make an authenticated API
call to Qoder's backend to trigger the automatic 14-day Pro trial grant.
This emulates what the Qoder CLI does on first sign-in.

## Flow

```
Register → Verify → Create PAT → Claim Pro Trial → OAuth/9Router
                                      │
                                      ▼
                    POST /api/v1/user/trial
                    Authorization: Bearer <pat>
                    User-Agent: QoderCLI/1.0
```

## Files

### `src/qoder_autopilot/auth/trial.py` (NEW)
- One async function: `claim_pro_trial(pat: str) -> bool`
- Makes HTTP POST to Qoder trial endpoint
- Returns True on success (2xx), False on failure

### `src/qoder_autopilot/infra/config.py` (MODIFY)
- Add `qoder_trial_url: str = "https://openapi.qoder.sh/api/v1/user/trial"`

### `src/qoder_autopilot/cli.py` (MODIFY)
- Import `claim_pro_trial` and call it after PAT creation + OAuth restore
- Add to step logging
- Non-fatal — registration continues if trial claim fails

## Error Handling
- Trial claim failures are non-fatal (account already registered)
- Log success/failure clearly
