
# Ratgeber

A DRBD/Linstor Configuration Advisor and Tutor — powered by LLM and RAG.

copyright (c) 2026 Always Up Networks. MIT License.

---

## What is Ratgeber?

Ratgeber (German: advisor, counselor) is an open source conversational tool that helps engineers configure, troubleshoot and learn Linbit technologies — DRBD, Linstor and Pacemaker.

You describe your problem in plain English or German. Ratgeber asks clarifying questions and responds with concrete configuration recommendations, topology diagrams and explanations — the way a seasoned Linbit engineer would.

## Two modes

**Configuration Advisor**
Describe your cluster requirements — nodes, replication, failover, cost constraints — and Ratgeber recommends a configuration tailored to your needs.

**Live Tutor**
Ask Ratgeber to explain DRBD replication modes, split brain, quorum, Linstor resource groups — anything. It teaches interactively, at your pace, in your language. It gets smarter as Linbit's documentation grows.

## Why Ratgeber?

Linbit's customers range from seasoned Linux cluster engineers to teams new to HA storage. Support calls spend too much time on configuration basics and concept explanations. Ratgeber handles those conversations so Linbit's engineers can focus on the hard problems.

## How it works

% ratgeber

Ratgeber>

Ratgeber runs locally on your infrastructure. No cloud dependency. No configuration data leaves your site.

```
[ Linbit Docs ]
      |
      | chunk + embed
      | (Sentence Transformers)
      v
[ ChromaDB ] \<=\=\=> [ LangChain ] \<=\=\=> [ Gemma via Ollama ] \<=\=\=> [ CLI ]
```

- ChromaDB — vector store holding chunked Linbit documentation
- LangChain — orchestrates retrieval and prompt construction
- Gemma via Ollama — on-prem LLM, no cloud, no API costs
- CLI — simple command line interface, English and German

## Status

Early prototype. Basic DRBD and Linstor configuration scenarios working. Tutor mode under development. Contributions welcome.

## Running locally

Coming soon.

## License

MIT License. See LICENSE file.
Always Up Networks, 2026.

---
