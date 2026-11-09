# HELP.md — using this on different AI coding tools

MCP is an open protocol. This server doesn't know or care which model is
on the other end of it — any MCP-capable client can call these tools.
"Does X AI support this?" is really a question about the *harness/CLI*
wrapping that model, not the model itself. Below is what's confirmed
working, checked November 2026 (this landscape moves fast — re-check if
something here looks stale).

## Claude Code

Add to `~/.claude.json` (all projects) or `.mcp.json` in the repo
(this project only):

```json
{
  "mcpServers": {
    "instagram-reel": {
      "command": "python",
      "args": ["/absolute/path/to/instagram-reel-mcp/server.py"]
    }
  }
}
```

Or via CLI: `claude mcp add instagram-reel -- python /absolute/path/to/server.py`

## OpenAI Codex CLI

Config lives at `~/.codex/config.toml`, shared with the Codex IDE
extension and desktop app. Add it with:

```bash
codex mcp add instagram-reel -- python /absolute/path/to/instagram-reel-mcp/server.py
```

Restart Codex, then check `/mcp` in the TUI or `codex mcp list` to confirm.

## Cursor

Add to `.cursor/mcp.json` (project) or `~/.cursor/mcp.json` (global) —
same JSON shape as Claude Code:

```json
{
  "mcpServers": {
    "instagram-reel": {
      "command": "python",
      "args": ["/absolute/path/to/instagram-reel-mcp/server.py"]
    }
  }
}
```

Restart Cursor fully after editing.

## Grok (xAI) — read this carefully, there are two different paths

- **Grok Build** (xAI's terminal coding agent) has native MCP support and
  runs stdio servers directly — any server config you already have for
  Claude Code works here with zero changes. This is the path that works
  for this server.
- **Raw xAI API "Remote MCP Tools"** only accepts **Streamable HTTP or
  SSE** servers, not stdio. This server is a local stdio process
  (FastMCP default), so it will **not** work if you try to wire it
  directly into the xAI API or the grok.com Connectors UI without first
  putting an HTTP bridge in front of it.

So: use Grok Build, not the raw API, unless you build that bridge.

## DeepSeek

DeepSeek doesn't ship an official first-party CLI with MCP support.
Community terminal agents built on the DeepSeek API do support MCP the
same way — e.g. **Whale** (`usewhale/DeepSeek-Code-Whale`). Install it,
then add this server to its MCP config using the same `mcpServers` JSON
shape as above (check that project's own `docs/mcp.md` for the exact
config file path, since community tools move their config locations
more often than first-party ones).

## Any other MCP-capable client

If a tool exposes an `mcpServers` JSON config or an "add MCP server"
command, point it at:

```json
{
  "command": "python",
  "args": ["/absolute/path/to/instagram-reel-mcp/server.py"]
}
```

If Instagram is asking for a login session, set the `IG_REEL_COOKIES`
env var in that client's MCP server config (`"env": {"IG_REEL_COOKIES": "/path/to/cookies.txt"}`)
rather than editing `server.py`.

## Using less credit / fewer tokens per call

There are three tools — pick the cheapest one that actually answers the
question:

| Tool | Cost | Use when |
|---|---|---|
| `fetch_instagram_reel` | lowest | you only need caption/counts/uploader |
| `fetch_reel_transcript` | low | question is about what was **said** — no images returned, no vision tokens |
| `analyze_instagram_reel` | highest | agent actually needs to **see** what's on screen |

Inside `analyze_instagram_reel`: read `contact_sheet_path` (one combined
grid image) first. Only open individual entries in `frames` if the
contact sheet isn't legible enough for the detail you need — that's the
difference between 1 vision call and up to 30.

Repeat calls on the same reel URL are served from local disk cache
automatically — no re-download, no re-transcription — unless you pass
`force_refresh=true` to `fetch_instagram_reel`.
