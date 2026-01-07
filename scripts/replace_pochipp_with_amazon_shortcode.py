#!/usr/bin/env python3
"""
Add Amazon shortcodes to Hugo markdown files based on Pochipp data from WordPress XML export
"""

import csv
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional

def load_product_data(csv_file: Path) -> Dict[str, Dict[str, str]]:
    """Load product data from CSV file, indexed by product_id"""
    products = {}
    
    if not csv_file.exists():
        print(f"Error: {csv_file} not found")
        return products
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        
        for row in reader:
            product_id = row.get('product_id', '')
            if product_id:
                products[product_id] = row
    
    return products

def extract_pochipp_from_xml(xml_file: Path) -> Dict[str, List[str]]:
    """Extract Pochipp shortcodes from WordPress XML export"""
    pochipp_data = {}
    
    if not xml_file.exists():
        print(f"Error: {xml_file} not found")
        return pochipp_data
    
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        # Find all items (posts)
        for item in root.findall('.//item'):
            # Get post slug
            post_name_elem = item.find('.//{http://wordpress.org/export/1.2/}post_name')
            if post_name_elem is None:
                continue
            
            post_slug = post_name_elem.text
            if not post_slug:
                continue
            
            # Get post content
            content_elem = item.find('.//{http://purl.org/rss/1.0/modules/content/}encoded')
            if content_elem is None:
                continue
            
            content = content_elem.text or ''
            
            # Find Pochipp shortcodes in content
            pochipp_pattern = r'<!-- wp:pochipp/linkbox \{"pid":(\d+).*?\} /-->'
            matches = re.findall(pochipp_pattern, content)
            
            if matches:
                pochipp_data[post_slug] = matches
                print(f"Found Pochipp in {post_slug}: PIDs {matches}")
    
    except ET.ParseError as e:
        print(f"Error parsing XML file: {e}")
    
    return pochipp_data

def generate_amazon_shortcode(product: Dict[str, str]) -> str:
    """Generate Amazon shortcode from product data"""
    asin = product.get('asin', '')
    title = product.get('product_name', '')
    
    if not asin or not title:
        return ''
    
    # Escape quotes in title
    title = title.replace('"', '\\"')
    
    return f'{{{{< amazon asin="{asin}" title="{title}" >}}}}'

def add_amazon_shortcode_to_file(file_path: Path, pids: List[str], products: Dict[str, Dict[str, str]]) -> bool:
    """Add Amazon shortcodes to a markdown file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if Amazon shortcodes already exist
        if '{{< amazon' in content:
            print(f"  Amazon shortcodes already exist in {file_path}")
            return False
        
        amazon_shortcodes = []
        for pid in pids:
            if pid in products:
                product = products[pid]
                shortcode = generate_amazon_shortcode(product)
                if shortcode:
                    amazon_shortcodes.append(shortcode)
        
        if not amazon_shortcodes:
            print(f"  No matching products found for PIDs: {pids}")
            return False
        
        # Find a good place to insert the shortcodes
        # Look for the end of the main content (before tables or at the end)
        lines = content.split('\n')
        insert_index = len(lines)
        
        # Try to find a table or the end of content
        for i, line in enumerate(lines):
            if line.strip().startswith('|') and '|' in line.strip():
                insert_index = i
                break
        
        # Insert Amazon shortcodes
        for shortcode in amazon_shortcodes:
            lines.insert(insert_index, '')
            lines.insert(insert_index + 1, shortcode)
            insert_index += 2
        
        # Write back to file
        new_content = '\n'.join(lines)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print(f"  Added {len(amazon_shortcodes)} Amazon shortcode(s)")
        return True
        
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def main():
    # Load product data
    csv_file = Path('exported/pochipp_products.csv')
    products = load_product_data(csv_file)
    
    if not products:
        print("No product data loaded. Exiting.")
        sys.exit(1)
    
    print(f"Loaded {len(products)} products from CSV")
    
    # Extract Pochipp data from XML
    xml_file = Path('exported/tatsshibata.WordPress.2026-01-05.xml')
    pochipp_data = extract_pochipp_from_xml(xml_file)
    
    if not pochipp_data:
        print("No Pochipp data found in XML. Exiting.")
        sys.exit(1)
    
    print(f"Found Pochipp data for {len(pochipp_data)} posts")
    
    # Find corresponding markdown files and add Amazon shortcodes
    content_dir = Path('content/posts')
    if not content_dir.exists():
        print(f"Error: {content_dir} not found")
        sys.exit(1)
    
    processed_files = 0
    
    for post_slug, pids in pochipp_data.items():
        # Find corresponding markdown file
        md_file = content_dir / post_slug / 'index.md'
        
        if md_file.exists():
            print(f"Processing: {md_file}")
            print(f"  PIDs: {pids}")
            
            if add_amazon_shortcode_to_file(md_file, pids, products):
                processed_files += 1
        else:
            print(f"Markdown file not found for {post_slug}")
    
    print(f"\nSummary:")
    print(f"  Processed {processed_files} files")
    print(f"  Total posts with Pochipp: {len(pochipp_data)}")

if __name__ == '__main__':
    main()
