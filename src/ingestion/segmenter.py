"""
Segmenter Module
First stage of the Smart Ingestor pipeline.

This module provides functionality to transform raw lore text (from various sources)
into clean, logical segments (paragraphs, headings, scenes) suitable for downstream
processing.
"""

import logging
import re
from typing import List

logger = logging.getLogger(__name__)

def normalize_text(text: str) -> str:
    """
    Normalize raw text into a consistent form:
    - unify line endings
    - remove BOMs
    - strip trailing spaces on each line
    - collapse obvious control characters
    """
    if not text:
        return ""
    
    # Remove BOM
    text = text.replace('\ufeff', '')
    
    # Unify line endings to \n
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # Strip trailing whitespace on each line
    lines = [line.rstrip() for line in text.split('\n')]
    text = '\n'.join(lines)
    
    # Collapse control characters (keep tabs and newlines, remove others if possible)
    # Removing non-printable characters except newline and tab
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)

    # Collapse excessive blank lines (3+ -> 2)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text

def split_into_blocks(text: str) -> List[str]:
    """
    Split normalized text into coarse blocks using blank lines (double newlines)
    as primary separators.
    - Preserve ordering.
    - Drop blocks that are empty or whitespace-only.
    """
    if not text:
        return []
    # Regex for splitting by 2 or more newlines
    blocks = re.split(r'\n{2,}', text)
    return [b.strip() for b in blocks if b.strip()]

def is_heading(line: str) -> bool:
    """
    Return True if the line looks like a section heading.

    Heuristics:
    - If the stripped line is empty -> False
    - If the line ends with ':' and is not purely numeric -> True
    - If the line is at least 3 characters and:
        * has at least one alphabetic character, AND
        * after stripping punctuation, .isupper() is True
      then treat it as a heading.
    """
    line = line.strip()
    if not line:
        return False
        
    # Check if line ends with ':' and is not just numbers (e.g. timestamps or generic counters)
    if line.endswith(':'):
        content_before = line[:-1]
        # Check if content_before is purely numeric (ignoring spaces)
        if not content_before.replace(' ', '').isnumeric():
            return True
            
    # Check ALL CAPS heuristic
    # Must be at least 3 chars
    if len(line) < 3:
        return False
        
    # Must have at least one alphabetic char
    if not any(c.isalpha() for c in line):
        return False
        
    # Strip punctuation and check if isupper
    cleaned = re.sub(r'[^\w\s]', '', line)
    if cleaned.isupper():
        return True
        
    return False

def merge_soft_wrapped_lines(block: str) -> str:
    """
    Merge lines within a block that were soft-wrapped by the source (e.g. PDF export).

    Behavior:
    - Split by '\n'.
    - If a line does NOT end with sentence-ending punctuation ('.', '!', '?', ':')
      and the next line starts with a lowercase letter or is clearly a continuation,
      merge them with a space.
    - Preserve intentional hard breaks where possible (e.g. lists).
    """
    lines = block.split('\n')
    if len(lines) <= 1:
        return block
        
    merged_lines = []
    current_line = lines[0]
    
    for next_line in lines[1:]:
        stripped_current = current_line.strip()
        stripped_next = next_line.strip()
        
        if not stripped_current:
            merged_lines.append(current_line)
            current_line = next_line
            continue
            
        # Protect headings from being merged into
        if is_heading(stripped_current):
            merged_lines.append(current_line)
            current_line = next_line
            continue

        if not stripped_next:
            merged_lines.append(current_line)
            current_line = next_line
            continue
            
        # Check end of current line
        ends_with_punct = stripped_current[-1] in {'.', '!', '?', ':'}
        
        # Check start of next line
        starts_lowercase = stripped_next[0].islower()
        next_is_heading = is_heading(stripped_next)
        # Simple list detection: starts with "1.", "*", "-", etc.
        next_is_list = bool(re.match(r'^[\d\-\*\u2022]+\.?\s', stripped_next))

        # Decision logic:
        # Merge if NOT ending in punctuation AND (next starts lower OR (not heading AND not list))
        should_merge = (not ends_with_punct) and (starts_lowercase or (not next_is_heading and not next_is_list))
        
        if should_merge:
            current_line = current_line + " " + next_line.strip()
        else:
            merged_lines.append(current_line)
            current_line = next_line
            
    merged_lines.append(current_line)
    return '\n'.join(merged_lines)

def segment_text(text: str) -> List[str]:
    """
    High-level entry point for the segmenter.

    Steps:
    1. normalize_text(text)
    2. split_into_blocks(...)
    3. For each block:
       - run merge_soft_wrapped_lines
       - trim leading/trailing whitespace
       - if the block contains multiple headings + content, split so that:
            * each heading becomes its own segment
            * content following a heading stays as a separate segment
    4. Filter out segments that are too short to be useful (e.g. length < 10 chars after stripping),
       *unless* they are headings (keep headings even if short).
    5. Return the list of segments in original order.
    """
    if not text:
        return []
        
    logger.debug("Starting text segmentation.")
    
    normalized = normalize_text(text)
    raw_blocks = split_into_blocks(normalized)
    
    logger.debug(f"Initial blocks found: {len(raw_blocks)}")
    
    final_segments = []
    
    for block in raw_blocks:
        # Merge soft wraps first
        merged_block = merge_soft_wrapped_lines(block)
        
        # Split merged block into segments based on hard lines (preserved by merge_soft_wrapped_lines)
        # This handles both headings and list items/paragraphs correctly.
        lines = merged_block.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            final_segments.append(line)
            
    # Filter short segments
    filtered_segments = []
    for seg in final_segments:
        # Check length, but preserve headings
        if len(seg) >= 10 or is_heading(seg):
            filtered_segments.append(seg)
            
    logger.debug(f"Final segments generated: {len(filtered_segments)}")
    return filtered_segments

# --- Self-Check / Examples ---
#
# example_text = """
# CHAPTER ONE
# 
# The quick brown fox jumps over the lazy dog.
# This is a soft-wrapped line
# that should be merged.
# 
# SECTION 2: THE CONCLUSION
# 
# Here is a list:
# 1. Item one
# 2. Item two
# """
#
# Expected segments:
# [
#   "CHAPTER ONE",
#   "The quick brown fox jumps over the lazy dog. This is a soft-wrapped line that should be merged.",
#   "SECTION 2: THE CONCLUSION",
#   "Here is a list:",
#   "1. Item one",
#   "2. Item two"
# ]
#
# Note on "1. Item one" and "2. Item two": Since they are separated by a hard break and look like list items,
# merge_soft_wrapped_lines should preserve the break, and segment_text should return them as separate segments.
