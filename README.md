# Agent Skills

A curated collection of installable skill protocols for AI agents — self-contained patches that extend agent capabilities. Drop in, reload, run.

## Skills

| Skill | Description |
|-------|-------------|
| [Holographic Enhanced Memory Protocol](./holographic-enhanced-memory-protocol/) | **Mechanically enhanced edition** of Hermes-Agent's native holographic memory plugin. **Five core enhancements:** ① system-level enforced memory hooks (write/session/startup triple-anchor, agent cannot bypass) ② hot/warm/cold gradient memory system with tiered sinking and use-it-or-lose-it pruning ③ TF-IDF semantic retrieval replacing FTS5 keyword search (Chinese-aware tokenization, zero API calls) ④ radical lightness — all mechanical operations are code-driven, no new services or dependencies ⑤ L0/DB decoupling + WAL retry resilience (v2.5.1) — hot layer operates independently of warm layer, startup sinking always runs even when SQLite is unavailable. |

## Usage

```bash
# Clone into your skills directory
git clone git@github.com:Tadalafil-cure/agent-skills.git ~/.hermes/skills/agent-skills

# Or copy individual skills
cp -r agent-skills/holographic-enhanced-memory-protocol ~/.hermes/skills/
```

Then restart your agent. Skills are loaded at startup.

## Contributing

Each skill lives in its own directory with a `SKILL.md` file. PRs welcome.
