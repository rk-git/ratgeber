
"""
cli.py - Ratgeber CLI end user interface

Prompts user, receives the user query and relays it to pipeline

copyright (c) 2026 Always Up Networks. MIT License.
"""

import logging

from src.rag.pipeline import pipeline

RATGEBER_BANNER = """
Ratgeber DRBD and Linstor configuration advisor.
copyright 2026, MIT License
"""

RATGEBER_PROMPT = "Ratgeber> "


def cli():
    logging.basicConfig(level=logging.INFO)
    print(RATGEBER_BANNER)

    messages = []  # conversation history grows here

    quit = False
    while not quit:
        user_query = input(RATGEBER_PROMPT)
        logging.info(f"user query = {user_query}")

        if user_query.lower() in ('quit', 'exit', 'q'):
            quit = True
        else:
            response, messages = pipeline(user_query, messages)
            print(f"\n{response}\n")

    logging.info("*** Goodbye ***")
    
if __name__ == "__main__":
    cli()

