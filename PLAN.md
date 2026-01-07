# MCP Memoria - Piano di Implementazione

## Executive Summary

**MCP Memoria** è un server MCP (Model Context Protocol) locale che fornisce memoria persistente illimitata per Claude Code e Claude Desktop, utilizzando **Qdrant** per lo storage vettoriale e **Ollama** per gli embeddings locali. Zero dipendenze cloud, zero limiti di storage, 100% privacy.

### Differenziazione rispetto a Memvid e alternative

| Caratteristica | MCP Memoria | Memvid | Mem0 | LangChain Memory |
|----------------|-------------|--------|------|------------------|
| **Storage locale** | ✅ Qdrant locale | File .mv2 | Cloud/Self-host | Richiede config |
| **Embeddings** | ✅ Ollama locale | Integrato | OpenAI/locale | OpenAI/locale |
| **Limiti storage** | ✅ Illimitato | 50MB free tier | Variabile | Variabile |
| **Privacy** | ✅ 100% locale | Parziale | Cloud default | Variabile |
| **MCP nativo** | ✅ Sì | No | No | No |
| **Costo** | ✅ €0 | Freemium | Freemium | Variabile |

---

## Architettura del Sistema

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Claude Code / Desktop                         │
│                              (MCP Client)                            │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ MCP Protocol (stdio)
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         MCP MEMORIA SERVER                           │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │    Tools     │  │  Resources   │  │   Prompts    │              │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤              │
│  │ store_memory │  │ memories://  │  │ recall_ctx   │              │
│  │ recall       │  │ stats://     │  │ summarize    │              │
│  │ search       │  │ collections/ │  │ relate       │              │
│  │ update       │  │ exports://   │  └──────────────┘              │
│  │ delete       │  └──────────────┘                                 │
│  │ consolidate  │                                                    │
│  │ export/import│                                                    │
│  └──────────────┘                                                    │
├─────────────────────────────────────────────────────────────────────┤
│                        MEMORY MANAGER                                │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │ │
│  │  │  Episodic   │  │  Semantic   │  │ Procedural  │            │ │
│  │  │   Memory    │  │   Memory    │  │   Memory    │            │ │
│  │  │ (eventi)    │  │ (fatti)     │  │ (skills)    │            │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘            │ │
│  │                                                                 │ │
│  │  ┌─────────────────────────────────────────────────────────┐  │ │
│  │  │                  Working Memory                          │  │ │
│  │  │     (contesto sessione corrente, cache LRU)             │  │ │
│  │  └─────────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────┤
│                      EMBEDDING ENGINE                                │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                     Ollama Client                               │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │ │
│  │  │ nomic-embed │  │ mxbai-embed │  │ bge-m3      │            │ │
│  │  │    -text    │  │   -large    │  │ (multilang) │            │ │
│  │  │   (768d)    │  │   (1024d)   │  │   (1024d)   │            │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘            │ │
│  │                                                                 │ │
│  │  [Embedding Cache - SQLite per evitare ricalcoli]              │ │
│  └────────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────┤
│                       VECTOR STORE                                   │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                      Qdrant (locale)                            │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │ │
│  │  │  episodic   │  │  semantic   │  │ procedural  │            │ │
│  │  │ collection  │  │ collection  │  │ collection  │            │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘            │ │
│  │                                                                 │ │
│  │  [HNSW Index] [Payload Index] [Quantization]                   │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Struttura del Progetto

```
mcp-memoria/
├── pyproject.toml              # Configurazione progetto Python
├── README.md                   # Documentazione
├── LICENSE                     # Apache 2.0
│
├── src/
│   └── mcp_memoria/
│       ├── __init__.py
│       ├── __main__.py         # Entry point
│       ├── server.py           # MCP Server principale
│       │
│       ├── core/
│       │   ├── __init__.py
│       │   ├── memory_manager.py    # Gestione memoria multi-livello
│       │   ├── memory_types.py      # Tipi di memoria (Episodic, Semantic, etc.)
│       │   ├── working_memory.py    # Cache sessione corrente
│       │   └── consolidation.py     # Consolidamento e forgetting
│       │
│       ├── embeddings/
│       │   ├── __init__.py
│       │   ├── ollama_client.py     # Client Ollama per embeddings
│       │   ├── embedding_cache.py   # Cache SQLite per embeddings
│       │   └── chunking.py          # Text chunking intelligente
│       │
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── qdrant_store.py      # Interfaccia Qdrant
│       │   ├── collections.py       # Gestione collezioni
│       │   └── backup.py            # Export/Import
│       │
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── store_tool.py        # Tool: memorizzazione
│       │   ├── recall_tool.py       # Tool: recupero semantico
│       │   ├── search_tool.py       # Tool: ricerca avanzata
│       │   ├── manage_tool.py       # Tool: update/delete
│       │   └── export_tool.py       # Tool: export/import
│       │
│       ├── resources/
│       │   ├── __init__.py
│       │   ├── memory_resource.py   # Resource: accesso memorie
│       │   └── stats_resource.py    # Resource: statistiche
│       │
│       ├── prompts/
│       │   ├── __init__.py
│       │   └── templates.py         # Prompt templates
│       │
│       └── config/
│           ├── __init__.py
│           ├── settings.py          # Configurazione
│           └── defaults.py          # Valori default
│
├── tests/
│   ├── __init__.py
│   ├── test_memory_manager.py
│   ├── test_embeddings.py
│   ├── test_storage.py
│   └── test_tools.py
│
├── docker/
│   ├── Dockerfile              # Container MCP Memoria
│   └── docker-compose.yml      # Stack completo (Qdrant + Ollama + MCP)
│
└── scripts/
    ├── install.sh              # Script installazione
    ├── setup_ollama.sh         # Setup modelli Ollama
    └── setup_qdrant.sh         # Setup Qdrant locale
```

---

## Componenti Dettagliati

### 1. MCP Tools

#### 1.1 `memoria_store` - Memorizzazione
```json
{
  "name": "memoria_store",
  "description": "Memorizza informazioni nel sistema di memoria persistente",
  "inputSchema": {
    "type": "object",
    "properties": {
      "content": {
        "type": "string",
        "description": "Contenuto da memorizzare"
      },
      "memory_type": {
        "type": "string",
        "enum": ["episodic", "semantic", "procedural"],
        "default": "episodic",
        "description": "Tipo di memoria"
      },
      "tags": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Tag per categorizzazione"
      },
      "importance": {
        "type": "number",
        "minimum": 0,
        "maximum": 1,
        "default": 0.5,
        "description": "Importanza del ricordo (0-1)"
      },
      "context": {
        "type": "object",
        "description": "Metadati contestuali (progetto, file, etc.)"
      }
    },
    "required": ["content"]
  }
}
```

#### 1.2 `memoria_recall` - Recupero Semantico
```json
{
  "name": "memoria_recall",
  "description": "Recupera ricordi rilevanti basandosi su similarità semantica",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "Query di ricerca"
      },
      "memory_types": {
        "type": "array",
        "items": {"type": "string", "enum": ["episodic", "semantic", "procedural"]},
        "default": ["episodic", "semantic", "procedural"],
        "description": "Tipi di memoria da cercare"
      },
      "limit": {
        "type": "integer",
        "default": 5,
        "description": "Numero massimo di risultati"
      },
      "min_score": {
        "type": "number",
        "default": 0.5,
        "description": "Score minimo di similarità"
      },
      "filters": {
        "type": "object",
        "description": "Filtri aggiuntivi (tags, date, etc.)"
      }
    },
    "required": ["query"]
  }
}
```

#### 1.3 `memoria_search` - Ricerca Avanzata
```json
{
  "name": "memoria_search",
  "description": "Ricerca avanzata con filtri e aggregazioni",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "Query semantica (opzionale)"
      },
      "filters": {
        "type": "object",
        "properties": {
          "tags": {"type": "array", "items": {"type": "string"}},
          "memory_type": {"type": "string"},
          "date_from": {"type": "string", "format": "date"},
          "date_to": {"type": "string", "format": "date"},
          "importance_min": {"type": "number"},
          "project": {"type": "string"}
        }
      },
      "sort_by": {
        "type": "string",
        "enum": ["relevance", "date", "importance", "access_count"],
        "default": "relevance"
      },
      "limit": {"type": "integer", "default": 10}
    }
  }
}
```

#### 1.4 `memoria_update` - Aggiornamento
```json
{
  "name": "memoria_update",
  "description": "Aggiorna una memoria esistente",
  "inputSchema": {
    "type": "object",
    "properties": {
      "memory_id": {"type": "string", "description": "ID della memoria"},
      "content": {"type": "string", "description": "Nuovo contenuto (opzionale)"},
      "tags": {"type": "array", "items": {"type": "string"}},
      "importance": {"type": "number"},
      "metadata": {"type": "object"}
    },
    "required": ["memory_id"]
  }
}
```

#### 1.5 `memoria_delete` - Eliminazione
```json
{
  "name": "memoria_delete",
  "description": "Elimina memorie per ID o filtro",
  "inputSchema": {
    "type": "object",
    "properties": {
      "memory_ids": {
        "type": "array",
        "items": {"type": "string"},
        "description": "IDs da eliminare"
      },
      "filter": {
        "type": "object",
        "description": "Filtro per eliminazione bulk"
      }
    }
  }
}
```

#### 1.6 `memoria_consolidate` - Consolidamento
```json
{
  "name": "memoria_consolidate",
  "description": "Consolida memorie simili e applica forgetting curve",
  "inputSchema": {
    "type": "object",
    "properties": {
      "similarity_threshold": {
        "type": "number",
        "default": 0.9,
        "description": "Soglia per merge memorie simili"
      },
      "forget_days": {
        "type": "integer",
        "default": 30,
        "description": "Giorni dopo cui applicare forgetting"
      },
      "min_importance": {
        "type": "number",
        "default": 0.3,
        "description": "Importanza minima per mantenere"
      },
      "dry_run": {
        "type": "boolean",
        "default": true,
        "description": "Simula senza eseguire"
      }
    }
  }
}
```

#### 1.7 `memoria_export` / `memoria_import` - Backup
```json
{
  "name": "memoria_export",
  "description": "Esporta memorie in formato portabile",
  "inputSchema": {
    "type": "object",
    "properties": {
      "format": {
        "type": "string",
        "enum": ["json", "jsonl", "parquet"],
        "default": "json"
      },
      "memory_types": {"type": "array", "items": {"type": "string"}},
      "include_vectors": {"type": "boolean", "default": false},
      "output_path": {"type": "string"}
    }
  }
}
```

---

### 2. MCP Resources

#### 2.1 `memories://{memory_type}` - Accesso Collezioni
```
URI: memories://episodic
URI: memories://semantic
URI: memories://procedural
URI: memories://all

Ritorna: Lista delle memorie nella collezione con metadati
```

#### 2.2 `memory://{id}` - Singola Memoria
```
URI: memory://uuid-della-memoria

Ritorna: Dettagli completi della memoria specifica
```

#### 2.3 `stats://overview` - Statistiche
```
URI: stats://overview
URI: stats://collections
URI: stats://usage

Ritorna: Statistiche di utilizzo, conteggi, dimensioni
```

---

### 3. Tipi di Memoria

#### 3.1 Episodic Memory (Memoria Episodica)
- **Cosa memorizza**: Eventi, conversazioni, interazioni specifiche
- **Use case**: "Cosa ho discusso ieri riguardo al bug X?"
- **Decay**: Graduale nel tempo se non acceduta
- **Metadata**: timestamp, session_id, project, user_action

#### 3.2 Semantic Memory (Memoria Semantica)
- **Cosa memorizza**: Fatti, concetti, conoscenza fattuale
- **Use case**: "Quali sono le best practices per questo progetto?"
- **Decay**: Minimo, conoscenza persistente
- **Metadata**: source, confidence, domain, last_verified

#### 3.3 Procedural Memory (Memoria Procedurale)
- **Cosa memorizza**: Procedure, workflow, pattern appresi
- **Use case**: "Come si esegue il deploy in questo progetto?"
- **Decay**: Nessuno se usata, rafforza con l'uso
- **Metadata**: steps, success_rate, last_executed, frequency

---

### 4. Working Memory

Cache in-memory per la sessione corrente:

```python
class WorkingMemory:
    """Memoria di lavoro per contesto immediato."""

    def __init__(self, max_size: int = 100, ttl_seconds: int = 3600):
        self.cache = LRUCache(max_size)
        self.ttl = ttl_seconds
        self.current_context = {}  # Progetto, file corrente, etc.

    def add_to_context(self, key: str, value: Any):
        """Aggiunge al contesto corrente."""
        self.current_context[key] = {
            "value": value,
            "timestamp": datetime.now()
        }

    def get_relevant_context(self) -> dict:
        """Ritorna il contesto rilevante per la query corrente."""
        return {k: v["value"] for k, v in self.current_context.items()
                if self._is_recent(v["timestamp"])}
```

---

### 5. Embedding Engine

#### Configurazione Modelli

```python
EMBEDDING_MODELS = {
    "fast": {
        "name": "all-minilm",
        "dimensions": 384,
        "max_context": 256,
        "use_case": "Prototipazione, ricerche veloci"
    },
    "balanced": {
        "name": "nomic-embed-text",
        "dimensions": 768,
        "max_context": 8192,
        "use_case": "Default, bilanciamento qualità/velocità"
    },
    "quality": {
        "name": "mxbai-embed-large",
        "dimensions": 1024,
        "max_context": 512,
        "use_case": "Massima precisione retrieval"
    },
    "multilingual": {
        "name": "bge-m3",
        "dimensions": 1024,
        "max_context": 8192,
        "use_case": "Supporto multilingue"
    }
}
```

#### Prefissi per Modello

```python
MODEL_PREFIXES = {
    "nomic-embed-text": {
        "query": "search_query: ",
        "document": "search_document: "
    },
    "mxbai-embed-large": {
        "query": "Represent this sentence for searching relevant passages: ",
        "document": ""
    }
}
```

---

### 6. Storage Configuration

#### Qdrant Collections

```python
COLLECTIONS_CONFIG = {
    "episodic": {
        "vectors": {
            "content": VectorParams(size=768, distance=Distance.COSINE)
        },
        "hnsw_config": HnswConfigDiff(m=16, ef_construct=100),
        "payload_indexes": ["timestamp", "tags", "project", "importance"]
    },
    "semantic": {
        "vectors": {
            "content": VectorParams(size=768, distance=Distance.COSINE)
        },
        "hnsw_config": HnswConfigDiff(m=32, ef_construct=200),  # Più preciso
        "payload_indexes": ["domain", "source", "confidence"]
    },
    "procedural": {
        "vectors": {
            "content": VectorParams(size=768, distance=Distance.COSINE)
        },
        "hnsw_config": HnswConfigDiff(m=16, ef_construct=100),
        "payload_indexes": ["category", "success_rate", "frequency"]
    }
}
```

---

## Piano di Implementazione

### Fase 1: Foundation (Core Infrastructure)

#### 1.1 Setup Progetto
- [ ] Inizializzare progetto Python con `pyproject.toml`
- [ ] Configurare struttura directory
- [ ] Setup testing framework (pytest)
- [ ] Configurare linting (ruff) e type checking (mypy)

#### 1.2 Embedding Engine
- [ ] Implementare `OllamaClient` con retry e error handling
- [ ] Implementare `EmbeddingCache` con SQLite
- [ ] Implementare `TextChunker` per splitting intelligente
- [ ] Test unitari per embedding engine

#### 1.3 Storage Layer
- [ ] Implementare `QdrantStore` wrapper
- [ ] Implementare gestione collezioni
- [ ] Implementare CRUD operations base
- [ ] Test unitari per storage layer

### Fase 2: Memory System

#### 2.1 Memory Types
- [ ] Implementare `EpisodicMemory` class
- [ ] Implementare `SemanticMemory` class
- [ ] Implementare `ProceduralMemory` class
- [ ] Implementare `WorkingMemory` cache

#### 2.2 Memory Manager
- [ ] Implementare `MemoryManager` centrale
- [ ] Implementare logica di consolidamento
- [ ] Implementare forgetting curve
- [ ] Implementare access tracking (rafforza con l'uso)

### Fase 3: MCP Server

#### 3.1 Server Base
- [ ] Setup MCP server con stdio transport
- [ ] Implementare handler lifecycle
- [ ] Configurare logging e error handling

#### 3.2 Tools Implementation
- [ ] Implementare `memoria_store` tool
- [ ] Implementare `memoria_recall` tool
- [ ] Implementare `memoria_search` tool
- [ ] Implementare `memoria_update` tool
- [ ] Implementare `memoria_delete` tool
- [ ] Implementare `memoria_consolidate` tool
- [ ] Implementare `memoria_export` / `memoria_import` tools

#### 3.3 Resources Implementation
- [ ] Implementare resource `memories://`
- [ ] Implementare resource `memory://{id}`
- [ ] Implementare resource `stats://`

### Fase 4: Integration & Testing

#### 4.1 Integration Tests
- [ ] Test end-to-end del workflow completo
- [ ] Test di performance con dataset realistici
- [ ] Test di resilienza (crash recovery, concurrent access)

#### 4.2 Documentation
- [ ] README completo con esempi
- [ ] Documentazione API
- [ ] Guida di configurazione

### Fase 5: Deployment & Distribution

#### 5.1 Packaging
- [ ] Build package PyPI
- [ ] Dockerfile per deployment containerizzato
- [ ] Docker Compose per stack completo

#### 5.2 Installation Scripts
- [ ] Script setup Ollama con modelli
- [ ] Script setup Qdrant locale
- [ ] Script configurazione Claude Code/Desktop

---

## Configurazione MCP

### Per Claude Code

```json
// ~/.claude/config.json
{
  "mcp_servers": {
    "memoria": {
      "command": "python",
      "args": ["-m", "mcp_memoria"],
      "env": {
        "QDRANT_PATH": "~/.mcp-memoria/qdrant",
        "OLLAMA_HOST": "http://localhost:11434",
        "EMBEDDING_MODEL": "nomic-embed-text",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

### Per Claude Desktop

```json
// ~/Library/Application Support/Claude/claude_desktop_config.json (macOS)
// %APPDATA%\Claude\claude_desktop_config.json (Windows)
{
  "mcpServers": {
    "memoria": {
      "command": "python",
      "args": ["-m", "mcp_memoria"],
      "env": {
        "QDRANT_PATH": "/path/to/qdrant/storage",
        "OLLAMA_HOST": "http://localhost:11434",
        "EMBEDDING_MODEL": "nomic-embed-text"
      }
    }
  }
}
```

---

## Dipendenze

```toml
[project]
name = "mcp-memoria"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    "mcp>=1.0.0",                    # MCP SDK
    "qdrant-client>=1.12.0",         # Qdrant client
    "ollama>=0.4.0",                 # Ollama client
    "pydantic>=2.0.0",               # Data validation
    "pydantic-settings>=2.0.0",      # Configuration
    "httpx>=0.27.0",                 # HTTP client async
    "aiosqlite>=0.20.0",             # Async SQLite for cache
    "numpy>=1.26.0",                 # Vector operations
    "rich>=13.0.0",                  # CLI output
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.0.0",
    "ruff>=0.4.0",
    "mypy>=1.10.0",
]
```

---

## Use Cases e Esempi

### Use Case 1: Memoria di Progetto

```
Claude: Sto lavorando sul progetto "e-commerce-api". Memorizza che
        usiamo FastAPI con SQLAlchemy e PostgreSQL.

[Tool: memoria_store]
→ Memorizzato in semantic memory con tags ["tech-stack", "e-commerce-api"]

...più tardi...

User: Che stack tecnologico usiamo?

[Tool: memoria_recall]
→ Recupera: "Il progetto e-commerce-api usa FastAPI con SQLAlchemy e PostgreSQL"
```

### Use Case 2: Ricordo di Decisioni

```
User: Abbiamo deciso di usare JWT invece di sessions perché
      dobbiamo supportare mobile.

[Tool: memoria_store]
→ Memorizzato in episodic memory con context del progetto corrente

...settimane dopo...

User: Perché usiamo JWT?

[Tool: memoria_recall]
→ Recupera la decisione originale con il contesto della motivazione
```

### Use Case 3: Procedure Apprese

```
User: Il deploy si fa con: git push origin main && ./deploy.sh production

[Tool: memoria_store] (procedural)
→ Memorizzato come procedura con steps

...

User: Come faccio il deploy?

[Tool: memoria_recall] (procedural)
→ Recupera la procedura completa
```

---

## Metriche di Successo

- **Latenza recall**: < 100ms per query tipica
- **Precisione retrieval**: > 90% relevance nei top-5 risultati
- **Storage efficiency**: Compressione > 80% vs raw text con embeddings
- **Uptime**: 99.9% disponibilità del server MCP
- **Memory footprint**: < 500MB RAM per 100K memorie

---

## Roadmap Futura

### v0.2.0 - Enhanced Features
- [ ] Graph memory per relazioni tra entità
- [ ] Hybrid search (dense + sparse vectors)
- [ ] Auto-tagging con LLM locale
- [ ] Web UI per gestione memorie

### v0.3.0 - Advanced Intelligence
- [ ] Memory synthesis (combina memorie correlate)
- [ ] Proactive recall (suggerisce memorie rilevanti)
- [ ] Time-aware retrieval (boost recency)
- [ ] Multi-user support con isolation

### v1.0.0 - Production Ready
- [ ] Clustering per scalabilità
- [ ] Encryption at rest
- [ ] Audit logging
- [ ] API REST complementare

---

## Risorse e Riferimenti

### Documentazione
- [MCP Specification](https://spec.modelcontextprotocol.io/)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [Ollama API](https://github.com/ollama/ollama/blob/main/docs/api.md)

### Progetti di Riferimento
- [Mem0](https://github.com/mem0ai/mem0) - Memory layer for AI
- [Memvid](https://github.com/memvid/memvid) - Portable AI memory
- [LangChain Memory](https://python.langchain.com/docs/concepts/memory/)

### Papers
- "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"
- "Memory Networks" (Facebook AI)
- "Episodic Memory in AI Systems"

---

*Piano creato il 2026-01-06*
*Progetto: MCP Memoria*
*Location: /home/alberto/dev/Memoria*
