import os
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import datetime
from jinja2 import Template

def get_blog_card_template():
    """Return the template for a blog card with consistent styling."""
    return """
    <div class="col-12">
        <div class="row g-0 border rounded overflow-hidden flex-md-row mb-4 shadow-sm h-md-250 position-relative">
            <div class="col p-4 d-flex flex-column position-static">
                <a href="{{ blog_url }}" class="icon-link gap-1 icon-link-hover stretched-link">
                    <h3 class="mb-0">{{ title }}</h3>
                </a>
            </div>
            <div class="col-auto d-none d-lg-block">
                <img class="rounded" width="120" height="80" src="{{ image_url }}" alt="{{ image_alt }}" />
            </div>
        </div>
    </div>
    """

def get_category_index_template():
    """Return the template for the category index page."""
    return """
    <!DOCTYPE html>
    <html class="no-js" lang="en">
        <head>
            <title>{{ category_title }} - Securade.ai</title>
            <meta charset="utf-8" />
            <meta http-equiv="x-ua-compatible" content="ie=edge" />
            <meta name="description" content="{{ category_description }}">
            <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no" />
            <!-- Include your standard header content here -->
        </head>
        <body>
            <!-- Include your standard navigation here -->
            <section id="category-blogs" class="feature-section">
                <div class="container">
                    <div class="row mb-2">
                        <h1 class="fw-bolder mb-1">{{ category_title }}</h1>
                        {{ blog_cards }}
                    </div>
                </div>
            </section>
            <!-- Include your standard footer here -->
        </body>
    </html>
    """

def create_or_update_category_index(category, blog_info, repo_root):
    """Create or update the category index page with the new blog."""
    category_path = repo_root / "blog" / category
    index_path = category_path / "index.html"
    
    # Ensure category directory exists
    category_path.mkdir(parents=True, exist_ok=True)
    
    blogs = []
    
    # Get existing blogs if index exists
    if index_path.exists():
        with open(index_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')
            existing_cards = soup.find_all('div', class_='col-12')
            for card in existing_cards:
                link = card.find('a')
                if link:
                    title = link.find('h3').text.strip()
                    url = link['href']
                    img = card.find('img')
                    image_url = img['src'] if img else ''
                    image_alt = img['alt'] if img else ''
                    blogs.append({
                        'title': title,
                        'url': url,
                        'image_url': image_url,
                        'image_alt': image_alt,
                        'date': datetime.now()  # You might want to extract this from the existing card
                    })
    
    # Add new blog to the list
    blogs.append({
        'title': blog_info['title'],
        'url': f"/{blog_info['path']}",
        'image_url': f"/{blog_info['image_path']}",
        'image_alt': blog_info['image_alt'],
        'date': datetime.now()
    })
    
    # Sort blogs by date, newest first
    blogs.sort(key=lambda x: x['date'], reverse=True)
    
    # Create blog cards HTML
    card_template = Template(get_blog_card_template())
    blog_cards_html = ""
    for blog in blogs:
        blog_cards_html += card_template.render(
            blog_url=blog['url'],
            title=blog['title'],
            image_url=blog['image_url'],
            image_alt=blog['image_alt']
        )
    
    # Create or update index page
    index_template = Template(get_category_index_template())
    index_html = index_template.render(
        category_title=category.replace('-', ' ').title(),
        category_description=f"Latest blog posts about {category.replace('-', ' ')} from Securade.ai",
        blog_cards=blog_cards_html
    )
    
    # Save index page
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(index_html)
    
    return str(index_path.relative_to(repo_root))

def update_category_indexes(repo, branch_name, blog_info):
    """Update category index pages in the repository."""
    try:
        # Get the category index path
        index_path = create_or_update_category_index(
            blog_info['category'],
            blog_info,
            Path(os.getcwd())
        )
        
        # Commit updated index to the repository
        with open(index_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Create or update the file in the repository
        try:
            # Try to get existing file
            repo.get_contents(index_path, ref=branch_name)
            # File exists, update it
            repo.update_file(
                path=index_path,
                message=f"Update category index for {blog_info['category']}",
                content=content,
                branch=branch_name,
                sha=repo.get_contents(index_path, ref=branch_name).sha
            )
        except:
            # File doesn't exist, create it
            repo.create_file(
                path=index_path,
                message=f"Create category index for {blog_info['category']}",
                content=content,
                branch=branch_name
            )
            
    except Exception as e:
        print(f"Error updating category index: {e}")
        raise