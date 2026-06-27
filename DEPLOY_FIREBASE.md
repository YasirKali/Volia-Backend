# Deploy Volia Backend on Firebase/Google Cloud

This backend is a FastAPI app that downloads media, runs `yt-dlp`/`spotdl`, uses `ffmpeg`, streams progress, and serves temporary files. The best Firebase-compatible deployment target is Cloud Run, with Firebase Hosting rewrites optional.

Your Firebase project id from the web config is:

```text
volia-753e3
```

## 1. Deploy the backend to Cloud Run

Cloud Run deployment requires the Firebase project to be upgraded from Spark to Blaze with billing enabled. Spark cannot enable the required Google Cloud services for this backend (`run.googleapis.com`, `cloudbuild.googleapis.com`, and `artifactregistry.googleapis.com`). If service activation fails with `UREQ_PROJECT_BILLING_NOT_FOUND`, attach a billing account to project `volia-753e3` in the Google Cloud Console first:

```text
https://console.cloud.google.com/billing/linkedaccount?project=volia-753e3
```

Run these commands from `volia-backend`:

```powershell
gcloud auth login
gcloud config set project volia-753e3
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
gcloud run deploy volia-backend --source . --region us-central1 --allow-unauthenticated
```

After deploy, Cloud Run prints a service URL such as:

```text
https://volia-backend-xxxxx-uc.a.run.app
```

Test it:

```powershell
Invoke-WebRequest -Uri https://YOUR-CLOUD-RUN-URL/health -UseBasicParsing
```

## 2. Connect Vercel frontend

In Vercel, set this environment variable for the frontend project:

```text
VITE_BACKEND_URL=https://YOUR-CLOUD-RUN-URL
```

Then redeploy the frontend.

## 3. Set CORS for production

Once you know the Vercel domain, set `ALLOWED_ORIGINS` on Cloud Run:

```powershell
gcloud run services update volia-backend --region us-central1 --set-env-vars ALLOWED_ORIGINS=https://YOUR-VERCEL-DOMAIN.vercel.app
```

Multiple origins can be comma-separated:

```text
https://yourdomain.com,https://your-project.vercel.app
```

For the current Vercel frontend, use:

```powershell
gcloud run services update volia-backend --region us-central1 --set-env-vars ALLOWED_ORIGINS=https://volia-ten.vercel.app
```

## Optional: Firebase Hosting rewrite

If you later want Firebase Hosting to proxy API traffic to Cloud Run, add this to a Firebase Hosting `firebase.json`:

```json
{
  "hosting": {
    "rewrites": [
      {
        "source": "/api/**",
        "run": {
          "serviceId": "volia-backend",
          "region": "us-central1",
          "pinTag": true
        }
      },
      {
        "source": "/health",
        "run": {
          "serviceId": "volia-backend",
          "region": "us-central1",
          "pinTag": true
        }
      }
    ]
  }
}
```

Then deploy Hosting config:

```powershell
firebase use volia-753e3
firebase deploy --only hosting
```

## Notes

- Do not commit or bake `cookies.txt` into the container image. It is ignored by `.dockerignore`.
- Browser cookie auto-detection only works on your local machine. In Cloud Run, use a safe server-side secret/cookie strategy if private-platform downloads require authentication.
- Downloads are stored in the container's temporary filesystem and removed after the file response is served.
