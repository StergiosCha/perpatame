# PostgreSQL Setup on Render

## ✅ SOLUTION: Use PostgreSQL for Persistent Storage

The app now supports both SQLite (local) and PostgreSQL (Render). 

## Steps to Set Up PostgreSQL on Render:

1. **Create PostgreSQL Database on Render:**
   - Go to Render Dashboard
   - Click "New +" → "PostgreSQL"
   - Choose a name (e.g., "perpatame-db")
   - Select region
   - Click "Create Database"

2. **Get Connection String:**
   - In your PostgreSQL database dashboard
   - Copy the "Internal Database URL" or "External Database URL"
   - It looks like: `postgresql://user:password@host:port/dbname`

3. **Add to Render Web Service:**
   - Go to your Web Service settings
   - Go to "Environment" tab
   - Add environment variable:
     - Key: `DATABASE_URL`
     - Value: Paste the PostgreSQL connection string

4. **Redeploy:**
   - The app will automatically detect `DATABASE_URL` and use PostgreSQL
   - Database will persist across redeploys!

## How It Works:

- **Without `DATABASE_URL`**: Uses SQLite (local development, ephemeral on Render)
- **With `DATABASE_URL`**: Uses PostgreSQL (persistent on Render)

## Migration:

The app automatically creates tables on startup. Your existing SQLite data won't transfer automatically, but:
- New submissions will go to PostgreSQL
- Old SQLite data is lost (already happened)

## Testing Locally:

To test PostgreSQL locally:
```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/dbname"
uvicorn backend.main:app --reload
```

