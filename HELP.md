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

## `discover_trending_by_hashtag` — extra setup (optional)

This tool doesn't use yt-dlp. It calls a third-party Apify Actor over
HTTPS, so it needs its own credential:

1. Create a free Apify account at apify.com (no card required, $5/month
   free credit).
2. Apify Console -> Settings -> API & Integrations -> copy your API token.
3. Set it in your AI agent's MCP server config, same place as
   `IG_REEL_COOKIES`:
   `"env": { "APIFY_API_TOKEN": "apify_api_xxxxxxxx" }`

Honest status: the actor ID and field names in `server.py` are from
Apify's published docs as of November 2026. This repo's build
environment has no network path to apify.com, so this specific tool
has not been run against the live API from here. Run it once yourself
with a cheap `limit=3` before trusting it in a workflow, and recheck if
Apify or the actor's maintainer changes something.

If you'd rather not depend on a paid third party at all: skip this
tool. `fetch_instagram_reel` and `fetch_reel_transcript` need nothing
but yt-dlp and work exactly as documented.

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
