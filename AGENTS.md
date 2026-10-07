# Working on this converter

Read `README.md`, `docs/format.md`, `docs/workflow.md`, and `docs/limitations.md`
before changing serialization behavior. This is a deliberately narrow experimental
workflow, not a universal downgrade promise.

- Keep every original input immutable. Outputs must use exclusive creation and
  refuse existing paths, including symlinks. Never silently write into live saves.
- Version headers alone are insufficient. Inventory record tails, enclosing
  lengths, name dictionaries and table pointers must remain consistent.
- Geralt and Ciri have different native skill definitions. Identify their owners;
  never select a character solely because its array appears first or second.
- Preserve items, quantities, equipment, facts and total skill points. Report
  native item-ID regeneration separately from actual loss.
- Unsupported state must fail with a clear error. Do not remove validation guards
  merely to make another sample produce a file.
- Public tests use synthetic bytes. Keep private saves, extracted data, game
  scripts, generated mods, screenshots, logs and connection details out of Git.
- Do not vendor a whole game script. The mod generator reads the user's installed
  file and inserts only this project's original snippet.
- Run `python -m unittest discover -v` and `python -m w3save --help` before claiming
  checks pass. A binary audit does not establish runtime compatibility.
- New compatibility claims require native loading, saving, and reloading without
  the migration mod. Describe tested checkpoints and remaining limits accurately.

The module interfaces and release checks are described in
`docs/implementation-plan.md`. Format research references are linked from the
README and format notes; distinguish observed layouts from hypotheses.
