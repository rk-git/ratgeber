
"""
cli.py - Ratgeber CLI end user interface

Prompts user, receives the user query and relays it to pipeline

copyright (c) 2026 Always Up Networks. MIT License.
"""

import logging
import os
from src.utils.utils import extract_topology, draw_topology
from rich.console import Console
from rich.markdown import Markdown
from src.rag.pipeline import pipeline

RATGEBER_BANNER = """
Ratgeber DRBD and Linstor configuration advisor.
copyright (c) 2026 Always Up Networks LLC. MIT License.
"""

RATGEBER_PROMPT = "Ratgeber> "
RATGEBER_END = "*** Goodbye ***"


def cli():
    logging.basicConfig(level=logging.ERROR)
    console = Console()
    os.system('clear')
    console.print("[bold green]Ratgeber>[/bold green]")
    console.print(RATGEBER_BANNER, style="bold red italic")
    messages = []  # conversation history grows here

    quitloop = False
    while not quitloop:
        console.print("[bold cyan]Ratgeber>[/bold cyan] ", end="")
        user_query = input()        #logging.info(f"user query = {user_query}")

        user_query = user_query.strip()
        if not user_query:
            continue
        if user_query.lower() in ('quit', 'exit', 'q'):
            quitloop = True
        else:
            with console.status("[yellow]Working...[/yellow]"):
                response, messages = pipeline(user_query, messages)

            #console.print("[bold green] [/bold green]")
            clean_text, topology = extract_topology(response)
            console.print()
            console.print(Markdown(clean_text))
            if topology:
                print()
                console.print("[bold yellow]Topology:[/bold yellow]")
                draw_topology(topology)

            console.print("---")
            console.print()

    console.print(RATGEBER_END)

if __name__ == "__main__":
    cli()

