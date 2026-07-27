# PAT Creation in Registration Flow

## Overview

Add a PAT (Personal Access Token) creation step during Qoder account registration.
After the user's account is verified via OTP, the browser navigates to
`qoder.com/account/integrations` and creates a PAT automatically, then saves
it along with the account credentials.

## Flow

```
Current:  Register → Solve Captcha → Enter OTP → Verify → [OAuth/9Router]
Proposed: Register → Solve Captcha → Enter OTP → Verify → Create PAT → [OAuth/9Router]
                                                             │
                                                             ▼
                                                   qoder.com/account/integrations
                                                   Click "+ New Token"
                                                   Fill name="a"
                                                   Set date=31/7/2026
                                                   Click create
                                                   Read & save PAT token
```

## Modified Files

### `src/qoder_autopilot/auth/pat.py` (NEW)
- Module with one async function: `create_pat(page) -> str | None`
- Uses same Playwright/Camoufox page object already available in the registration flow
- Navigates to `qoder.com/account/integrations`
- Interacts with the PAT creation modal via XPath selectors
- Returns the PAT token string or None on failure

### `src/qoder_autopilot/infra/config.py` (MODIFY)
- Add `qoder_integrations_url` setting: `"https://qoder.com/account/integrations"`

### `src/qoder_autopilot/register.py` (MODIFY)
- Import and call `create_pat()` after successful OTP verification
- Add as Step 6 (before final success)
- Log progress and errors gracefully

### `src/qoder_autopilot/cli.py` (MODIFY)
- Include PAT in saved credentials dict
- Surface PAT in output results

## XPath Selectors

| Element | XPath |
|---------|-------|
| "+ New Token" button | `/html/body/div[1]/div/div/div/main/div[2]/div[3]/div[1]/button` |
| Name input (modal) | `/html/body/div[2]/div/div[2]/div/div[1]/div/div[2]/div/div[1]/input` |
| Date picker (modal) | `/html/body/div[2]/div/div[2]/div/div[1]/div/div[2]/div/div[2]/div` |
| Create button (modal) | `/html/body/div[2]/div/div[2]/div/div[1]/div/div[3]/div/div/button[2]` |
| PAT token display | `/html/body/div[2]/div/div[2]/div/div[1]/div/div[2]/div/div[2]/div` |

## Error Handling

- PAT creation failures are non-fatal (account is still registered)
- Log errors and continue with OAuth/9Router step
- Screenshot on failure for debugging

## Security

- PAT token stored in `qoder_accounts.json` alongside other credentials
- File permissions restricted to owner-only (existing pattern)
