#!/usr/bin/env python3
"""
Hugo frontmatter string attributes quote fixer
Script to add quotes to string attributes in frontmatter
"""

import os
import re
import glob
from pathlib import Path

def fix_frontmatter_quotes(content):
    """
    Add quotes to string attributes in frontmatter
    """
    lines = content.split('\n')
    in_frontmatter = False
    fixed_lines = []
    in_list = False
    
    for line in lines:
        # Detect frontmatter start/end
        if line.strip() == '---':
            in_frontmatter = not in_frontmatter
            in_list = False
            fixed_lines.append(line)
            continue
        
        if not in_frontmatter:
            fixed_lines.append(line)
            continue
        
        # Process lines within frontmatter
        # Match string attribute patterns
        # Single-value string attributes that need quotes
        string_attr_pattern = r'^(\s*)(date|title|description|summary|type|url):\s*([^"\'\[\n].*)$'
        match = re.match(string_attr_pattern, line)
        
        if match:
            indent, attr_name, value = match.groups()
            # Trim the value
            value = value.strip()
            # Skip if already quoted
            if not (value.startswith('"') and value.endswith('"')) and not (value.startswith("'") and value.endswith("'")):
                fixed_line = f'{indent}{attr_name}: "{value}"'
                fixed_lines.append(fixed_line)
                print(f"  Fixed: {attr_name}: {value}")
            else:
                fixed_lines.append(line)
        else:
            # Check for list attributes (tags, categories)
            list_attr_pattern = r'^(\s*)(tags|categories):\s*$'
            list_match = re.match(list_attr_pattern, line)
            if list_match:
                in_list = True
                fixed_lines.append(line)
            # Check for list items
            elif in_list:
                list_item_pattern = r'^(\s*)-\s*([^"\'\n].*)$'
                item_match = re.match(list_item_pattern, line)
                if item_match:
                    indent, value = item_match.groups()
                    value = value.strip()
                    # Skip if already quoted
                    if not (value.startswith('"') and value.endswith('"')) and not (value.startswith("'") and value.endswith("'")):
                        fixed_line = f'{indent}- "{value}"'
                        fixed_lines.append(fixed_line)
                        print(f"  Fixed list item: {value}")
                    else:
                        fixed_lines.append(line)
                else:
                    # Not a list item, end of list
                    if line.strip() and not line.startswith(' ') and not line.startswith('\t'):
                        in_list = False
                    fixed_lines.append(line)
            else:
                fixed_lines.append(line)
    
    return '\n'.join(fixed_lines)

def process_markdown_files():
    """
    Process all Markdown files in the content directory
    """
    content_dir = Path('content')
    if not content_dir.exists():
        print("content directory not found")
        return
    
    # Search for all .md files in content directory
    md_files = list(content_dir.rglob('*.md'))
    
    print(f"Found {len(md_files)} Markdown files")
    
    for md_file in md_files:
        print(f"\nProcessing: {md_file}")
        
        try:
            # Read file
            with open(md_file, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            # Fix frontmatter
            fixed_content = fix_frontmatter_quotes(original_content)
            
            # Update file only if changes were made
            if original_content != fixed_content:
                with open(md_file, 'w', encoding='utf-8') as f:
                    f.write(fixed_content)
                print(f"  ✓ Fixed: {md_file}")
            else:
                print(f"  - No changes needed: {md_file}")
                
        except Exception as e:
            print(f"  ✗ Error: {md_file} - {e}")

if __name__ == "__main__":
    print("Starting frontmatter string attribute fix")
    process_markdown_files()
    print("\nFix completed!")
