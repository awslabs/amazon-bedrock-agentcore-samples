# Path Fix Summary

## Issue
After moving scripts to the `scripts/` directory, the `setup_identity.sh` script was looking for files in the wrong locations.

## Files Fixed

### `scripts/setup_identity.sh`
Updated to handle being called from the parent directory:

1. **Script location detection**
   ```bash
   SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
   PARENT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
   ```

2. **Python script path**
   - Old: `python identity_setup.py`
   - New: `python "$SCRIPT_DIR/identity_setup.py"`

3. **.env file path**
   - Old: `source .env`
   - New: `source "$PARENT_DIR/.env"`

4. **identity_config.json path**
   - Old: `identity_config.json`
   - New: `"$PARENT_DIR/identity_config.json"`

5. **All .env updates**
   - Old: `.env`
   - New: `"$PARENT_DIR/.env"`

## How It Works Now

```
cloud_strands_insurance_agent/
├── .env                          ← Loaded from here
├── identity_config.json          ← Created here
└── scripts/
    ├── setup_identity.sh         ← Called from parent dir
    └── identity_setup.py         ← Executed from here
```

## Usage

From the `cloud_strands_insurance_agent` directory:
```bash
./scripts/setup_identity.sh
```

Or from the root directory via `deploy_all.sh`:
```bash
./deploy_all.sh
```

Both work correctly now!
