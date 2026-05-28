"""
utils.py - Ratgeber utility functions

Low level string and other utility functions

copyright (c) 2026 Always Up Networks. MIT License.
"""


import re
def strip_markdown(text: str) -> str:
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'#+\s', '', text)
    return text.strip()