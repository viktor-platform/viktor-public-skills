# Installing VIKTOR Skills

This file keeps the detailed install options out of the main README.

## Recommended: npx skills

Install into Claude Code and Codex:

```bash
npx skills add viktor-platform/viktor-public-skills --skill '*' -a claude-code -a codex -g
```

Run non-interactively:

```bash
npx skills add viktor-platform/viktor-public-skills --skill '*' -a claude-code -a codex -g -y
```

Preview the available skills:

```bash
npx skills add viktor-platform/viktor-public-skills --list
```

Update later:

```bash
npx skills update -g
```

## Codex

For Codex, the recommended install path is the `npx skills` command above with `-a codex`.

After installing, start a new Codex thread and invoke the router explicitly:

```text
$viktor
```

You can also let Codex pick the skill automatically by asking for VIKTOR app work.

Codex reads skills from agent-standard skill folders. The exact user folder can vary by Codex version, so prefer `npx skills` unless you are doing a manual install for local development.

## Claude Code Marketplace

<details>
<summary>Watch the 30-second marketplace setup</summary>

![Add the VIKTOR marketplace and try the skills in Claude](https://github.com/viktor-platform/viktor-public-skills/releases/download/docs-media/viktor-claude-skill-demo.gif)

</details>

Add the marketplace and install the plugin:

```text
/plugin marketplace add viktor-platform/viktor-public-skills
/plugin install viktor-skills@viktor-public-skills
/reload-plugins
```

Invoke the router:

```text
/viktor-skills:viktor
```

## GitHub Copilot

### VS Code

1. Open [Install VIKTOR Skills in VS Code](https://vscode.dev/redirect?url=vscode%3A%2F%2Fchat-plugin%2Finstall&source=viktor-platform%2Fviktor-public-skills&plugin=viktor-skills).
2. In **Choose Where to Install Plugins**, select **Copilot** to install the skill pack for GitHub Copilot on this machine. Choose **VS Code** if you want VS Code to manage it for compatible agents in the editor.
3. Confirm that the marketplace is `viktor-platform/viktor-public-skills` and the plugin is `viktor-skills`. Confirm the install.
4. Open your app folder and start a new Copilot chat. Ask “Use the `viktor` skill to help me build and run this app.”

If the link does not open the install dialog, run **Chat: Open Customizations** from the Command Palette. Select **Browse → Configure Marketplaces → Add Marketplace**. Enter `viktor-platform/viktor-public-skills`, return to **Browse**, and install `viktor-skills` from that marketplace. If plugin actions are missing, check `chat.plugins.enabled` in Settings. [VS Code plugin guide](https://code.visualstudio.com/docs/agent-customization/agent-plugins)

### GitHub Copilot app

1. Open **Customize** in the sidebar.
2. Open the marketplace settings next to the marketplace dropdown. Add `viktor-platform/viktor-public-skills`.
3. On **Browse**, search for `viktor-skills` and select **Install**.
4. Start a new chat and ask “Use the `viktor` skill to help me build and run this app.”

[GitHub Copilot app guide](https://docs.github.com/en/copilot/how-tos/github-copilot-app/customize-github-copilot-app#adding-a-plugin-marketplace)

## Windows PowerShell Without npx

If you do not want to use `npx`, clone the repository and copy the skills into the local Claude Code and Codex skill folders:

```powershell
$repo = Join-Path $env:TEMP 'viktor-public-skills'; Remove-Item $repo -Recurse -Force -ErrorAction SilentlyContinue; git clone --depth 1 https://github.com/viktor-platform/viktor-public-skills.git $repo; New-Item -ItemType Directory -Force -Path "$HOME\.claude\skills", "$HOME\.codex\skills", "$HOME\.agents\skills" | Out-Null; Copy-Item "$repo\skills\*" "$HOME\.claude\skills\" -Recurse -Force; Copy-Item "$repo\skills\*" "$HOME\.codex\skills\" -Recurse -Force; Copy-Item "$repo\skills\*" "$HOME\.agents\skills\" -Recurse -Force
```

If Git is not installed yet, install it with WinGet first and run the copy in the same PowerShell session:

```powershell
winget install -e --id Git.Git --accept-package-agreements --accept-source-agreements; $env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User'); $repo = Join-Path $env:TEMP 'viktor-public-skills'; Remove-Item $repo -Recurse -Force -ErrorAction SilentlyContinue; git clone --depth 1 https://github.com/viktor-platform/viktor-public-skills.git $repo; New-Item -ItemType Directory -Force -Path "$HOME\.claude\skills", "$HOME\.codex\skills", "$HOME\.agents\skills" | Out-Null; Copy-Item "$repo\skills\*" "$HOME\.claude\skills\" -Recurse -Force; Copy-Item "$repo\skills\*" "$HOME\.codex\skills\" -Recurse -Force; Copy-Item "$repo\skills\*" "$HOME\.agents\skills\" -Recurse -Force
```

Optional: install Claude Code itself with WinGet:

```powershell
winget install -e --id Anthropic.ClaudeCode --accept-package-agreements --accept-source-agreements
```

## Manual Install

Manual install is useful when you are editing this repository locally.

For Claude Code:

```bash
mkdir -p ~/.claude/skills
cp -R skills/* ~/.claude/skills/
```

For Codex:

```bash
mkdir -p ~/.codex/skills
cp -R skills/* ~/.codex/skills/
```

Codex also scans agent-standard skills folders in current versions, so this project can be installed there too:

```bash
mkdir -p ~/.agents/skills
cp -R skills/* ~/.agents/skills/
```

Or symlink local edits into both agents:

```bash
mkdir -p ~/.claude/skills ~/.codex/skills ~/.agents/skills
for skill in skills/*; do
  ln -sfn "$(pwd)/$skill" "$HOME/.claude/skills/$(basename "$skill")"
  ln -sfn "$(pwd)/$skill" "$HOME/.codex/skills/$(basename "$skill")"
  ln -sfn "$(pwd)/$skill" "$HOME/.agents/skills/$(basename "$skill")"
done
```

## Troubleshooting

Install all skills, not only `viktor`. The router skill links to specialized VIKTOR skills with relative references.

Restart Claude Code or Codex if the skills do not appear after installation.

For Claude Code marketplace installs, plugin skills are namespaced. Use `/viktor-skills:viktor`, not `/viktor`.

For `npx skills` installs, the standalone skill name is available as `/viktor` in Claude Code and as a skill mention in Codex.
