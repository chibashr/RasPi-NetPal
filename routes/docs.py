from flask import Blueprint, render_template, send_from_directory, abort, redirect, url_for
import os
import codecs
import re
import json
import datetime

# Try to import markdown, but provide fallback if not available
try:
    import markdown
    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False
    print("Markdown package not available. Documentation will be displayed as raw text.")

bp = Blueprint('docs', __name__, url_prefix='/docs')

# Documentation files mapping
DOC_FILES = {
    'index': 'README.md',
    'architecture': 'Architecture.md',
    'components': 'Components.md',
    'installation': 'Installation.md',
    'usage': 'Usage.md',
    'about': 'About.md',
    'changelog': '_generated_' # Special marker for dynamically generated content
}

# Reverse mapping for lookups
MD_TO_ROUTE = {v.lower(): k for k, v in DOC_FILES.items() if not v.startswith('_')}

# Load version information
def load_version_info():
    """Load version information from version.json"""
    try:
        with open('version.json', 'r') as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error loading version.json: {e}")
        return {
            "version": "Unknown",
            "name": "Raspberry Pi Network Control Panel",
            "developer": "Unknown",
            "release_date": "Unknown",
            "changelog": []
        }

def generate_changelog_content():
    """Generate changelog markdown content from version.json"""
    version_info = load_version_info()
    
    # Start with the header
    content = "# Changelog\n\n"
    content += "This file documents all notable changes to the Raspberry Pi Network Control Panel.\n\n"
    
    # Add each version entry
    for entry in version_info.get('changelog', []):
        version = entry.get('version', 'Unknown')
        date = entry.get('date', 'Unknown date')
        
        content += f"## Version {version} ({date})\n\n"
        
        # Group changes by type if needed
        changes = entry.get('changes', [])
        if changes:
            content += "### Changes\n"
            for change in changes:
                content += f"- {change}\n"
            content += "\n"
    
    content += "_Note: This changelog is automatically generated from the version.json file._\n"
    
    return content

@bp.route('/')
def index():
    """Render the documentation index page."""
    return redirect(url_for('docs.show_doc', doc_name='index'))

@bp.route('/<doc_name>')
def show_doc(doc_name):
    """Render a specific documentation file."""
    # Remove .md extension if present
    doc_name = doc_name.replace('.md', '').lower()
    
    # Check if this is a markdown filename rather than a route name
    if doc_name in MD_TO_ROUTE:
        return redirect(url_for('docs.show_doc', doc_name=MD_TO_ROUTE[doc_name]))
    
    # Convert to lowercase for case-insensitive matching
    doc_name_lower = doc_name.lower()
    
    # Find the matching doc file
    matched_key = None
    for key in DOC_FILES.keys():
        if key.lower() == doc_name_lower:
            matched_key = key
            break
    
    if not matched_key:
        abort(404)
    
    # Special handling for dynamically generated content
    if DOC_FILES[matched_key].startswith('_generated_'):
        if matched_key.lower() == 'changelog':
            md_content = generate_changelog_content()
        else:
            abort(404)
    else:
        # Normal file reading
        doc_path = os.path.join('docs', DOC_FILES[matched_key])
        
        try:
            # Read the markdown file
            with codecs.open(doc_path, 'r', encoding='utf-8') as f:
                md_content = f.read()
        except IOError as e:
            return render_template(
                'docs.html',
                doc_name=doc_name,
                doc_files=DOC_FILES,
                content=f"<p>Error: Could not read documentation file: {str(e)}</p>"
            )
    
    # If it's the About page, inject version information
    if matched_key.lower() == 'about':
        version_info = load_version_info()
        md_content = md_content.replace('{{VERSION}}', version_info['version'])
    
    # Fix markdown links: change [text](file.md) to [text](/docs/route)
    if MARKDOWN_AVAILABLE:
        try:
            # Process links before converting to HTML
            def replace_md_links(match):
                link_text = match.group(1)
                link_target = match.group(2).lower()
                
                # If it's a markdown file, convert to route
                if link_target.endswith('.md'):
                    base_name = os.path.basename(link_target)
                    if base_name.lower() in MD_TO_ROUTE:
                        route_name = MD_TO_ROUTE[base_name.lower()]
                        return f'[{link_text}]({url_for("docs.show_doc", doc_name=route_name)})'
                
                return match.group(0)
            
            # Replace markdown links
            md_content = re.sub(r'\[(.*?)\]\((.*?\.md)\)', replace_md_links, md_content)
            
            html_content = markdown.markdown(md_content, extensions=['tables', 'fenced_code'])
        except Exception as e:
            html_content = f"<pre>Error rendering markdown: {str(e)}\n\n{md_content}</pre>"
    else:
        html_content = f"<pre>{md_content}</pre>"
    
    return render_template(
        'docs.html',
        doc_name=doc_name,
        doc_files=DOC_FILES,
        content=html_content
    ) 