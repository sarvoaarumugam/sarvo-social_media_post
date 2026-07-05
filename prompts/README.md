# Prompts

All AI prompts live here as **YAML files**, grouped by stage. You can read and
edit them without touching code, and edits take effect immediately (no restart).

Each file holds one or more named prompts. Placeholders use the `$name` form and
are filled in by the app at runtime — keep them intact and just change the wording
around them. (For a literal `$`, write `$$`.)

## Files

### `style_dna.yaml` — the retention principles (used by strategy AND script)
| Key | Used for | Placeholders |
|-----|----------|--------------|
| `dna` | The distilled "why top videos win" rules injected into both stages | — |

Upgrade it from real videos you admire: put their transcripts (.txt) in `references/`
and run `uv run python scripts/analyze_references.py`.

### `strategy.yaml` — stage 1: the Strategist (runs BEFORE the script)
| Key | Used for | Placeholders |
|-----|----------|--------------|
| `system` | Plans titles, thumbnail concept, hooks, outline with open loops, takeaway | `$brand`, `$host1`, `$host2`, `$language`, `$tone`, `$minutes`, `$target_words`, `$style_dna` |
| `user` | The topic ask | `$topic` |

### `script.yaml` — stage 2: the Scriptwriter (follows the blueprint)
| Key | Used for | Placeholders |
|-----|----------|--------------|
| `system` | The rules & style for writing the script | `$brand`, `$host1`, `$host2`, `$language`, `$tone`, `$target_words`, `$floor` |
| `user` | The actual ask sent with the topic | `$topic`, `$host1`, `$host2` |
| `expansion_system` | Used only if a draft is too short, to lengthen it | `$target_words`, `$floor` |
| `expansion_user` | Hands the short draft back for expansion | `$current_words`, `$target_words`, `$dialogue` |

### `audio.yaml` — the voice stage
| Key | Used for | Placeholders |
|-----|----------|--------------|
| `delivery` | How the voice should *speak* (de-robots the audio) | `$persona` |

### `image.yaml` — the cover-art stage
| Key | Used for | Placeholders |
|-----|----------|--------------|
| `generation` | First image, built from the topic | `$topic`, `$brand`, `$style` |
| `regeneration` | New image using your feedback | `$topic`, `$brand`, `$style`, `$feedback` |

## Where the placeholder values come from
- `$language`, `$tone`, `$persona` → settings/`.env`
  (`show_language`, `show_tone`, `tts_persona_host1`, `tts_persona_host2`).
- `$target_words` → derived from the requested duration (minutes × words-per-minute).
- `$floor` → the hard minimum word count (~90% of `$target_words`).
- `$topic`, `$host1`, `$host2` → the episode being generated.

## How it's loaded
`app/core/prompts.py` → `render("script", "system", brand=..., ...)`.
