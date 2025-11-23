# Database Persistence on Render

## ⚠️ CRITICAL: Render's filesystem is EPHEMERAL

**The database file (`stories.db`) gets DELETED on every redeploy.**

## Solutions:

### Option 1: Use Render PostgreSQL (RECOMMENDED)
1. Create a PostgreSQL database on Render
2. Get the connection string from Render dashboard
3. Update `backend/main.py` to use PostgreSQL instead of SQLite
4. Database will persist across redeploys

### Option 2: Automatic Backups
- The app now creates backups every 6 hours
- Download backups via: `GET /api/backup`
- **BUT**: Backups are also on ephemeral filesystem, so download them regularly!

### Option 3: External Storage
- Upload backups to S3/Google Cloud Storage
- Or use a persistent disk volume (if available on your Render plan)

## Immediate Actions:

1. **Download current database**: Visit `https://your-app.onrender.com/api/backup`
2. **Export all stories**: Visit `https://your-app.onrender.com/api/stories/export`
3. **Set up PostgreSQL** before next event to prevent data loss

## Migration to PostgreSQL:

1. Install: `pip install psycopg2-binary`
2. Add to requirements.txt
3. Update `get_db()` to use PostgreSQL connection
4. Run migrations to create tables

