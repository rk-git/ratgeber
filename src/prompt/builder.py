
"""
builder.py - Ratgeber prompt builder

Receives user query and retrieved context,
then builds the Ratgeber prompt.

copyright (c) 2026 Always Up Networks. MIT License.
"""

import logging


PROMPT_TEMPLATE = """
You are Ratgeber, a DRBD and Linstor configuration advisor for Linbit.

Answer the user's question based ONLY on the context below.

If the context does not contain enough information
to answer confidently, say so.

Do not invent or hallucinate configurations,
commands, settings, or features not supported
by the context.

CONTEXT:
{context}

USER QUESTION:
{query}

ANSWER:
"""


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