## Project Deployment

Run the following shell commands to deploy the project:

```shell
dr run infra:up-yes
```

In case the deployment process fails, you can try deleting it by running the following command:

```shell
dr run infra:down-yes
```

## Local Development

One-time setup (deploys backing infrastructure):

```shell
dr start
```

## Pre-deploy Checklist

Before running `dr run infra:up-yes`, ask the user to ensure their environment is configured. The following variables must be set:

- `DATAROBOT_API_TOKEN` and `DATAROBOT_ENDPOINT`
- `PULUMI_CONFIG_PASSPHRASE`
- `SESSION_SECRET_KEY` (required if using the FastAPI component)
- `DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT` (required if your agent uses a custom execution environment)

If the user hasn't set up their environment yet, ask them to run:

```shell
dr start
```

or

```shell
dr dotenv setup
```

## Troubleshooting

**Deploy exits with code 1 but a Custom Application URL appears in the output**
The app is live — the non-zero exit came from a post-deploy cleanup step, not the app itself. Run the following to reconcile Pulumi state:

```shell
dr run infra:refresh -- -y
```

Do not re-deploy.

**422 error when deleting ApplicationSource**
The source is still attached to a live application. Reconcile Pulumi state and retry:

```shell
dr run infra:refresh -- -y
```

**Docker context error on first deploy**
Set `DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT` in your `.env` file to point to an existing execution environment.

**Container fails to install dependencies at startup**
If your app depends on a local package (e.g. `core/`), ensure it is included in the application bundle before deploying.

**Pulumi commands fail/hang with GitHub rate-limit errors**
`pulumi-datarobot` is a GitHub-distributed plugin, so Pulumi resolves and update-checks it via `api.github.com` (60 req/hour anonymous limit) by default. `dr dependency install`/`dr start` already install it through a direct release-download URL to dodge this. If it's still hit, set `PULUMI_SKIP_UPDATE_CHECK=1` so Pulumi stops re-checking `api.github.com` on every invocation.

If the failing download is for an **old** version (a pre-existing stack's resources can be pinned to whatever `pulumi-datarobot` provider version was current when they were deployed — check `pulumi stack export` for `pulumi:providers:datarobot`), that version is still fetched via the same rate-limited GitHub API path regardless of the env var, since this template doesn't pin an explicit provider version in code. Install it manually the same rate-limit-safe way, using the version named in the error:

```sh
pulumi plugin install resource datarobot <VERSION> --server https://github.com/datarobot-community/pulumi-datarobot/releases/download/v<VERSION>
```

## Expected Deploy Times

| Operation | Duration |
|---|---|
| First deploy | ~10–15 min |
| Re-deploy | ~5–10 min |
| `task refresh` | ~1–2 min |
