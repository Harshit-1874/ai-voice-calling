# 🚀 Render Deployment Guide for AI Voice Calling Backend

## Why Render?
- **Free tier**: Perfect for your Python FastAPI backend
- **Zero configuration**: Works out of the box with Python
- **Automatic deploys**: Connects to GitHub for CI/CD
- **Built-in database**: Free PostgreSQL database included
- **Environment variables**: Easy management in dashboard

## 📋 Prerequisites

1. **GitHub Repository**: Your code should be pushed to GitHub
2. **Render Account**: Sign up at [render.com](https://render.com) (free)
3. **Environment Variables**: You'll need all your API keys ready

## 🛠️ Step-by-Step Deployment

### Step 1: Prepare Your Database

#### Option A: Use Render's Free PostgreSQL (Recommended)
1. Go to Render Dashboard
2. Click "New" → "PostgreSQL" 
3. Choose the free plan
4. Note down the connection string (Internal Database URL)

#### Option B: Use Supabase (Your current setup)
- Keep your existing `SUPABASE_URL` from your `.env` file

### Step 2: Deploy to Render

1. **Connect GitHub**:
   - Go to [render.com](https://render.com)
   - Click "New" → "Web Service"
   - Connect your GitHub account
   - Select your `ai-voice-calling` repository

2. **Configure Service**:
   ```
   Name: ai-voice-calling-backend
   Region: Choose closest to your users
   Branch: main
   Root Directory: (leave empty)
   Runtime: Python 3
   Build Command: pip install -r backend/requirements.txt && cd backend && prisma generate
   Start Command: cd backend && python main.py
   ```

3. **Set Environment Variables**:
   Go to Environment tab and add these variables:

   **Required Variables:**
   ```
   PORT=10000
   HOST=0.0.0.0
   DEBUG=false
   
   # Database
   SUPABASE_URL=your_database_url_here
   
   # Twilio
   TWILIO_ACCOUNT_SID=your_account_sid
   TWILIO_AUTH_TOKEN=your_auth_token
   TWILIO_PHONE_NUMBER=your_phone_number
   
   # OpenAI
   OPENAI_API_KEY=your_api_key
   
   # HubSpot (if using)
   HUBSPOT_ACCESS_TOKEN=your_token
   
   # Redis (optional)
   REDIS_HOST_URI=your_redis_url
   REDIS_PASS=your_redis_password
   
   # Base URL (update after deployment)
   BASE_URL=https://your-app-name.onrender.com
   ```

4. **Deploy**:
   - Click "Create Web Service"
   - Wait for deployment (usually 5-10 minutes)
   - Your app will be available at `https://your-app-name.onrender.com`

### Step 3: Update Your Frontend

Update your frontend API base URL to point to your new Render deployment:
```javascript
const API_BASE_URL = 'https://your-app-name.onrender.com'
```

## 🔧 Troubleshooting

### Common Issues:

1. **Build Fails**:
   - Check that `requirements.txt` is in the `backend/` folder
   - Ensure all dependencies are listed correctly

2. **Database Connection Issues**:
   - Verify your `SUPABASE_URL` is correct
   - Make sure the database is accessible from external connections

3. **Prisma Issues**:
   - Make sure `prisma generate` runs in build command
   - Check that schema.prisma is correctly configured

4. **Environment Variables**:
   - Double-check all required env vars are set
   - Sensitive values should not have quotes in Render dashboard

### Performance Tips:

1. **Free Tier Limitations**:
   - App sleeps after 15 minutes of inactivity
   - 750 hours/month (plenty for testing)
   - 0.5 GB RAM, 0.5 CPU

2. **Keep Alive** (Optional):
   - Use a service like UptimeRobot to ping your app every 5 minutes
   - Prevents sleeping during active hours

## 🎯 Alternative: Quick Railway Deployment

If Render doesn't work, try Railway.app:

1. Go to [railway.app](https://railway.app)
2. Connect GitHub
3. Deploy from repo
4. Add environment variables
5. Set start command: `cd backend && python main.py`

## 📝 Post-Deployment Checklist

- [ ] App deploys successfully
- [ ] Database connections work
- [ ] API endpoints respond correctly
- [ ] Twilio webhooks updated to new URL
- [ ] Frontend updated to use new backend URL
- [ ] Environment variables all set correctly

## 🚨 Security Notes

- Never commit `.env` files to GitHub
- Use Render's environment variables for sensitive data
- Set `DEBUG=false` in production
- Consider using HTTPS-only in production

Your app should work exactly like running `python main.py` locally, but now it's accessible worldwide! 🌍
