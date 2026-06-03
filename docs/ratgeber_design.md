# RatGeber: Intelligent Configuration Advisor for DRBD and LINSTOR

**Always Up Networks LLC — 2026 — MIT License**
**https://github.com/rk-git/ratgeber/**

---

## Overview

DRBD and LINSTOR are powerful and flexible technologies — and that flexibility means
configuration decisions have real consequences. RatGeber (German: *advice giver*) is
an open-source, locally-run AI advisor that helps administrators get those decisions right.

RatGeber provides three core capabilities:

- **Configuration validation** — checks whether your configuration actually implements
  your intent, not just whether it is syntactically correct.
- **Log analysis** — identifies failure patterns in DRBD and LINSTOR logs and determines
  whether the root cause is configuration, network, or hardware.
- **Tutoring** — answers questions on advanced topics such as split brain, quorum,
  fencing, and protocol selection, at any level of expertise.

RatGeber speaks English and German, runs entirely on your own infrastructure, and never
sends your configuration data or logs to the cloud.

---

## System Architecture

```
  Administrator
       |
       | natural language query / config file / log file
       v
+----------------+
|   RatGeber     |  CLI interface (Python, Rich)
|   CLI          |
+----------------+
       |
       v
+----------------+      +-------------------------+
|   RAG          |----->|   ChromaDB              |
|   Pipeline     |      |   (vector store)        |
+----------------+      |   Official Linbit docs  |
       |                +-------------------------+
       | augmented prompt (query + retrieved context)
       v
+----------------+
|   Ollama       |
|   (local LLM)  |
|   Mistral      |
+----------------+
       |
       | response (language matched to user's query)
       v
  Administrator
```

All components run locally. No data leaves the administrator's machine.

---

## Configuration Validation

This is RatGeber's defining capability. Existing tools validate syntax. RatGeber
validates intent.

### The two-model framework

- **In-model (Intended Model):** Derived from the administrator's natural language
  description of their goal. What the administrator *wants* the cluster to do.
- **Im-model (Implemented Model):** Derived by parsing the actual DRBD/LINSTOR
  configuration files. What the configuration *actually* does.

### Validation stages

**Stage 0 — Syntactic and semantic parsing**
The configuration is parsed for correctness before any intelligent analysis begins.
Malformed configurations are rejected early with clear error messages.

**Stage 1 — Intent validation**
The In-model is checked against established best practices before it is compared to
the configuration. If the administrator's intent itself is problematic — for example,
requesting synchronous replication over a high-latency WAN link — RatGeber raises this
before proceeding. There is no value in validating a configuration against a flawed goal.

**Stage 2 — Topology generation and refinement**
RatGeber derives an intended topology from the In-model and presents it as an ASCII
diagram. The administrator can refine it interactively. This becomes the ground truth
for diff computation.

**Stage 3 — Three-way diff**

- **In-model minus Im-model:** Intent not reflected in the configuration. Things the
  administrator wants but has not configured. RatGeber suggests the missing elements.
- **Im-model minus In-model:** Configuration elements that directly oppose the
  administrator's intent. Flagged as errors requiring correction.
- **Benign differences:** Configuration elements that are neither required by the intent
  nor contradicting it. Reported as informational only.

### Example interaction

```
Ratgeber> validate --config /etc/drbd.d/storage.res

Describe your intended configuration goal:
> Three-node cluster, synchronous replication, automatic failover,
  quorum enabled to prevent split brain.

Draw your topology (or press ENTER to generate from intent):
> [ENTER]

Generating intended topology...

+----------------------+     +----------------------+     +----------------------+
| Node A               |     | Node B               |     | Node C               |
| Role: Primary        |     | Role: Secondary      |     | Role: Secondary      |
| State: Active        |     | State: Standby       |     | State: Standby       |
+----------------------+     +----------------------+     +----------------------+
     <== DRBD sync Protocol C ==>         <== DRBD sync Protocol C ==>

Does this topology match your intent? (yes/tweak): yes

Validating...

INTENT CHECK: Passed. Three-node synchronous replication with quorum
is a supported and recommended configuration.

MISSING (In-model - Im-model):
  - Quorum policy not defined. Your intent requires quorum but no
    'quorum' section exists in storage.res.
    Suggested addition:
      quorum {
          policy auto;
          quorum-device /dev/quorum;
      }

CONFLICT (Im-model - In-model):
  - Protocol A specified in storage.res. Synchronous replication
    requires Protocol C. Change: protocol A -> protocol C;

BENIGN:
  - Resync rate set to 50MB/s. Not required by your intent but
    does not conflict with it.
```

---

## Log Analysis

RatGeber accepts DRBD and LINSTOR log files — and optionally the configuration — and
identifies failure patterns. It distinguishes between configuration errors, network
issues, and storage failures, and explains the likely root cause in plain language.

The analysis answers a question that raw logs do not: *did this fail because of how
the cluster was configured, or because of what happened to the network or hardware?*

### Example interaction

```
Ratgeber> analyze --log /var/log/drbd.log --config /etc/drbd.d/storage.res

Analyzing...

ROOT CAUSE: Network partition on the replication interface between
node-a and node-b at 03:42:17. DRBD detected split brain at 03:42:19.

CONTRIBUTING FACTOR: No after-sb-1pri policy is defined in storage.res.
Without an automatic resolution policy, split brain requires manual
intervention. Consider adding:
  net {
      after-sb-1pri discard-secondary;
  }

CONFIGURATION STATUS: Otherwise healthy. The failure was caused by the
network event, not by a configuration error.
```

---

## Tutoring

RatGeber answers questions on advanced DRBD and LINSTOR topics at any level of
expertise — from an administrator new to replication to an experienced engineer
debugging a quorum edge case.

Topics include: split brain detection and resolution, quorum policies, fencing
strategies, protocol selection (A/B/C), Pacemaker integration, LINSTOR satellite
configuration, and storage pool management.

RatGeber responds in the language of the question. German prompt yields German
response. English prompt yields English response.

### Elementary example

```
Ratgeber> What is split brain in DRBD?

Split brain occurs when two DRBD nodes both assume the Primary role
simultaneously, typically because the replication link between them
was lost and each node continued accepting writes independently.
When the link is restored, DRBD detects that both nodes have diverged
and refuses to automatically reconcile them to avoid data loss...
```

### Advanced example

```
Ratgeber> In a three-node cluster with after-sb-1pri discard-secondary,
          what happens if the primary loses quorum but remains reachable
          by one secondary?

In this scenario, the primary has lost quorum (it can only see one of
two secondaries) but has not fully lost connectivity. DRBD's quorum
policy will demote the primary to secondary to preserve data integrity.
The secondary that remains connected to the former primary will...
```

---

## Design Principles

**Runs locally.** RatGeber uses Ollama with a local language model. Configuration
files, logs, and queries never leave the administrator's machine.

**Grounded in official documentation.** All answers are derived from official Linbit
documentation via Retrieval-Augmented Generation (RAG). RatGeber does not speculate
beyond its knowledge base. When information is not available, it says so explicitly.

**Open source.** MIT License. The code, the documentation corpus, and the prompt
design are all open for inspection and contribution.

---

## Caveats

RatGeber is early-stage software. Please keep the following in mind:

- Validation is as good as the retrieved documentation context. Unusual or
  undocumented configurations may produce incomplete analysis.
- Log analysis currently focuses on common failure patterns. Edge cases may not
  be recognized.
- The local language model (Mistral via Ollama) is capable but not infallible.
  Always verify RatGeber's suggestions against official Linbit documentation.
- RatGeber is an independent open-source project. It is not affiliated with or
  endorsed by Linbit.

---

## Contributing

RatGeber is at an early stage where community input matters most. If you use it,
break it, or have ideas for how to make it more useful to DRBD and LINSTOR
administrators, please open an issue or a pull request.

**GitHub:** https://github.com/rk-git/ratgeber/

Areas where contributions are especially welcome:

- Expanding the documentation corpus for better RAG retrieval
- Additional log pattern recognition
- Testing against real-world configurations and failure scenarios
- Docker packaging

---

*RatGeber — advice giver. For the administrators who keep storage alive.*
