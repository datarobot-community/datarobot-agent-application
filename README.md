<p align="center">
  <a href="https://github.com/datarobot-community/datarobot-agent-application">
    <img src="./.github/datarobot_logo.avif" width="600px" alt="DataRobot Logo"/>
  </a>
</p>
<p align="center">
    <span style="font-size: 1.5em; font-weight: bold; display: block;">DataRobot Agentic Workflow Application Template</span>
</p>

<p align="center">
  <a href="https://datarobot.com">Homepage</a>
  ·
  <a href="https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/index.html">Documentation</a>
  ·
  <a href="https://docs.datarobot.com/en/docs/get-started/troubleshooting/general-help.html">Support</a>
</p>

<p align="center">
  <a href="https://github.com/datarobot-community/datarobot-agent-application/tags">
    <img src="https://img.shields.io/github/v/tag/datarobot-community/datarobot-agent-application?label=version" alt="Latest Release">
  </a>
  <a href="/LICENSE">
    <img src="https://img.shields.io/github/license/datarobot-community/datarobot-agent-application" alt="License">
  </a>
</p>

This repository provides a ready-to-use application template for building and deploying agentic workflows with multi-agent frameworks, a FastAPI backend server, a React frontend, and an MCP server.
The template streamlines the process of setting up new agentic applications with minimal configuration requirements.
It supports local development and testing, as well as one-command deployments to production environments within DataRobot.

> [!CAUTION]
> This repository updates frequently.
> Make sure to update your local branch regularly to obtain the latest changes.

# Table of contents

- [Installation](#installation)
- [Run your agent](#run-your-agent)
- [Develop your agent](#develop-your-agent)
- [Deploy your agent](#deploy-your-agent)
- [Get help](#get-help)

# Installation

> [!CAUTION]
> This repository is only compatible with macOS and Linux operating systems.
> If you are using Windows, consider using a [DataRobot codespace](https://docs.datarobot.com/en/docs/workbench/wb-notebook/codespaces/index.html), [Windows Subsystem for Linux (WSL)](https://learn.microsoft.com/en-us/windows/wsl/install), or a virtual machine running a supported OS.

## Prerequisite tools

The following tools are required to install and run the agent application template.
Ensure that you have the following tools installed and on your system at the required version (or newer).
It is **recommended you install the tools system-wide** rather than in a virtual environment to ensure they are available in your terminal sessions.

For detailed installation steps, see [Installation instructions](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/agentic-install.html#installation-instructions) in the DataRobot documentation.

| Tool         | Version    | Description                     | Installation guide            |
|--------------|------------|---------------------------------|-------------------------------|
| **dr-cli**   | >= 0.2.12  | The DataRobot CLI.              | [dr-cli installation guide](https://github.com/datarobot-oss/cli?tab=readme-ov-file#installation) |
| **git**      | >= 2.30.0  | A version control system.       | [git installation guide](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git) |
| **uv**       | >= 0.6.10  | A Python package manager.       | [uv installation guide](https://docs.astral.sh/uv/getting-started/installation/)                  |
| **Pulumi**   | >= 3.163.0 | An Infrastructure as Code tool. | [Pulumi installation guide](https://www.pulumi.com/docs/iac/download-install/)              |
| **Taskfile** | >= 3.43.3  | A task runner.                  | [Taskfile installation guide](https://taskfile.dev/docs/installation)                   |
| **NodeJS**   | >= 24      | JavaScript runtime for frontend development. | [NodeJS installation guide](https://nodejs.org/en/download/)                      |

> [!IMPORTANT]
> You will also need a compatible C++ compiler and build tools installed on your system to compile some Python packages.

<details><summary><b>Click here for details on using a development container</b></summary>

### Development container (experimental)

[devcontainers](https://containers.dev/) enable you to use a container environment for local development. They are integrated with
[modern IDEs](https://containers.dev/supporting) such as VSCode and PyCharm, and the [Dev Container CLI](https://containers.dev/supporting#devcontainer-cli) allows you to integrate them with terminal-centric development workflows.

> [!TIP]
> This can also be used as a solution for Windows development.

> [!NOTE]
> [Docker Desktop](https://docs.docker.com/desktop/) is the recommended backend for running devcontainers, but any Docker-compatible backend is supported.

This template offers a `devcontainer` with all prerequisites installed.
To start working in it, simply open the template in PyCharm (version >= 2023.2, Pro) or VSCode, and the IDE will prompt you to reopen it in a container.

<details><summary><b>☂️ Click here to see example screenshots</b></summary>
*PyCharm*:

<img src="docs/img/pycharm-devcontainer.png" alt="Open in Dev Container PyCharm" width="350px" />

*VSCode*:

<img src="docs/img/vscode-devcontainer.png" alt="Open in Dev Container VSCode" width="350px" />
</details>

Click **Reopen in Container** to reopen the project in the container.
Then, if you work directly in the terminal, run:

```shell
devcontainer up --workspace-folder .
devcontainer exec --workspace-folder . /bin/sh
```

## Prepare application

> [!CAUTION]
> Ensure that all prerequisites are installed before proceeding.

As the final step, run `dr start` to prepare your local development environment. An interactive wizard will guide you through the selection of configuration options.

</details>

<details><summary><b>☂️ Configuration options explained</b></summary>

## LLM configuration

Agentic Application supports multiple flexible LLM options including:

- LLM Blueprint with LLM Gateway (default)
- LLM Blueprint with an External LLM
- Already Deployed Text Generation model in DataRobot

### LLM configuration recommended option

You can edit the LLM configuration by manually changing which configuration is active.
Simply run:

```sh
ln -sf ../configurations/<chosen_configuration> infra/infra/llm.py
```

After doing so, you'll likely want to edit the `llm.py` file to select the correct model, particularly for non-LLM Gateway options.

### LLM configuration alternative option

If you want to configure it dynamically, you can set it as a configuration value in your `.env` file:

```sh
INFRA_ENABLE_LLM=<chosen_configuration>
```

Choose from the available options in the `infra/configurations/llm` folder.

Here are some examples of each configuration using the dynamic option described above:

#### LLM blueprint with LLM Gateway (default)

The default option is **LLM Gateway**, if not specified in your `.env` file.

```sh
INFRA_ENABLE_LLM=blueprint_with_llm_gateway.py
```

#### Existing LLM deployment in DataRobot

Uncomment and configure these in your `.env` file:

```sh
TEXTGEN_DEPLOYMENT_ID=<your_deployment_id>
INFRA_ENABLE_LLM=deployed_llm.py
```

#### External LLM provider

Configure an LLM with an external LLM provider like Azure, Bedrock, Anthropic, or VertexAI. Here's an Azure AI example:

```sh
INFRA_ENABLE_LLM=blueprint_with_external_llm.py
LLM_DEFAULT_MODEL="azure/gpt-4o"
OPENAI_API_VERSION='2024-08-01-preview'
OPENAI_API_BASE='https://<your_custom_endpoint>.openai.azure.com'
OPENAI_API_DEPLOYMENT_ID='<your deployment_id>'
OPENAI_API_KEY='<your_api_key>'
```

See the [DataRobot documentation](https://docs.datarobot.com/en/docs/gen-ai/playground-tools/deploy-llm.html) for details on other providers.

In addition to the `.env` file changes, you can also edit the respective `llm.py` file to make additional changes, such as the default LLM, temperature, top_p, etc., within the chosen configuration.

## OAuth applications

The template can work with files stored in Google Drive and Box.
To enable access to those files, you need to configure OAuth applications.

### Google OAuth application

- Go to the [Google API Console](https://console.developers.google.com/) from your Google account.
- Navigate to "APIs & Services" > "Enabled APIs & services" > "Enable APIs and services", search for Drive, and add it.
- Navigate to "APIs & Services" > "OAuth consent screen" and ensure your consent screen is configured. You may have both "External" and "Internal" audience types.
- Navigate to "APIs & Services" > "Credentials" and click the "Create Credentials" button. Select "OAuth client ID".
- Select "Web application" as the application type, and fill in the "Name" and "Authorized redirect URIs" fields. For local development, use these redirect URLs:
  - `http://localhost:5173/oauth/callback` - local Vite dev server (used by frontend developers)
  - `http://localhost:8080/oauth/callback` - web-proxied frontend
  - `http://localhost:8080/api/v1/oauth/callback/` - the local web API (optional)
  - For production, add your DataRobot callback URL. For example, in US Prod it is `https://app.datarobot.com/custom_applications/{appId}/oauth/callback`. For any DataRobot installation, it is `https://<datarobot-endpoint>/custom_applications/{appId}/oauth/callback`.
- Click the **Create** button when you are done.
- Copy the **Client ID** and **Client Secret** values from the created OAuth client ID and set them in your `.env` file as `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`, respectively.
- Make sure you have the "Google Drive API" enabled in the "APIs & Services" > "Library" section. Otherwise, you will get 403 errors.
- Finally, go to "APIs & Services" > "OAuth consent screen" > "Data Access" and make sure you have the following scopes selected:
  - `openid`
  - `https://www.googleapis.com/auth/userinfo.email`
  - `https://www.googleapis.com/auth/userinfo.profile`
  - `https://www.googleapis.com/auth/drive.readonly`

### Box OAuth application

- Go to the [Box Developer Console](https://app.box.com/developers/console) from your Box account.
- Create a new platform application, then select "Custom App" type.
- Fill in the "Application Name" and select "Purpose" (e.g., "Integration"). Then, fill in three more info fields. The actual selections don't matter.
- Select "User Authentication (OAuth 2.0)" as the authentication method and click the "Create App" button.
- In the "OAuth 2.0 Redirect URIs" section, add the callback URLs you want to use:
  - `http://localhost:5173/oauth/callback` - local Vite dev server (used by frontend developers)
  - `http://localhost:8080/oauth/callback` - web-proxied frontend
  - `http://localhost:8080/api/v1/oauth/callback/` - the local web API (optional)
  - For production, add your DataRobot callback URL. For example, in US Prod it is `https://app.datarobot.com/custom_applications/{appId}/oauth/callback`.
- Click "Save Changes" after that.
- Under "Application Scopes", ensure you have both "Read all files and folders stored in Box" and "Write all files and folders stored in Box" checkboxes selected. Both are needed because the application writes to the log when it downloads selected files.
- Finally, under the "OAuth 2.0 Credentials" section, find your Client ID and Client Secret pair and set them in your `.env` file as `BOX_CLIENT_ID` and `BOX_CLIENT_SECRET`, respectively.

After you've set these values in your project `.env` file, the next `pulumi up` will create OAuth providers in your DataRobot installation. To view, manage, and verify they are working, navigate to `<your_datarobot_url>/account/oauth-providers` or in US production: https://app.datarobot.com/account/oauth-providers.

Additionally, the Pulumi output variables are used to populate those providers for your Codespace and local development environment as well.

</details>

# Run your agent

This section walks you through running your agent application locally.
Choose the option that best fits your development workflow.

## Build your agent application

The first step is to build the frontend once and run it as a static build, while the backend components use autoreload.

1. Build the frontend:

```shell
dr task run frontend_web:build
```

1. In a new terminal window or tab, start the MCP server:

```shell
dr task run mcp_server:dev
```

3. In a third terminal window or tab, start the application:

```shell
dr task run web:dev
```

4. In a fourth terminal window or tab, start the writer agent:

```shell
dr task run writer_agent:dev
```

5. Open your browser and navigate to http://localhost:8080.

<details><summary><b>Click here to view other build and run options</b></summary>

## Option 2: Autoreload for all components

This option enables autoreload for all components, including the frontend, which is useful during active frontend development.

1. Start the frontend in development mode (instead of building it):

```shell
dr task run frontend_web:dev
```

2. Start the MCP server, application, and writer agent as described in Option 1 (steps 2-4).

3. Open your browser and navigate to http://localhost:5173/ (the Vite dev server port).

## Option 3 (experimental): Agent playground only

If you want to test just the agent without the full application, you can use the Chainlit playground interface.

1. Start the writer agent:

```shell
dr task run writer_agent:dev
```

2. In another terminal, start the Chainlit interface:

```shell
dr task run writer_agent:chainlit
```

This will start a separate frontend application for your local agent at http://localhost:8083/.
</details>

# Develop your agent

Once setup is complete, you are ready to customize your agent by adding your own logic and functionality.
See the following documentation for more details:

- [Customize your agent](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/agentic-development.html)
- [Add tools to your agent](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/agentic-tools-integrate.html)
- [Configure LLM providers](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/agentic-llm-providers.html)
- [Use the agent CLI](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/agentic-cli-guide.html)
- [Add Python requirements](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/agentic-python-packages.html)

# Deploy your agent

> [!CAUTION]
> Ensure that you have tested your agent locally before deploying.

Next, deploy your agent to DataRobot, which requires a Pulumi login.
If you do not have one, use `pulumi login --local` for local login or create a free account at [the Pulumi website](https://app.pulumi.com/signup).

Run the following command to deploy your agent:

```shell
dr task run deploy
```

# Get help

If you encounter issues or have questions, try the following:

- Check the [DataRobot documentation](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/index.html) for detailed guides.
- [Contact DataRobot](https://docs.datarobot.com/en/docs/get-started/troubleshooting/general-help.html) for support.
- Open an issue on the [GitHub repository](https://github.com/datarobot-community/datarobot-agent-application).
