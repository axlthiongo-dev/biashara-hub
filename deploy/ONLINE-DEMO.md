# Put the demo fully online

The website is already published at https://axlthiongo-dev.github.io/biashara-hub/. GitHub Pages hosts the frontend; the API and PostgreSQL database run on Render.

## Deploy the API

1. Sign in to Render and choose **New > Blueprint**.
2. Connect the GitHub account that owns `axlthiongo-dev/biashara-hub` and select that repository.
3. Render reads the root `render.yaml`. Review the API service and PostgreSQL database, then deploy the Blueprint.
4. Set the prompted `INITIAL_ADMIN_EMAIL` and `INITIAL_ADMIN_PASSWORD`. Use a real email you control and a unique password with at least 12 characters; keep the password private.
5. Wait until the `biashara-hub-api` service is live. Open its `https://...onrender.com/health` URL and confirm it returns `{"status":"ok","version":"1.0.0"}`. Copy the service's base URL without `/health`.

## Connect the website to the API

1. Open the GitHub repository's **Settings > Secrets and variables > Actions > Variables**.
2. Add a repository variable named `VITE_API_BASE_URL` with the API base URL copied above, for example `https://biashara-hub-api.onrender.com` (no trailing slash).
3. Open **Actions**, select **Deploy web app to GitHub Pages**, and choose **Run workflow** on `main`.
4. When the Pages workflow succeeds, reload the public site and try the customer/business registration flow. Use the admin email and password from the Render deployment to sign in to the admin page.

No Daraja keys are included. M-Pesa checkout needs Safaricom Daraja sandbox credentials and an HTTPS callback URL configured on the API first. The rest of the demo, including accounts, vendor approval, products, and orders, can run without payment credentials.

## Free demo limits

Render's free API service can sleep after 15 minutes without traffic, so the first request after a quiet period may take about a minute. The free PostgreSQL database expires after 30 days and is intended for testing, not production. See [Render's free instance limitations](https://render.com/docs/free).
