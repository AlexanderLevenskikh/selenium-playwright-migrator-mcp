# P2: MCP/Skill structural-flow acceptance consumer

Stacked on MCP/Skill draft #56 exact parent `a9d7a121bb8480131a93a8c7237a3e9fcf7a6a57`. The two
unchanged Linux/Windows MCP CI jobs checkout the exact **Core P2 control-flow
draft #74** SHA `6f2155479822f6266ed1f25f2be97a65a17b3ee8`, build local NuGet packages and
exercise actual MCP stdio. This is not a general migration success gate.

## New protocol regression

A fictional NUnit source with guarded Click, else assertion,
try/catch/throw/finally is analyzed and previewed via MCP. An agent-edited
target retains all matching invocations but removes each structural path.
Actual `verify_artifact` must return `migrator-acceptance/v1`,
`rejected_incomplete`, missing `control_flow` entries with the exact
candidate/source/target identities, and `behavioralEquivalence=not_run`.

Preserved syntax shapes, including an inverted guard, MUST NOT become
`accepted`. The Agent Skill explicitly treats the new lineage as mandatory
debt. No user code is executed; smoke is a fictional fixture.

This does not validate equivalence of arguments, conditions, inherited
NUnit lifecycle, transitive POM call graphs, or source-target browser
observables. Original Windows P47 and Core issue #59 are unchanged.
No merge/release, no product-fix claim; validate the full exact-head
MCP 2-job matrix in addition to Core #74's 28-job matrix.
