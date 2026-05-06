<p align="center">
  <img src="logo.png" alt="CC CONFIG UI" width="96" height="96">
</p>

<h1 align="center">CC CONFIG UI</h1>

<p align="center">
  A lightweight, zero-dependency web UI for managing your
  <a href="https://docs.anthropic.com/en/docs/claude-code">Claude Code</a> configuration
</p>

<p align="center">
  <a href="README_CN.md">中文文档</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
  <img src="https://img.shields.io/badge/Python-3.7%2B-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/Dependencies-Zero-green.svg" alt="Dependencies">
  <img src="https://img.shields.io/badge/PRs-welcome-pink.svg" alt="PRs Welcome">
</p>

---

## ✨ What is this

Claude Code stores everything — plugins, sessions, skills, settings — in `~/.claude/`. As you use it more, that directory gets complex. **Claude Config Manager** gives you a clean web interface to see and manage it all.

**Zero dependencies.** One Python file + one HTML file. Clone and run.

## 🚀 Quick Start

```bash
git clone https://github.com/YOUR_USERNAME/cc-config-ui.git
cd cc-config-ui
python server.py
```

Then open **http://127.0.0.1:8787** in your browser.

Or use the launcher scripts:

| Platform | Command |
|----------|---------|
| Windows | `start.bat` |
| macOS / Linux | `chmod +x start.sh && ./start.sh` |

## 📦 Features

| Feature | Description |
|---------|-------------|
| 📊 **Dashboard** | Overview stats, storage breakdown, recent activity, config summary |
| 🧩 **Plugin Manager** | Enable/disable, view SKILL.md, uninstall — grouped by source |
| 💬 **Session Manager** | Browse conversations, rename sessions, resume in CLI |
| ⚙️ **Config Editor** | Edit settings.json, CLAUDE.md, permissions — in the browser |
| 🔌 **MCP Servers** | View, enable/disable, delete MCP servers across all plugins |
| ⭐ **Skills Browser** | Installed skills + marketplace browser with install status |
| 🧹 **Cleanup Tool** | Free disk space, open folders in file explorer |
| 📈 **System Info** | Token usage by model, activity heatmap, daily stats |
| 🌐 **i18n** | Full English & Chinese support, one-click switch |
| 🌙 **Themes** | Dark mode (default) + light mode toggle |

## 🖥️ Usage

<details>
<summary><b>Managing Plugins</b></summary>

1. Navigate to **Plugins** in the sidebar
2. Filter by source using the tabs at the top
3. Search by name using the search bar
4. Toggle the switch to enable/disable a plugin
5. Click **Detail** to view SKILL.md documentation
6. Click **Uninstall** to remove a plugin

</details>

<details>
<summary><b>Viewing Sessions</b></summary>

1. Navigate to **Sessions** in the sidebar
2. Select a project from the left panel
3. Click **View** to read the conversation
4. Click **Rename** (pencil icon) to set a custom title
5. Click **Resume** to copy the `claude --resume` command
6. Click **Delete** to remove a session

</details>

<details>
<summary><b>Managing MCP Servers</b></summary>

1. Navigate to **MCP** in the sidebar
2. See all MCP servers across all plugins
3. Toggle to enable/disable a server
4. Click **Detail** to view the raw config
5. Click **Delete** to remove a server

</details>

<details>
<summary><b>Browsing Skills Marketplace</b></summary>

1. Navigate to **Skills** → **Marketplace** tab
2. Select a marketplace source
3. Browse available skills (green badge = installed)
4. Click a skill to view its SKILL.md

</details>

<details>
<summary><b>Cleaning Up Storage</b></summary>

1. Navigate to **Cleanup** in the sidebar
2. Check the directories you want to clean
3. See estimated space to free in real-time
4. Click the folder icon to open any directory
5. Click **Execute Cleanup** to delete contents

</details>

## 🏗️ Architecture

```
┌──────────────────────┐       ┌──────────────────────┐
│                      │  API  │                      │
│    index.html        │◄─────►│    server.py         │
│    (Single file)     │ JSON  │    (Zero deps)       │
│                      │       │                      │
│  • Tailwind CSS CDN  │       │  • Python stdlib     │
│  • Vanilla JS        │       │  • http.server       │
│  • i18n (en/zh)      │       │  • Atomic writes     │
└──────────────────────┘       └───────────┬──────────┘
                                           │ reads/writes
                                           ▼
                                  ┌──────────────────────┐
                                  │     ~/.claude/       │
                                  │  settings.json       │
                                  │  plugins/cache/      │
                                  │  projects/           │
                                  │  skills/             │
                                  └──────────────────────┘
```

**Design principles:**
- 🔹 **Zero dependencies** — no npm, no pip, no build step
- 🔹 **Single-file architecture** — one HTML, one Python
- 🔹 **Local-only** — binds to 127.0.0.1, never exposed to network
- 🔹 **Atomic writes** — temp file + rename to prevent corruption

## 📡 API Reference

### Read (GET)

| Endpoint | Description |
|----------|-------------|
| `/api/dashboard` | Aggregated overview stats |
| `/api/plugins` | Plugins grouped by source |
| `/api/plugins/:key` | Plugin detail (SKILL.md) |
| `/api/sessions` | Projects & sessions with titles |
| `/api/sessions/:project/:id` | Session conversation content |
| `/api/skills` | Installed skills list |
| `/api/skills/:name` | Skill detail (SKILL.md) |
| `/api/mcp` | All MCP servers |
| `/api/mcp/:plugin/:server` | MCP server config |
| `/api/marketplace/skills` | Marketplace skills browser |
| `/api/settings` | settings.json |
| `/api/claude-md` | CLAUDE.md |
| `/api/history` | Session history |
| `/api/stats` | Usage statistics |
| `/api/storage` | Storage breakdown |

### Write (PUT/POST/DELETE)

| Method | Endpoint | Description |
|--------|----------|-------------|
| PUT | `/api/settings` | Write settings.json |
| PUT | `/api/claude-md` | Write CLAUDE.md |
| POST | `/api/plugins/toggle` | Enable/disable plugin |
| POST | `/api/mcp/toggle` | Enable/disable MCP |
| POST | `/api/sessions/rename` | Rename session |
| POST | `/api/cleanup/execute` | Execute cleanup |
| POST | `/api/open-folder` | Open folder in explorer |
| DELETE | `/api/plugins/:key` | Uninstall plugin |
| DELETE | `/api/sessions/:project/:id` | Delete session |
| DELETE | `/api/skills/:name` | Delete skill |
| DELETE | `/api/mcp/:plugin/:server` | Delete MCP server |

## 📁 Project Structure

```
├── server.py            # Backend REST API (~1100 lines)
├── index.html           # Frontend UI (~1400 lines)
├── logo.png             # Project logo
├── start.bat            # Windows launcher
├── start.sh             # macOS/Linux launcher
├── README.md            # English documentation
└── README_CN.md         # 中文文档
```

## 🔒 Security

- Server binds to **localhost only** (`127.0.0.1`)
- API key fields masked with password input
- Path traversal protection (all paths validated against `~/.claude/`)
- Atomic file writes prevent corruption
- Delete operations require confirmation

## 🤝 Contributing

Contributions are welcome!

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

<p align="center">
  Built with ❤️ for the <a href="https://docs.anthropic.com/en/docs/claude-code">Claude Code</a> community
</p>
