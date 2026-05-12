# CLI Reference

Hippocampus provides a command-line interface for managing setup, models, integrations, the server, and configuration.

## hippocampus setup

Prepare the default out-of-box environment. This initializes the workspace if needed, selects an embedding model by content language, selects a HuggingFace download source by network region, downloads the model, and verifies embedding.

```bash
hippocampus setup [--language auto|en|zh|multi] [--region auto|cn|global] [--profile default|fast|best]
```

`setup` does not start the server. Run `hippocampus start` afterwards.

## hippocampus init

Initialize a new Hippocampus workspace without network access. Creates the configuration file, SQLite database, and knowledge graph file in the workspace directory (default: `HIPPOCAMPUS_HOME` or `~/.hippocampus/`).

```bash
hippocampus init
```

**Options:**

| Option | Description |
|--------|-------------|
| `--dir DIR` | Target directory (default: `~/.hippocampus/`) |
| `--force` | Overwrite existing files |

## hippocampus model

Inspect or prefetch embedding models.

```bash
hippocampus model status
hippocampus model prefetch --model BAAI/bge-m3 --region cn
```

**Created files:**

- `hippocampus.json` -- configuration file
- `hippocampus.db` -- SQLite database
- `knowledge_graph.json` -- knowledge graph data

**Example:**

```bash
# Initialize in default workspace (~/.hippocampus/)
hippocampus init

# Initialize in a specific directory
hippocampus init --dir /path/to/project

# Re-initialize, overwriting existing files
hippocampus init --force
```

## hippocampus start

Start the Hippocampus server.

```bash
hippocampus start
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--host` | `0.0.0.0` | Bind address |
| `--port` | `8321` | Port number |
| `--reload` | -- | Enable auto-reload for development |

**Example:**

```bash
# Start with defaults
hippocampus start

# Start on a custom port
hippocampus start --port 9000

# Start in development mode with auto-reload
hippocampus start --reload
```

## hippocampus stop

Stop a running Hippocampus server.

```bash
hippocampus stop
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--url` | `http://localhost:8321` | Server URL to stop |

**Example:**

```bash
# Stop the default server
hippocampus stop

# Stop a server on a custom URL
hippocampus stop --url http://localhost:9000
```

## hippocampus restart

Restart the Hippocampus server.

```bash
hippocampus restart
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--host` | `0.0.0.0` | Bind address |
| `--port` | `8321` | Port number |
| `--reload` | -- | Enable auto-reload for development |

**Example:**

```bash
hippocampus restart
hippocampus restart --port 9000 --reload
```

## hippocampus status

Check the health and status of the running server, including scheduler information.

```bash
hippocampus status
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--url` | `http://localhost:8321` | Server URL to check |

**Example:**

```bash
hippocampus status
hippocampus status --url http://localhost:9000
```

**Sample output:**

```
Hippocampus v0.1.0
Status: running
Workspace: /home/user/.hippocampus
Storage: sqlite
Embedding: enabled
Consolidation: next run in 42m
Forgetting: next run in 12m
```

## hippocampus workspace

Show the resolved workspace directory. This is where Hippocampus stores all data files (`hippocampus.db`, `knowledge_graph.json`).

```bash
hippocampus workspace
```

The workspace is resolved in the following order:

1. `HIPPOCAMPUS_HOME` environment variable
2. `home` field in `hippocampus.json`
3. Parent directory of `hippocampus.json`
4. `~/.hippocampus/` (default)

**Example:**

```bash
hippocampus workspace
# Output: /home/user/.hippocampus

# Override via environment variable
export HIPPOCAMPUS_HOME=/data/memories
hippocampus workspace
# Output: /data/memories
```

## hippocampus config

Manage configuration via CLI subcommands.

### config list

Display all configuration values (sensitive values are masked).

```bash
hippocampus config list
```

### config get

Get the value of a specific configuration field. The computed property `workspace` is derived from the workspace directory and cannot be set directly.

```bash
hippocampus config get llm_model
# Output: openai/gpt-4o-mini

# Computed property (derived from workspace)
hippocampus config get workspace
# Output: /home/user/.hippocampus
```

### config set

Set a configuration value. The change is saved to `hippocampus.json` immediately.

```bash
hippocampus config set llm_api_key sk-your-key-here
hippocampus config set port 9000
hippocampus config set embedding_enabled false
```

### config path

Display the path to the active `hippocampus.json` file.

```bash
hippocampus config path
# Output: /home/user/project/hippocampus.json
```
