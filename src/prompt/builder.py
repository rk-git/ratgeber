
"""
builder.py - Ratgeber prompt builder

Receives user query and retrieved context,
then builds the Ratgeber prompt.

copyright (c) 2026 Always Up Networks. MIT License.
"""

import logging


PROMPT_TEMPLATE = """CONTEXT FROM OFFICIAL LINBIT DOCUMENTATION:
{context}

---
Based ONLY on the context above, answer this question: {query}

If the context does not contain the answer, respond with exactly: "I don't have that information in my knowledge base."

Do not use any knowledge outside the context above.

If the question involves deployment topology, include a JSON block at the very end of your response in this exact format:

```topology
{{
    "nodes": [
        {{"name": "Node A", "role": "Primary", "state": "Active"}},
        {{"name": "Node B", "role": "Secondary", "state": "Standby"}}
    ],
    "links": [
        {{"from": "Node A", "to": "Node B", "type": "DRBD sync", "protocol": "C"}}
    ]
}}
```

ANSWER:"""


def build_ratgeber_prompt(
    context: str,
    query: str
) -> str:

    prompt = PROMPT_TEMPLATE.format(
        context=context,
        query=query
    )

    logging.info(
        "Built prompt with context length=%d and query='%s'",
        len(context),
        query
    )

    return prompt