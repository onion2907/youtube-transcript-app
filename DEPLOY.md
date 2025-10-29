# Deploy to Railway (Free Hosting)

This guide will help you deploy your YouTube Transcript App to Railway's free tier.

## What is Railway?
Railway is a cloud platform that lets you deploy apps without complex setup. It has a generous free tier perfect for personal projects.

## Step-by-Step Deployment

### 1. Create a GitHub Account (if you don't have one)
- Go to [github.com](https://github.com) and sign up
- It's free and takes 2 minutes

### 2. Upload Your Code to GitHub
1. Go to [github.com/new](https://github.com/new)
2. Name your repository: `youtube-transcript-app`
3. Make it **Public** (required for free Railway)
4. Click "Create repository"

5. Upload your files:
   - Click "uploading an existing file"
   - Drag and drop all files from your `/Users/ajinkyaganoje/utran` folder:
     - `app.py`
     - `requirements.txt`
     - `Procfile`
     - `runtime.txt`
     - `railway.json`
     - `static/` folder (with `index.html`, `style.css`, `app.js`)
     - `README.md`
   - Add commit message: "Initial commit"
   - Click "Commit changes"

### 3. Deploy to Railway
1. Go to [railway.app](https://railway.app)
2. Click "Login" and sign in with GitHub
3. Click "New Project"
4. Select "Deploy from GitHub repo"
5. Choose your `youtube-transcript-app` repository
6. Click "Deploy Now"

### 4. Optional: Enable Browserless (recommended)

Create a free Browserless account and get an API token. In Railway → Variables, add:

- `BROWSERLESS_TOKEN` = your token

The app will use Browserless to drive Playwright remotely when you click "Open in Tactiq". If not set, it will try local Playwright or open Tactiq in a new tab.

### 5. Wait for Deployment
- Railway will automatically:
  - Install Python 3.11
  - Install all dependencies from `requirements.txt`
  - Install Playwright Chromium (via nixpacks plan)
  - Start your app
- This takes 2-4 minutes on first deploy

### 6. Get Your App URL
1. Once deployed, click on your project
2. Go to "Settings" tab
3. Find "Domains" section
4. Copy your app URL (looks like: `https://youtube-transcript-app-production-xxxx.up.railway.app`)

### 6. Test Your App
1. Open the URL in your browser
2. Paste a YouTube URL and test it!
3. Try the "Share" button on your phone

## Configuration (Optional)

To change the AI model or settings:

1. In Railway dashboard, go to your project
2. Click "Variables" tab
3. Add these environment variables:
   - `MODEL_NAME` = `tiny` (faster) or `base` (better quality)
   - `WHISPER_DEVICE` = `cpu` (for free tier)
   - `WHISPER_COMPUTE` = `int8` (uses less memory)

## Free Tier Limits

- **500 hours/month** of runtime (plenty for personal use)
- **1GB RAM** (enough for `tiny` or `base` models)
- **1GB storage** (for cache and models)
- **Automatic sleep** after 5 minutes of inactivity (wakes up when accessed)

## Troubleshooting

**App won't start?**
- Check Railway logs in the "Deployments" tab
- Make sure all files were uploaded to GitHub

**Slow first request?**
- Normal! The app downloads the AI model on first use
- Subsequent requests are much faster

**Out of memory?**
- Change `MODEL_NAME` to `tiny` in Variables
- Restart the deployment

**Need help?**
- Railway has great documentation: [docs.railway.app](https://docs.railway.app)
- Or ask in their Discord community

## Updating Your App

To make changes:
1. Edit files locally
2. Upload changes to GitHub
3. Railway automatically redeploys

## Cost

- **Free tier**: 500 hours/month, 1GB RAM, 1GB storage
- **Paid plans**: Start at $5/month if you need more resources
- **No credit card required** for free tier

Your app will be live at a URL like: `https://youtube-transcript-app-production-xxxx.up.railway.app`
