# 🔐 Setting Up Google OAuth2 Credentials for Your Agent
This guide walks you through the steps to create a Google Cloud Project and configure OAuth 2.0 credentials to integrate with services like Google Drive.

## ✅ 1. Create a Project in Google Developer Console

1. Go to the [Google Developer Console](https://console.developers.google.com/).
2. In the top navigation bar, click on “Create Project”.
3. Enter a Project Name.
4. Choose an Organization or leave as “No organization” if not applicable.
5. Click Create.

Your new project will appear in the project list.

## 📦 2. Enable Google Calendar API

1. With your project selected, open the left-hand menu and go to APIs & Services > Library.
2. In the search bar, type Google Calendar API.
3. Click on Google Calendar API from the results.
4. Click Enable.

## 🛡️ 3. Configure OAuth Consent Screen

1. In the left-hand menu, go to APIs & Services > OAuth consent screen.

2. Click “Get started”.

3. Fill in the required fields: App Name, and User Support Email
4. Click Next, then: Select the User Type (Internal or External). If selecting External, add the tester email addresses. Provide Developer Contact Information (your email).
5. Accept terms and click Finish.
6. Click Create to finalize the consent screen.

## 🔧 4. Create OAuth 2.0 Credentials

1. Navigate to APIs & Services > Credentials from the left-hand menu.
2. Click Create Credentials > OAuth client ID.
3. Choose Web application as the application type.
4. Enter a name for the credentials.
5. Under Authorized redirect URIs, add your following redirect URI:
   - `https://bedrock-agentcore.us-east-1.amazonaws.com/identities/oauth2/callback`
6. Click Create.

## 🔑 5. Obtain Client ID and Client Secret

After creation, a dialog will display your Client ID and Client Secret. Download JSON to save the credentials to a file. Save this file to your project in `credentials.json`.

## 🔍 6. Update the Data Access Scopes

1. Go to APIs & Services > Credentials.
2. Click on the OAuth 2.0 client ID you created.
3. In the left-hand menu, select Data access.
4. Click “Add or remove scopes”.
5. Under Manually add scopes, enter scope: `https://www.googleapis.com/auth/calendar`
6. Click Update, then click Save to confirm the configuration.
