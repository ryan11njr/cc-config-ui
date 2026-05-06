"""
Claude Code Configuration Manager - Backend Server
Zero-dependency Python REST API for managing ~/.claude/ directory
"""

import http.server
import json
import os
import platform
import shutil
import subprocess
import tempfile
import urllib.parse
from pathlib import Path
from datetime import datetime

# Auto-detect: ~/.claude on all platforms
CLAUDE_DIR = Path.home() / ".claude"
HOST = "127.0.0.1"
PORT = 8787
HTML_DIR = Path(__file__).resolve().parent


class ClaudeAPIHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, indent=None).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text, status=200, content_type="text/plain; charset=utf-8"):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, message, status=400):
        self._send_json({"error": message}, status)

    def _read_json(self, rel_path):
        p = CLAUDE_DIR / rel_path
        if not p.exists():
            return None
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_json(self, rel_path, data):
        p = CLAUDE_DIR / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: temp file then rename
        fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            # On Windows, need to remove target first
            if p.exists():
                p.unlink()
            os.rename(tmp, str(p))
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def _write_text(self, rel_path, text):
        p = CLAUDE_DIR / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
            if p.exists():
                p.unlink()
            os.rename(tmp, str(p))
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def _read_text(self, rel_path):
        p = CLAUDE_DIR / rel_path
        if not p.exists():
            return None
        with open(p, "r", encoding="utf-8") as f:
            return f.read()

    def _dir_size(self, path):
        """Get total size of directory in bytes."""
        total = 0
        if path.is_file():
            return path.stat().st_size
        try:
            for entry in path.rglob("*"):
                if entry.is_file():
                    try:
                        total += entry.stat().st_size
                    except (OSError, PermissionError):
                        pass
        except (OSError, PermissionError):
            pass
        return total

    def _format_size(self, size_bytes):
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

    def _get_session_title(self, filepath, max_lines=50):
        """Extract conversation title from session file."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    try:
                        data = json.loads(line.strip())
                        # Prefer summary entries (compacted conversation titles)
                        if data.get("type") == "summary" and data.get("summary"):
                            return data["summary"][:120]
                        # Fall back to first human message
                        if data.get("type") == "human" and data.get("message"):
                            msg = data["message"]
                            if isinstance(msg, str):
                                return msg[:120]
                            if isinstance(msg, dict):
                                content = msg.get("content", "")
                                if isinstance(content, str):
                                    return content[:120]
                                if isinstance(content, list):
                                    for block in content:
                                        if isinstance(block, dict) and block.get("type") == "text":
                                            return block.get("text", "")[:120]
                    except Exception:
                        continue
        except Exception:
            pass
        return None

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        return {}

    # ==================== ROUTING ====================

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, PUT, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        query = urllib.parse.parse_qs(parsed.query)

        routes = {
            "/api/dashboard": self.h_dashboard,
            "/api/settings": self.h_get_settings,
            "/api/settings-local": self.h_get_settings_local,
            "/api/claude-md": self.h_get_claude_md,
            "/api/plugins": self.h_get_plugins,
            "/api/sessions": self.h_get_sessions,
            "/api/skills": self.h_get_skills,
            "/api/history": self.h_get_history,
            "/api/stats": self.h_get_stats,
            "/api/storage": self.h_get_storage,
            "/api/marketplaces": self.h_get_marketplaces,
            "/api/shell-snapshots": self.h_get_shell_snapshots,
            "/api/mcp": self.h_get_mcp,
            "/api/marketplace/skills": self.h_get_marketplace_skills,
        }

        if path in routes:
            routes[path](query)
        elif path.startswith("/api/plugins/"):
            key = path[len("/api/plugins/"):]
            self.h_get_plugin_detail(urllib.parse.unquote(key))
        elif path.startswith("/api/mcp/"):
            parts = path[len("/api/mcp/"):].split("/")
            if len(parts) == 2 and parts[1]:
                self.h_get_mcp_detail(urllib.parse.unquote(parts[0]), urllib.parse.unquote(parts[1]))
            else:
                self._send_error("Not found", 404)
        elif path.startswith("/api/sessions/"):
            parts = path[len("/api/sessions/"):].split("/")
            if len(parts) == 2 and parts[1]:
                self.h_get_session_content(urllib.parse.unquote(parts[0]), urllib.parse.unquote(parts[1]))
            else:
                self.h_get_project_sessions(urllib.parse.unquote(parts[0]), query)
        elif path.startswith("/api/marketplace/skill/"):
            # Marketplace skill detail: /api/marketplace/skill/:mp/:skill
            parts = path[len("/api/marketplace/skill/"):].split("/")
            if len(parts) == 2:
                self.h_get_marketplace_skill_detail(urllib.parse.unquote(parts[0]), urllib.parse.unquote(parts[1]))
            else:
                self._send_error("Not found", 404)
        elif path.startswith("/api/skills/"):
            name = path[len("/api/skills/"):]
            self.h_get_skill_detail(urllib.parse.unquote(name))
        elif path == "/api/file-content":
            rel = query.get("path", [""])[0]
            self.h_get_file_content(rel)
        else:
            self._serve_static(path)

    def do_PUT(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        body = self._read_body()

        if path == "/api/settings":
            self.h_put_settings(body)
        elif path == "/api/settings-local":
            self.h_put_settings_local(body)
        elif path == "/api/claude-md":
            self.h_put_claude_md(body)
        elif path == "/api/file-content":
            self.h_put_file_content(body)
        else:
            self._send_error("Unknown endpoint", 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        body = self._read_body()

        if path == "/api/plugins/toggle":
            self.h_toggle_plugin(body)
        elif path == "/api/skills/toggle":
            self.h_toggle_skill(body)
        elif path == "/api/cleanup/preview":
            self.h_cleanup_preview(body)
        elif path == "/api/cleanup/execute":
            self.h_cleanup_execute(body)
        elif path == "/api/mcp/toggle":
            self.h_toggle_mcp(body)
        elif path == "/api/sessions/rename":
            self.h_rename_session(body)
        elif path == "/api/open-folder":
            self.h_open_folder(body)
        else:
            self._send_error("Unknown endpoint", 404)

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path.startswith("/api/plugins/"):
            key = path[len("/api/plugins/"):]
            self.h_delete_plugin(urllib.parse.unquote(key))
        elif path.startswith("/api/sessions/"):
            parts = path[len("/api/sessions/"):].split("/")
            if len(parts) == 2:
                self.h_delete_session(urllib.parse.unquote(parts[0]), urllib.parse.unquote(parts[1]))
        elif path.startswith("/api/skills/"):
            name = path[len("/api/skills/"):]
            self.h_delete_skill(urllib.parse.unquote(name))
        elif path.startswith("/api/mcp/"):
            parts = path[len("/api/mcp/"):].split("/")
            if len(parts) == 2:
                self.h_delete_mcp(urllib.parse.unquote(parts[0]), urllib.parse.unquote(parts[1]))
            else:
                self._send_error("Not found", 404)
        else:
            self._send_error("Unknown endpoint", 404)

    # ==================== STATIC FILES ====================

    def _serve_static(self, path):
        if path == "" or path == "/":
            path = "/index.html"
        file_path = HTML_DIR / path.lstrip("/")
        if file_path.exists() and file_path.is_file():
            ext = file_path.suffix.lower()
            types = {
                ".html": "text/html; charset=utf-8",
                ".css": "text/css; charset=utf-8",
                ".js": "application/javascript; charset=utf-8",
                ".json": "application/json; charset=utf-8",
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".svg": "image/svg+xml",
                ".ico": "image/x-icon",
            }
            ct = types.get(ext, "application/octet-stream")
            body = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)
        else:
            self._send_error("File not found", 404)

    # ==================== GET HANDLERS ====================

    def h_dashboard(self, query=None):
        settings = self._read_json("settings.json") or {}
        stats = self._read_json("stats-cache.json") or {}

        # Plugins by source
        plugins_by_source = {}
        for key in settings.get("enabledPlugins", {}):
            parts = key.split("@")
            source = parts[1] if len(parts) > 1 else "unknown"
            plugins_by_source[source] = plugins_by_source.get(source, 0) + 1

        # Projects and sessions
        projects_dir = CLAUDE_DIR / "projects"
        projects = []
        total_sessions = 0
        if projects_dir.exists():
            for d in sorted(projects_dir.iterdir()):
                if d.is_dir():
                    count = sum(1 for f in d.iterdir() if f.is_file() and f.suffix == ".jsonl")
                    size = self._dir_size(d)
                    total_sessions += count
                    projects.append({
                        "name": d.name,
                        "sessions": count,
                        "size": size,
                    })

        # Skills count
        skills_dir = CLAUDE_DIR / "skills"
        skill_count = 0
        if skills_dir.exists():
            skill_count = sum(1 for d in skills_dir.iterdir() if d.is_dir())

        # Recent history
        recent = []
        history_path = CLAUDE_DIR / "history.jsonl"
        if history_path.exists():
            with open(history_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in lines[-15:]:
                try:
                    recent.append(json.loads(line.strip()))
                except Exception:
                    pass
        recent.reverse()

        # Storage breakdown
        storage = {}
        total_size = 0
        for item in sorted(CLAUDE_DIR.iterdir()):
            try:
                s = self._dir_size(item)
                storage[item.name] = s
                total_size += s
            except Exception:
                pass

        self._send_json({
            "totalStorage": total_size,
            "storage": storage,
            "pluginsBySource": plugins_by_source,
            "totalPlugins": len(settings.get("enabledPlugins", {})),
            "totalProjects": len(projects),
            "totalSessions": total_sessions,
            "totalSkills": skill_count,
            "model": settings.get("model", "unknown"),
            "effortLevel": settings.get("effortLevel", "default"),
            "recentHistory": recent[:15],
            "projects": projects,
        })

    def h_get_settings(self, query=None):
        data = self._read_json("settings.json")
        if data:
            self._send_json(data)
        else:
            self._send_error("settings.json not found", 404)

    def h_get_settings_local(self, query=None):
        data = self._read_json("settings.local.json")
        if data:
            self._send_json(data)
        else:
            self._send_error("settings.local.json not found", 404)

    def h_get_claude_md(self, query=None):
        text = self._read_text("CLAUDE.md")
        if text is not None:
            self._send_json({"content": text})
        else:
            self._send_json({"content": ""})

    def h_get_plugins(self, query=None):
        settings = self._read_json("settings.json") or {}
        installed = self._read_json("plugins/installed_plugins.json") or {}
        enabled = settings.get("enabledPlugins", {})

        plugins = []
        for key, is_enabled in enabled.items():
            parts = key.split("@")
            name = parts[0]
            source = parts[1] if len(parts) > 1 else "unknown"

            # Get extra info from installed_plugins
            info = installed.get(key, {})
            install_count = info.get("installCount", 0)
            version = info.get("version", "unknown")
            installed_at = info.get("installedAt", "unknown")

            plugins.append({
                "key": key,
                "name": name,
                "source": source,
                "enabled": is_enabled,
                "installCount": install_count,
                "version": version,
                "installedAt": installed_at,
                "path": info.get("path", ""),
            })

        # Group by source
        sources = {}
        for p in plugins:
            s = p["source"]
            if s not in sources:
                sources[s] = []
            sources[s].append(p)

        self._send_json({"plugins": plugins, "sources": sources, "total": len(plugins)})

    def h_get_plugin_detail(self, key):
        # Try to find SKILL.md in plugin cache
        cache_dir = CLAUDE_DIR / "plugins" / "cache"
        skill_content = ""
        found_path = ""

        if cache_dir.exists():
            for source_dir in cache_dir.iterdir():
                if source_dir.is_dir():
                    for plugin_dir in source_dir.iterdir():
                        if plugin_dir.is_dir():
                            # Check if plugin name matches
                            if key.split("@")[0] == plugin_dir.name:
                                skill_file = None
                                for root, dirs, files in os.walk(plugin_dir):
                                    for f in files:
                                        if f == "SKILL.md":
                                            skill_file = Path(root) / f
                                            break
                                    if skill_file:
                                        break
                                if skill_file and skill_file.exists():
                                    skill_content = skill_file.read_text(encoding="utf-8")
                                    found_path = str(skill_file.parent)

        self._send_json({"key": key, "skillContent": skill_content, "path": found_path})

    def h_get_sessions(self, query=None):
        projects_dir = CLAUDE_DIR / "projects"
        projects = []
        if projects_dir.exists():
            for d in sorted(projects_dir.iterdir()):
                if d.is_dir():
                    custom_titles = self._get_session_titles(d.name)
                    sessions = []
                    for f in sorted(d.iterdir()):
                        if f.is_file() and f.suffix == ".jsonl":
                            stat = f.stat()
                            # Custom title takes priority, then auto-detected
                            sid = f.stem
                            title = custom_titles.get(sid) or self._get_session_title(f)
                            has_custom = sid in custom_titles
                            sessions.append({
                                "id": sid,
                                "title": title,
                                "hasCustomTitle": has_custom,
                                "size": stat.st_size,
                                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            })
                    projects.append({
                        "name": d.name,
                        "sessions": sessions,
                        "size": self._dir_size(d),
                    })
        self._send_json({"projects": projects})

    def h_get_project_sessions(self, project_name, query=None):
        proj_dir = CLAUDE_DIR / "projects" / project_name
        if not proj_dir.exists():
            self._send_error("Project not found", 404)
            return

        sessions = []
        for f in sorted(proj_dir.iterdir()):
            if f.is_file() and f.suffix == ".jsonl":
                stat = f.stat()
                sessions.append({
                    "id": f.stem,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })

        # Also check subdirectories
        subagents_count = 0
        for d in proj_dir.iterdir():
            if d.is_dir():
                sub_dir = d / "subagents"
                if sub_dir.exists():
                    subagents_count += sum(1 for _ in sub_dir.iterdir() if _.is_file())

        self._send_json({
            "project": project_name,
            "sessions": sessions,
            "totalSize": self._dir_size(proj_dir),
            "subagentsCount": subagents_count,
        })

    def h_get_session_content(self, project, session_id):
        """Read conversation messages from a session .jsonl file."""
        session_file = CLAUDE_DIR / "projects" / project / f"{session_id}.jsonl"
        if not session_file.exists():
            self._send_error("Session not found", 404)
            return

        messages = []
        title = None
        cwd = ""
        try:
            with open(session_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        msg_type = data.get("type", "")

                        # Get title from summary
                        if msg_type == "summary" and not title and data.get("summary"):
                            title = data["summary"]

                        # Get cwd
                        if data.get("cwd") and not cwd:
                            cwd = data["cwd"]

                        # Extract human messages
                        if msg_type == "human":
                            text = self._extract_text(data.get("message", ""))
                            if text:
                                messages.append({
                                    "role": "user",
                                    "content": text[:2000],
                                    "timestamp": data.get("timestamp", ""),
                                })

                        # Extract assistant messages
                        elif msg_type == "assistant":
                            text = self._extract_text(data.get("message", ""))
                            if text:
                                messages.append({
                                    "role": "assistant",
                                    "content": text[:2000],
                                    "timestamp": data.get("timestamp", ""),
                                })

                        # Limit to last 200 messages for performance
                        if len(messages) > 200:
                            break
                    except Exception:
                        continue
        except Exception as e:
            self._send_error(str(e), 500)
            return

        self._send_json({
            "id": session_id,
            "project": project,
            "title": title,
            "cwd": cwd,
            "messages": messages[-200:],
            "totalMessages": len(messages),
        })

    def _extract_text(self, message):
        """Extract plain text from a message field."""
        if isinstance(message, str):
            return message.strip()
        if isinstance(message, dict):
            content = message.get("content", "")
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                parts = []
                for block in content:
                    if isinstance(block, str):
                        parts.append(block)
                    elif isinstance(block, dict):
                        if block.get("type") == "text":
                            parts.append(block.get("text", ""))
                        elif block.get("type") == "tool_use":
                            parts.append(f"[Tool: {block.get('name', 'unknown')}]")
                        elif block.get("type") == "tool_result":
                            content_val = block.get("content", "")
                            if isinstance(content_val, str):
                                parts.append(content_val[:500])
                return "\n".join(parts).strip()
        return ""

    def h_get_skills(self, query=None):
        skills_dir = CLAUDE_DIR / "skills"
        disabled_set = self._get_disabled_skills()
        skills = []
        if skills_dir.exists():
            for d in sorted(skills_dir.iterdir()):
                if d.is_dir() and not d.name.startswith("."):
                    skill_file = d / "SKILL.md"
                    size = self._dir_size(d)
                    skills.append({
                        "name": d.name,
                        "hasSkillMd": skill_file.exists(),
                        "size": size,
                        "disabled": d.name in disabled_set,
                    })
        self._send_json({"skills": skills, "total": len(skills)})

    def _get_disabled_skills(self):
        """Read the set of disabled skill names from metadata file."""
        f = CLAUDE_DIR / "disabled-skills.json"
        if f.exists():
            try:
                return set(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass
        return set()

    def _save_disabled_skills(self, disabled_set):
        """Save the set of disabled skill names to metadata file."""
        f = CLAUDE_DIR / "disabled-skills.json"
        f.write_text(json.dumps(sorted(disabled_set), indent=2), encoding="utf-8")

    def h_get_skill_detail(self, name):
        skill_file = CLAUDE_DIR / "skills" / name / "SKILL.md"
        disabled = name in self._get_disabled_skills()
        if skill_file.exists():
            content = skill_file.read_text(encoding="utf-8")
            self._send_json({"name": name, "content": content, "disabled": disabled})
        else:
            self._send_error("Skill not found", 404)

    def h_toggle_skill(self, body):
        name = body.get("name", "")
        disable = body.get("disabled", False)
        if not name:
            self._send_error("Missing name", 400)
            return
        skill_dir = CLAUDE_DIR / "skills" / name
        if not skill_dir.exists():
            self._send_error("Skill not found", 404)
            return
        disabled_set = self._get_disabled_skills()
        if disable:
            disabled_set.add(name)
        else:
            disabled_set.discard(name)
        self._save_disabled_skills(disabled_set)
        self._send_json({"ok": True, "disabled": disable})

    def h_get_marketplace_skill_detail(self, mp_name, skill_name):
        """Read SKILL.md from a marketplace skill directory."""
        raw = self._read_json("plugins/known_marketplaces.json") or {}
        mp_data = raw.get(mp_name)
        if not isinstance(mp_data, dict):
            self._send_error("Marketplace not found", 404)
            return
        install_loc = mp_data.get("installLocation", "")
        if not install_loc:
            self._send_error("No install location", 404)
            return
        skill_file = CLAUDE_DIR / install_loc / skill_name / "SKILL.md"
        if skill_file.exists():
            content = skill_file.read_text(encoding="utf-8")
            self._send_json({"name": skill_name, "content": content, "marketplace": mp_name})
        else:
            # Try listing files in the skill directory to find any readable file
            skill_dir = CLAUDE_DIR / install_loc / skill_name
            if skill_dir.exists():
                # Return directory listing instead
                files = [f.name for f in skill_dir.iterdir()]
                self._send_json({"name": skill_name, "content": f"Files in {skill_name}:\n" + "\n".join(files), "marketplace": mp_name})
            else:
                self._send_error("Skill not found", 404)

    def h_get_history(self, query=None):
        history_path = CLAUDE_DIR / "history.jsonl"
        entries = []
        if history_path.exists():
            with open(history_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entries.append(json.loads(line.strip()))
                    except Exception:
                        pass
        # Return last 100 entries reversed
        self._send_json({"entries": entries[-100:][::-1], "total": len(entries)})

    def h_get_stats(self, query=None):
        data = self._read_json("stats-cache.json")
        if data:
            self._send_json(data)
        else:
            self._send_json({})

    def h_get_storage(self, query=None):
        storage = {}
        total = 0
        for item in sorted(CLAUDE_DIR.iterdir()):
            try:
                s = self._dir_size(item)
                storage[item.name] = s
                total += s
            except Exception:
                pass
        self._send_json({"storage": storage, "total": total})

    def h_get_marketplaces(self, query=None):
        data = self._read_json("plugins/known_marketplaces.json")
        if data:
            self._send_json(data)
        else:
            self._send_json([])

    def h_get_shell_snapshots(self, query=None):
        snap_dir = CLAUDE_DIR / "shell-snapshots"
        snaps = []
        if snap_dir.exists():
            for f in sorted(snap_dir.iterdir()):
                if f.is_file():
                    stat = f.stat()
                    snaps.append({
                        "name": f.name,
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    })
        self._send_json({"snapshots": snaps})

    def h_get_file_content(self, rel_path):
        if not rel_path:
            self._send_error("path parameter required", 400)
            return
        p = CLAUDE_DIR / rel_path
        if not p.exists():
            self._send_error("File not found", 404)
            return
        # Safety: ensure path is within CLAUDE_DIR
        try:
            p.resolve().relative_to(CLAUDE_DIR.resolve())
        except ValueError:
            self._send_error("Access denied", 403)
            return
        content = p.read_text(encoding="utf-8")
        self._send_json({"path": rel_path, "content": content})

    # ==================== PUT HANDLERS ====================

    def h_put_settings(self, body):
        try:
            self._write_json("settings.json", body)
            self._send_json({"ok": True})
        except Exception as e:
            self._send_error(str(e), 500)

    def h_put_settings_local(self, body):
        try:
            self._write_json("settings.local.json", body)
            self._send_json({"ok": True})
        except Exception as e:
            self._send_error(str(e), 500)

    def h_put_claude_md(self, body):
        try:
            self._write_text("CLAUDE.md", body.get("content", ""))
            self._send_json({"ok": True})
        except Exception as e:
            self._send_error(str(e), 500)

    def h_put_file_content(self, body):
        rel_path = body.get("path", "")
        content = body.get("content", "")
        if not rel_path:
            self._send_error("path required", 400)
            return
        p = CLAUDE_DIR / rel_path
        # Safety check
        try:
            p.resolve().relative_to(CLAUDE_DIR.resolve())
        except ValueError:
            self._send_error("Access denied", 403)
            return
        try:
            self._write_text(rel_path, content)
            self._send_json({"ok": True})
        except Exception as e:
            self._send_error(str(e), 500)

    # ==================== POST HANDLERS ====================

    def h_toggle_plugin(self, body):
        key = body.get("key", "")
        enabled = body.get("enabled", True)
        if not key:
            self._send_error("key required", 400)
            return
        settings = self._read_json("settings.json") or {}
        if "enabledPlugins" in settings and key in settings["enabledPlugins"]:
            settings["enabledPlugins"][key] = enabled
            try:
                self._write_json("settings.json", settings)
                self._send_json({"ok": True, "key": key, "enabled": enabled})
            except Exception as e:
                self._send_error(str(e), 500)
        else:
            self._send_error(f"Plugin {key} not found", 404)

    def h_cleanup_preview(self, body):
        targets = body.get("targets", [])
        total = 0
        details = {}
        for t in targets:
            p = CLAUDE_DIR / t
            if p.exists():
                s = self._dir_size(p)
                details[t] = s
                total += s
        self._send_json({"targets": details, "totalSize": total})

    def h_cleanup_execute(self, body):
        targets = body.get("targets", [])
        results = {}
        for t in targets:
            p = CLAUDE_DIR / t
            if p.exists():
                if p.is_dir():
                    shutil.rmtree(str(p))
                    p.mkdir()  # Recreate empty dir
                    results[t] = "cleaned"
                else:
                    p.unlink()
                    results[t] = "deleted"
            else:
                results[t] = "not_found"
        self._send_json({"results": results})

    # ==================== DELETE HANDLERS ====================

    def h_delete_plugin(self, key):
        settings = self._read_json("settings.json") or {}
        # Remove from enabledPlugins
        if "enabledPlugins" in settings and key in settings["enabledPlugins"]:
            del settings["enabledPlugins"][key]
        # Remove from installed_plugins
        installed = self._read_json("plugins/installed_plugins.json") or {}
        if key in installed:
            del installed[key]
        try:
            self._write_json("settings.json", settings)
            self._write_json("plugins/installed_plugins.json", installed)
            self._send_json({"ok": True})
        except Exception as e:
            self._send_error(str(e), 500)

    def h_delete_session(self, project, session_id):
        session_file = CLAUDE_DIR / "projects" / project / f"{session_id}.jsonl"
        if not session_file.exists():
            self._send_error("Session not found", 404)
            return
        try:
            session_file.unlink()
            # Also remove subdirectory if exists
            session_dir = CLAUDE_DIR / "projects" / project / session_id
            if session_dir.exists():
                shutil.rmtree(str(session_dir))
            self._send_json({"ok": True})
        except Exception as e:
            self._send_error(str(e), 500)

    def h_delete_skill(self, name):
        skill_dir = CLAUDE_DIR / "skills" / name
        if not skill_dir.exists():
            self._send_error("Skill not found", 404)
            return
        try:
            shutil.rmtree(str(skill_dir))
            # Also remove from disabled set if present
            disabled_set = self._get_disabled_skills()
            if name in disabled_set:
                disabled_set.discard(name)
                self._save_disabled_skills(disabled_set)
            self._send_json({"ok": True})
        except Exception as e:
            self._send_error(str(e), 500)

    # ==================== MCP HANDLERS ====================

    def _scan_mcp_configs(self):
        """Scan all .mcp.json files in plugin cache dirs, return aggregated MCP servers."""
        servers = []
        cache_dir = CLAUDE_DIR / "plugins" / "cache"
        if not cache_dir.exists():
            return servers

        # Read auth cache
        auth_cache = self._read_json("mcp-needs-auth-cache.json") or {}

        # Walk the entire cache tree to find .mcp.json files
        # Structure: cache/source/plugin/version/.mcp.json
        for root, dirs, files in os.walk(cache_dir):
            for f in files:
                if f != ".mcp.json":
                    continue
                mcp_file = Path(root) / f
                # Extract plugin name from path: cache/source/plugin/version/.mcp.json
                parts = mcp_file.relative_to(cache_dir).parts
                plugin_name = parts[1] if len(parts) > 2 else mcp_file.parent.name
                source_name = parts[0] if len(parts) > 1 else "unknown"
                try:
                    data = json.loads(mcp_file.read_text(encoding="utf-8"))
                    mcp_servers = data.get("mcpServers", {})
                    for srv_name, srv_config in mcp_servers.items():
                        srv_type = "http" if srv_config.get("type") == "http" or srv_config.get("url") else "command"
                        env = srv_config.get("env", {})
                        servers.append({
                            "name": srv_name,
                            "plugin": plugin_name,
                            "source": source_name,
                            "type": srv_type,
                            "url": srv_config.get("url", ""),
                            "command": srv_config.get("command", ""),
                            "args": srv_config.get("args", []),
                            "env_keys": list(env.keys()) if env else [],
                            "disabled": srv_config.get("disabled", False),
                            "config_path": str(mcp_file),
                            "needs_auth": srv_name in auth_cache,
                        })
                except Exception:
                    continue
        return servers

    def h_get_mcp(self, query=None):
        servers = self._scan_mcp_configs()
        # Group by plugin
        by_plugin = {}
        for s in servers:
            pk = s["plugin"]
            if pk not in by_plugin:
                by_plugin[pk] = []
            by_plugin[pk].append(s)
        self._send_json({"servers": servers, "byPlugin": by_plugin, "total": len(servers)})

    def h_get_mcp_detail(self, plugin, server_name):
        """Return raw config for a specific MCP server."""
        mcp_file = self._find_mcp_file(plugin)
        if not mcp_file:
            self._send_error("Not found", 404)
            return
        try:
            data = json.loads(mcp_file.read_text(encoding="utf-8"))
            srv_config = data.get("mcpServers", {}).get(server_name)
            if srv_config:
                self._send_json({
                    "name": server_name,
                    "plugin": plugin,
                    "config": srv_config,
                    "config_path": str(mcp_file),
                })
            else:
                self._send_error("MCP server not found in config", 404)
        except Exception as e:
            self._send_error(str(e), 500)

    def _find_mcp_file(self, plugin):
        """Find the .mcp.json file for a plugin by walking cache tree."""
        cache_dir = CLAUDE_DIR / "plugins" / "cache"
        if not cache_dir.exists():
            return None
        for root, dirs, files in os.walk(cache_dir):
            for f in files:
                if f != ".mcp.json":
                    continue
                mcp_file = Path(root) / f
                parts = mcp_file.relative_to(cache_dir).parts
                if len(parts) > 1 and parts[1] == plugin:
                    return mcp_file
        return None

    def h_toggle_mcp(self, body):
        plugin = body.get("plugin", "")
        server_name = body.get("server", "")
        disabled = body.get("disabled", False)
        if not plugin or not server_name:
            self._send_error("plugin and server required", 400)
            return

        mcp_file = self._find_mcp_file(plugin)
        if not mcp_file:
            self._send_error("MCP server not found", 404)
            return

        try:
            data = json.loads(mcp_file.read_text(encoding="utf-8"))
            if server_name not in data.get("mcpServers", {}):
                self._send_error("MCP server not found in config", 404)
                return
            data["mcpServers"][server_name]["disabled"] = disabled
            fd, tmp = tempfile.mkstemp(dir=str(mcp_file.parent), suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            if mcp_file.exists():
                mcp_file.unlink()
            os.rename(tmp, str(mcp_file))
            self._send_json({"ok": True, "server": server_name, "disabled": disabled})
        except Exception as e:
            if os.path.exists(tmp):
                os.unlink(tmp)
            self._send_error(str(e), 500)

    def h_delete_mcp(self, plugin, server_name):
        mcp_file = self._find_mcp_file(plugin)
        if not mcp_file:
            self._send_error("MCP server not found", 404)
            return

        try:
            data = json.loads(mcp_file.read_text(encoding="utf-8"))
            if server_name not in data.get("mcpServers", {}):
                self._send_error("MCP server not found in config", 404)
                return
            del data["mcpServers"][server_name]
            fd, tmp = tempfile.mkstemp(dir=str(mcp_file.parent), suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            if mcp_file.exists():
                mcp_file.unlink()
            os.rename(tmp, str(mcp_file))
            self._send_json({"ok": True})
        except Exception as e:
            if os.path.exists(tmp):
                os.unlink(tmp)
            self._send_error(str(e), 500)

    # ==================== MARKETPLACE SKILLS ====================

    def h_get_marketplace_skills(self, query=None):
        raw = self._read_json("plugins/known_marketplaces.json") or {}
        # known_marketplaces.json is a dict: {marketplace_name: {source, url/path, installLocation, ...}}
        installed = self._read_json("plugins/installed_plugins.json") or {}
        installed_names = set()
        for key in installed:
            parts = key.split("@")
            installed_names.add(parts[0])

        result = []
        for mp_name, mp_data in raw.items():
            if not isinstance(mp_data, dict):
                continue
            # source can be a dict like {"source": "git", "url": "..."} or a string
            source_raw = mp_data.get("source", mp_name)
            if isinstance(source_raw, dict):
                url = source_raw.get("url", source_raw.get("path", ""))
                source_type = source_raw.get("source", "")
            elif isinstance(source_raw, str):
                url = source_raw
                source_type = source_raw
            else:
                url = ""
                source_type = ""
            install_loc = mp_data.get("installLocation", "")
            mp_path = CLAUDE_DIR / install_loc if install_loc else None

            skills = []
            if mp_path and mp_path.exists():
                for d in sorted(mp_path.iterdir()):
                    if d.is_dir():
                        skill_file = d / "SKILL.md"
                        skills.append({
                            "name": d.name,
                            "installed": d.name in installed_names,
                            "hasSkillMd": skill_file.exists(),
                            "size": self._dir_size(d),
                        })

            result.append({
                "name": mp_name,
                "source": source_raw,
                "sourceType": source_type,
                "url": url,
                "installLocation": install_loc,
                "lastUpdated": mp_data.get("lastUpdated", ""),
                "skills": skills,
                "skillCount": len(skills),
            })

        self._send_json({"marketplaces": result})

    # ==================== SESSION RENAME ====================

    def h_rename_session(self, body):
        project = body.get("project", "")
        session_id = body.get("sessionId", "")
        title = body.get("title", "")
        if not project or not session_id:
            self._send_error("project and sessionId required", 400)
            return

        titles_file = CLAUDE_DIR / "projects" / project / "session-titles.json"
        titles = {}
        if titles_file.exists():
            try:
                titles = json.loads(titles_file.read_text(encoding="utf-8"))
            except Exception:
                titles = {}

        if title:
            titles[session_id] = title
        elif session_id in titles:
            del titles[session_id]

        try:
            self._write_json(f"projects/{project}/session-titles.json", titles)
            self._send_json({"ok": True, "title": title})
        except Exception as e:
            self._send_error(str(e), 500)

    def _get_session_titles(self, project):
        """Read custom session titles for a project."""
        titles_file = CLAUDE_DIR / "projects" / project / "session-titles.json"
        if titles_file.exists():
            try:
                return json.loads(titles_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    # ==================== OPEN FOLDER ====================

    def h_open_folder(self, body):
        rel_path = body.get("path", "")
        if not rel_path:
            self._send_error("path required", 400)
            return
        p = CLAUDE_DIR / rel_path
        # Safety: ensure within CLAUDE_DIR
        try:
            p.resolve().relative_to(CLAUDE_DIR.resolve())
        except ValueError:
            self._send_error("Access denied", 403)
            return
        if not p.exists():
            # Create it if it doesn't exist
            try:
                p.mkdir(parents=True, exist_ok=True)
            except Exception:
                self._send_error("Directory not found", 404)
                return

        try:
            sys_name = platform.system()
            if sys_name == "Windows":
                os.startfile(str(p))
            elif sys_name == "Darwin":
                subprocess.Popen(["open", str(p)])
            else:
                subprocess.Popen(["xdg-open", str(p)])
            self._send_json({"ok": True})
        except Exception as e:
            self._send_error(str(e), 500)


def main():
    server = http.server.HTTPServer((HOST, PORT), ClaudeAPIHandler)
    print(f"\n  CC CONFIG UI")
    print(f"  ----------------------------")
    print(f"  Server:   http://{HOST}:{PORT}")
    print(f"  Claude:   {CLAUDE_DIR}")
    print(f"  Press Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
