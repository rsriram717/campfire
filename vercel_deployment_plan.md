# Vercel Deployment Implementation Plan

## Current Issues
1. `sh: line 1: pip: command not found` - Python environment not properly initialized
2. Warning about `builds` in configuration overriding project settings
3. Database migrations failing to run during deployment
4. Environment variables not properly accessible during build

## Solution Strategy

### 1. Project Configuration
- **Keep** a minimal `vercel.json` so Vercel always selects the Python builder and we avoid the "builds overriding project settings" warning.
  ```json
  {
    "builds": [
      { "src": "app.py", "use": "@vercel/python", "config": { "buildCommand": "./build.sh" } }
    ],
    "routes": [
      { "src": "/(.*)", "dest": "app.py" }
    ]
  }
  ```
- In the Vercel dashboard set **Framework Preset** to "Other" (builder already handled by the file).
- Leave the **Install Command** field **blank** – `build.sh` will handle dependency installation.
- Set **Build Command** to `./build.sh` (redundant but harmless; Vercel will run it from the builder config).

### 2. Python Environment Setup
- Rely on Vercel's default Python 3.12 runtime (no `runtime.txt` or `.python-version` needed).
- Ensure `requirements.txt` has pinned or caret-pinned versions as currently committed.

### 3. Build Process (build.sh)
Update `build.sh` (snippet shown only for additions):
```bash
#!/bin/bash
set -e
# ... existing debug lines ...

# Verify environment variables
required_vars=(
  "DATABASE_URL" "SUPABASE_URL" "SUPABASE_KEY" "FLASK_ENV" \
  "OPENAI_API_KEY"
)
# ... existing loop ...
```
- **Only** `build.sh` installs requirements; dashboard Install Command remains blank to avoid double install.

### 4. Development/Production Configuration
Update `app.py` to handle database configuration more robustly:
```python
# Database configuration
ENVIRONMENT = os.getenv('FLASK_ENV', 'development')
if ENVIRONMENT == 'production':
    # Verify all required environment variables
    required_vars = ['SUPABASE_URL', 'SUPABASE_KEY', 'DATABASE_URL']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    try:
        # Initialize Supabase client
        supabase: Client = create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_KEY')
        )
        # Configure SQLAlchemy
        app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
        logging.info("Successfully configured Supabase connection")
    except Exception as e:
        logging.error(f"Failed to initialize Supabase: {str(e)}")
        raise
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/restaurant_recommendations.db'
    logging.info("Using SQLite database for development")
```

### 5. Implementation Steps

1. **Cleanup**:
   ```bash
   # Remove legacy files
   rm -f runtime.txt              # not needed anymore
   # If an old vercel.json existed, replace it with the minimal version above
   ```

2. **Create/Update Files**:
   - Overwrite `vercel.json` with the minimal content above
   - Update `build.sh` with extended env-var checks and ensure it has `chmod +x build.sh`

3. **Vercel Dashboard Configuration**:
   - Framework Preset → "Other"
   - Build Command → `./build.sh`
   - Install Command → (leave blank)
   - Output Directory → `./` (default)
   - Ensure Environment Variables:
     - `FLASK_ENV=production`
     - `DATABASE_URL`
     - `SUPABASE_URL`
     - `SUPABASE_KEY`
     - `OPENAI_API_KEY`

4. **Testing**:
   - Test build script locally:
     ```bash
     export FLASK_ENV=production
     export DATABASE_URL="your_supabase_url"
     export SUPABASE_URL="your_supabase_url"
     export SUPABASE_KEY="your_supabase_key"
     ./build.sh
     ```
   - Verify migrations run successfully
   - Check application starts locally

5. **Deployment**:
   - Push changes to GitHub
   - Monitor Vercel build logs for each step
   - Verify environment variables in Vercel dashboard
   - Test deployed application endpoints

### 6. Rollback Plan
If deployment fails:
1. Revert to last working commit
2. Restore previous Vercel configuration
3. Document specific failure point for further investigation

## Success Criteria
- Build completes successfully
- No warnings in Vercel deployment logs
- Migrations run successfully
- Application responds to requests
- Database queries work in production

## Monitoring
- Watch build logs for Python version confirmation
- Verify environment variables are accessible
- Monitor database migration success
- Check application logs for connection errors

## Key Learnings & Troubleshooting

### Vercel Build Configuration Precedence

A critical issue encountered during this deployment was a conflict between the `vercel.json` file and the settings in the Vercel Dashboard UI.

- **The Problem**: If a `builds` property exists in `vercel.json`, Vercel **completely ignores** the "Build & Development Settings" configured in the Project Settings UI. This means our `./build.sh` script was not being executed, causing silent failures where dependencies were not installed and database migrations did not run.
- **The Solution**: For a Python project where we need a custom build script, the most reliable configuration is to **remove the `builds` object from `vercel.json` entirely**. This forces Vercel to respect the settings configured in the UI, ensuring our `Build Command` (`./build.sh`) and `Install Command` (left blank) are correctly used. 