# Vercel Deployment Implementation Plan

## Evolution of Deployment Strategy

Our deployment strategy has evolved through several iterations, each teaching us important lessons about Vercel's Python deployment:

1. Initial Approach (with build.sh):
   - Used a build.sh script for dependency installation and migrations
   - Complex vercel.json with builds configuration
   - Migrations handled during build time

2. Current Simplified Approach:
   - Removed build.sh in favor of simpler configuration
   - Streamlined vercel.json
   - Migrations handled during application startup

## Current Configuration

### 1. vercel.json
The minimal but complete configuration:
```json
{
  "version": 2,
  "builds": [
    {
      "src": "app.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "app.py"
    }
  ]
}
```

### 2. Application Configuration (app.py)
Key components:
```python
# Initialize Flask app with writable instance path for Vercel
app = Flask(__name__, instance_path='/tmp/instance')

# Configure database based on environment
ENVIRONMENT = os.getenv('FLASK_ENV', 'development')
if ENVIRONMENT == 'production':
    # Use POSTGRES_URL from Vercel integration, fallback to DATABASE_URL
    DATABASE_URL = os.getenv('POSTGRES_URL') or os.getenv('DATABASE_URL')
    
    # Run migrations during app startup in production
    try:
        logging.info("Running database migrations...")
        from flask_migrate import upgrade
        with app.app_context():
            upgrade()
        logging.info("Database migrations completed successfully")
    except Exception as e:
        logging.error(f"Database migration failed: {str(e)}")
        # Don't raise here - let the app start even if migrations fail
```

## Required Environment Variables

1. Database Configuration:
   - `POSTGRES_URL` (primary) or `DATABASE_URL` (fallback)
   - Set automatically by Vercel-Supabase integration

2. Supabase Configuration:
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - Set automatically by Vercel-Supabase integration

3. Application Configuration:
   - `FLASK_ENV=production`
   - `OPENAI_API_KEY`
   - Must be manually set in Vercel dashboard

## Deployment Steps

1. **Vercel Dashboard Configuration**:
   - Framework Preset → "Other"
   - Build Command → (leave blank)
   - Install Command → (leave blank)
   - Output Directory → `./` (default)

2. **Environment Variables**:
   - Verify all required variables are set in both Production and Preview environments
   - Double-check Supabase integration variables are properly set

3. **Deployment**:
   - Push changes to GitHub
   - Monitor Vercel build logs
   - Verify application starts correctly
   - Test deployed endpoints

## Troubleshooting Guide

### Common Issues and Solutions

1. **Application Downloads Instead of Running**:
   - Verify vercel.json has proper version and builds configuration
   - Check that @vercel/python builder is specified
   - Ensure app.py is properly configured for WSGI

2. **Database Connection Issues**:
   - Verify Supabase integration in Vercel marketplace
   - Check both POSTGRES_URL and DATABASE_URL are set
   - Ensure using transaction pooler URL for Supabase

3. **Migration Failures**:
   - Check migration logs in application startup
   - Verify database URL is correct
   - Ensure all migrations are committed to repository

### Key Learnings

1. **Simplified Configuration is Better**:
   - Removed build.sh in favor of built-in Vercel Python handling
   - Migrations during app startup are more reliable than build-time
   - Minimal vercel.json configuration reduces conflicts

2. **Environment Variable Management**:
   - Prefer Vercel integrations for automatic variable setup
   - Use fallbacks for different variable names (e.g., POSTGRES_URL → DATABASE_URL)
   - Always verify variables in both Production and Preview environments

3. **Vercel-Specific Best Practices**:
   - Use /tmp for writable paths
   - Handle migrations gracefully during startup
   - Keep configuration in vercel.json minimal but complete

## Success Criteria
- Application serves properly (not downloading files)
- Database migrations run successfully during startup
- All routes respond correctly
- Database queries work in production
- Environment variables are properly accessible

## Monitoring
- Watch application startup logs for migration success
- Monitor database connection status
- Check for any file permission issues in /tmp
- Verify environment variables are loaded correctly

## Rollback Plan
If deployment fails:
1. Revert to last working commit
2. Verify vercel.json configuration
3. Check environment variables
4. Review application logs for specific failure points 