# Contributing

Start with the supported-profile table in the README and the format notes.
The highest-value contributions are additional verified format cases, synthetic
fixtures for unknown fields, and narrowly guarded compatibility improvements.

For a bug report, include the converter version, source/target game versions,
command, error message, and relevant aggregate report fields. Inspect generated
reports before sharing them. A private gameplay save is not required in a public
issue; never attach account configuration or authentication information.

For code changes:

1. Add a synthetic regression test that demonstrates the behavior.
2. Keep original save bytes immutable and refuse ambiguous data.
3. Run the complete `unittest` suite.
4. Document which cases were checked in the native game. A parser round-trip is
   useful evidence, but it does not prove a campaign can be played correctly.

Compatibility expansion should state its exact source/target builds and what
happens to skills or mechanics absent from 4.04. Avoid adding an unsafe force flag
to bypass unsupported state.
