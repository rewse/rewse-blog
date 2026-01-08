#!/bin/bash
# Add aliases to all posts for redirecting from old WordPress URLs

for dir in content/posts/*/; do
  slug=$(basename "$dir")
  file="$dir/index.md"
  
  if [ -f "$file" ]; then
    # Check if aliases already exists
    if grep -q "^aliases:" "$file"; then
      echo "Skipping $slug (aliases already exists)"
      continue
    fi
    
    # Add aliases after the date line
    sed -i '' '/^date:/a\
aliases:\
  - /blog/'"$slug"'/
' "$file"
    echo "Added alias to $slug"
  fi
done

echo "Done!"
