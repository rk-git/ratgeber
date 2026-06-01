
"""
builder.py - Ratgeber prompt builder

Receives user query and retrieved context,
then builds the Ratgeber prompt.

copyright (c) 2026 Always Up Networks. MIT License.
"""

import logging


PROMPT_SYSTEM_TEMPLATE = """CONTEXT FROM OFFICIAL LINBIT DOCUMENTATION:
{context}

---
IMPORTANT: Always respond in the same language as the user's question. 
CRITICAL: Detect the language of the CURRENT question only. Ignore the language of previous questions. Each question must be answered in its own language independently.
Do not use any knowledge outside the context above.
If the context does not contain the answer, inform the user in their language that the information is not available in your knowledge base.
"""

PROMPT_USER_TEMPLATE = """
---
Answer this question: {query}

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

    prompt_system = PROMPT_SYSTEM_TEMPLATE.format(
        context=context
    )
    prompt_user = PROMPT_USER_TEMPLATE.format(
        query=query
    )

    logging.info(
        "Built prompt with context length=%d and query='%s'",
        len(context),
        query
    )

    return prompt_system, prompt_user