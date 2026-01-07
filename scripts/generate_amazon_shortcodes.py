#!/usr/bin/env python3
"""
Generate Amazon shortcode snippets from CSV data
"""

import csv
import sys
from pathlib import Path

def generate_shortcode(product):
    """Generate Amazon shortcode from product data"""
    asin = product.get('asin', '')
    title = product.get('product_name', '')
    image = product.get('image_url', '')
    price = product.get('price', '')
    description = product.get('product_info', '')
    
    # Clean up price (remove non-numeric characters except digits)
    if price:
        try:
            price = int(float(price))
        except (ValueError, TypeError):
            price = ''
    
    shortcode = f'{{{{< amazon asin="{asin}"'
    
    if title:
        shortcode += f' title="{title}"'
    
    if image:
        shortcode += f' image="{image}"'
    
    if price:
        shortcode += f' price="{price}"'
    
    if description:
        shortcode += f' description="{description}"'
    
    shortcode += ' >}}'
    
    return shortcode

def main():
    csv_file = Path('exported/pochipp_products.csv')
    
    if not csv_file.exists():
        print(f"Error: {csv_file} not found")
        sys.exit(1)
    
    print("# Amazon Shortcode Examples")
    print("# Copy and paste these into your markdown files\n")
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        
        for i, row in enumerate(reader):
            if i >= 10:  # Limit to first 10 products for example
                break
                
            shortcode = generate_shortcode(row)
            print(f"## {row.get('product_name', 'Unknown Product')}")
            print(f"```")
            print(shortcode)
            print(f"```\n")

if __name__ == '__main__':
    main()
