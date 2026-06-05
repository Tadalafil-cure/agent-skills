# Agent Skills

A curated collection of installable skill protocols for AI agents — self-contained patches that extend agent capabilities. Drop in, reload, run.

## Skills

| Skill | Description |
|-------|-------------|
| [Holographic Enhanced Memory Protocol](./holographic-enhanced-memory-protocol/) | System-level enforced memory hooks + hot/warm/cold gradient memory. Mechanically enhanced edition of Hermes' native holographic plugin. Zero new dependencies. |

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
