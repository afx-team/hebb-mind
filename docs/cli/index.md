# CLI Reference

Hippocampus provides a command-line interface for managing the server and configuration.

## hippocampus init

Initialize a new Hippocampus project directory. Creates the configuration file, SQLite database, and knowledge graph file.

```bash
hippocampus init
```

**Options:**

| Option | Description |
|--------|-------------|
| `--dir DIR` | Target directory (default: current directory) |
| `--force` | Overwrite existing files |

**Created files:**

- `hippocampus.json` -- configuration file
- `hippocampus.db` -- SQLite database
- `knowledge_graph.json` -- knowledge graph data

**Example:**

```bash
# Initialize in current directory
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
Storage: sqlite
Embedding: enabled
Consolidation: next run in 42m
Forgetting: next run in 12m
```

## hippocampus config

Manage configuration via CLI subcommands.

### config list

Display all configuration values (sensitive values are masked).

```bash
hippocampus config list
```

### config get

Get the value of a specific configuration field.

```bash
hippocampus config get llm_model
# Output: openai/gpt-4o-mini
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
