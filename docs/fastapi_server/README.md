# Agentic Starter: FastAPI (backend)

## Tech stack

- FastAPI

## API

- OpenAPI: http://localhost:8080/docs
- Redoc: http://localhost:8080/redoc

## Development

To start the development server:

```
uv run fastapi_server run --reload
```

To run tests:

```
uv run pytest --cov --cov-report term --cov-report html
```



## OAuth applications

The template can work with files stored in Google Drive and Box.
In order to give it access to those files, you need to configure OAuth Applications.

### Google OAuth application

- Go to [Google API Console](https://console.developers.google.com/) from your Google account
- Navigate to "APIs & Services" > "Enabled APIs & services" > "Enable APIs and services", search for Drive, and add it.
- Navigate to "APIs & Services" > "OAuth consent screen" and make sure you have your consent screen configured. You may have both "External" and "Internal" audience types.
- Navigate to "APIs & Services" > "Credentials" and click on the "Create Credentials" button. Select "OAuth client ID".
- Select "Web application" as Application type, fill in "Name" & "Authorized redirect URIs" fields. For example, for local development, the redirect URL will be:
  - `http://localhost:5173/oauth/callback` - local vite dev server (used by frontend developers)
  - `http://localhost:8080/oauth/callback` - web-proxied frontend
  - `http://localhost:8080/api/v1/oauth/callback/` - the local web API (optional).
  -  For production, you'll want to add your DataRobot callback URL. For example, in US Prod it is `https://app.datarobot.com/custom_applications/{appId}/oauth/callback`. For any installation of DataRobot it is `https://<datarobot-endpoint>/custom_applications/{appId}/oauth/callback`.
- Hit the "Create" button when you are done.
- Copy the "Client ID" and "Client Secret" values from the created OAuth client ID and set them in the template env variables as `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` respectively.
- Make sure you have the "Google Drive API" enabled in the "APIs & Services" > "Library" section. Otherwise, you will get 403 errors.
- Finally, go to "APIs & Services" > "OAuth consent screen" > "Data Access" and make sure you have the following scopes selected:
  - `openid`
  - `https://www.googleapis.com/auth/userinfo.email`
  - `https://www.googleapis.com/auth/userinfo.profile`
  - `https://www.googleapis.com/auth/drive.readonly`

### Box OAuth application

- Navigate to the [Box Developer Console](https://app.box.com/developers/console) from your Box account.
- Create a new platform application, then select the "Custom App" type.
- Fill in "Application Name" and select "Purpose" (e.g. "Integration"). Then, fill in three more info fields. The actual selection doesn't matter.
- Select "User Authentication (OAuth 2.0)" as Authentication Method and click on the "Create App" button.
- In the "OAuth 2.0 Redirect URIs" section, please fill in callback URLs you want to use:
  - `http://localhost:5173/oauth/callback` - local vite dev server (used by frontend developers)
  - `http://localhost:8080/oauth/callback` - web-proxied frontend
  - `http://localhost:8080/api/v1/oauth/callback/` - the local web API (optional).
  -  For production, you'll want to add your DataRobot callback URL. For example, in US Prod it is `https://app.datarobot.com/custom_applications/{appId}/oauth/callback`.
- Hit "Save Changes" after that.
- Under the "Application Scopes", please make sure you have both `Read all files and folders stored in Box` and "Write all files and folders stored in Box" checkboxes selected. We need both because we need to "write" to the log that we've downloaded the selected files.
- Finally, under the "OAuth 2.0 Credentials" section, you should be able to find your Client ID and Client Secret pair to setup in the template env variables as `BOX_CLIENT_ID` and `BOX_CLIENT_SECRET` respectively.

## Database configuration

By default, the application uses a SQLite async database that is only
suitable for development purposes. We recommend configuring it with a
production grade hosted database that supports SQLAlchemy's 2.0+ async
engine such as https://github.com/MagicStack/asyncpg.

## Memory Space chat persistence (optional)

By default, chats, messages, users, and identities are stored in the SQLite database described above. To use a DataRobot Memory Space instead:

1. Ensure your organization has agentic memory API access (`ENABLE_AGENTIC_MEMORY_API`).
2. Set `USE_APPLICATION_MEMORY_SPACE=true` in your project `.env` (see `.env.template`).
3. Run `task deploy-dev`. Pulumi provisions a Memory Space and wires `USE_APPLICATION_MEMORY_SPACE` and `APPLICATION_MEMORY_SPACE_ID` on the **FastAPI custom application** runtime (not the agent deployment).

If you change `USE_APPLICATION_MEMORY_SPACE` later, rerun `task deploy-dev` before `task dev` so infrastructure and runtime parameters stay in sync with your `.env`.

When enabled, the backend uses `X-DataRobot-User-Id` as the memory-service participant id when that header is present (the user's DataRobot ObjectId). Otherwise it maps each app user to a stable 24-character hex participant id derived from the app user UUID. Assistant messages use a separate stable app-agent participant id.

OAuth identities (provider connections and tokens) and user profiles are also stored in the same Memory Space as metadata documents keyed by indexed session descriptions (for example `/user/email/{email}` for users and `/user/{user_id}/identity/{provider_type}` for identities). When `USE_APPLICATION_MEMORY_SPACE` is enabled, the FastAPI backend does not persist application data in SQLite.

See commented examples in the project root `.env.template`.
