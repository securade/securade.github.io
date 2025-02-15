import os
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import datetime
from jinja2 import Template, Environment, FileSystemLoader

def get_blog_card_template():
    """Return the template for a blog card with consistent styling."""
    return """
    <div class="col-12">
        <div class="row g-0 border rounded overflow-hidden flex-md-row mb-4 shadow-sm h-md-250 position-relative">
            <div class="col p-4 d-flex flex-column position-static">
                <a href="./{{ blog_url }}" class="icon-link gap-1 icon-link-hover stretched-link">
                    <h3 class="mb-0">{{ title }}</h3>
                </a>
            </div>
            <div class="col-auto d-none d-lg-block">
                <img class="rounded" width="120" height="80" src="../../../{{ image_url }}" alt="{{ image_alt }}" />
            </div>
        </div>
    </div>
    """

def find_repo_root():
    """Find the repository root by looking for specific markers in securade.github.io repo."""
    current = Path(os.getcwd()).absolute()
    print(f"Current working directory: {current}")
    
    # Start with current directory
    if current.name == 'securade.github.io':
        print(f"Found repo root at current directory: {current}")
        return current
        
    # Check if we're in the scripts directory
    if current.name == 'scripts' and current.parent.name == 'securade.github.io':
        print(f"Found repo root from scripts directory: {current.parent}")
        return current.parent
        
    # Try parent directory if it's the repo root
    if current.parent.name == 'securade.github.io':
        print(f"Found repo root in parent directory: {current.parent}")
        return current.parent
    
    # If we can't find it in standard locations, search upwards for securade.github.io
    parent = current
    while parent != parent.parent:
        if parent.name == 'securade.github.io':
            print(f"Found repo root by searching upwards: {parent}")
            return parent
        parent = parent.parent
    
    # If we still haven't found it, raise an error
    raise ValueError(f"Could not find securade.github.io repository root from {current}")

def get_template_path():
    """Get the path to the blog template."""
    repo_root = find_repo_root()
    print(f"Checking for templates in: {repo_root}/templates")
    
    template_path = repo_root / 'templates'
    if not template_path.exists():
        raise ValueError(f"Template directory not found at {template_path}")
    
    # Verify template file exists
    template_file = template_path / 'blog_template.html'
    if not template_file.exists():
        raise ValueError(f"blog_template.html not found at {template_path}")
        
    print(f"Found template at: {template_file}")
    return template_path

def create_or_update_category_index(category, blog_info, repo_root=None):
    """Create or update the category index page with the new blog."""
    if repo_root is None:
        repo_root = find_repo_root()
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
    # Get just the filename from the full path for the blog URL
    blog_filename = os.path.basename(blog_info['path'])
    
    # For image path, preserve the full path from assets
    image_path = blog_info['image_path']
    if image_path.startswith('/'):
        image_path = image_path[1:]  # Remove leading slash if present
        
    blogs.append({
        'title': blog_info['title'],
        'url': blog_filename,  # Just the filename since we're in the category directory
        'image_url': image_path,  # Full path from root but without leading slash
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
    
    # Get the template path and verify it exists
    template_path = get_template_path()
    print(f"Using template path for category index: {template_path}")
    
    # Create environment with template loader
    env = Environment(loader=FileSystemLoader(str(template_path)))
    try:
        template = env.get_template('blog_template.html')
        print("Successfully loaded blog_template.html")
    except Exception as e:
        print(f"Error loading template: {e}")
        print(f"Template path contents: {list(template_path.glob('*'))}")
        raise
    
    # Create category title and description
    category_title = category.replace('-', ' ').title()
    category_description = f"Latest blog posts about {category.replace('-', ' ')} from Securade.ai"
    
    # Create the main content section
    main_content = f"""
    <section class="mb-5">
        <h1 class="fw-bolder mb-1">{category_title}</h1>
        <div class="row mb-2">
            {blog_cards_html}
        </div>
    </section>
    """
    
    # Render the full page using the blog template
    index_html = template.render(
        title=f"{category_title} - Securade.ai",
        meta_description=category_description,
        keywords=f"{category}, securade, ai, safety, workplace safety",
        og_title=f"{category_title} - Securade.ai Blogs",
        og_description=category_description,
        content=main_content,
        date=datetime.now().strftime('%B %d, %Y'),
        author="Securade.ai",
        image_url="/assets/images/logo/logo.png",
        image_alt="Securade.ai Logo",
        css_classes={
            'body_content': 'col-lg-8 mx-auto',
            'article_header': 'mb-4',
            'title': 'fw-bolder mb-1',
            'meta': 'text-muted fst-italic mb-2',
            'figure': 'mb-4',
            'image': 'img-fluid rounded'
        }
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
            file = repo.get_contents(index_path, ref=branch_name)
            # File exists, update it
            repo.update_file(
                path=index_path,
                message=f"Update category index for {blog_info['category']}",
                content=content,
                branch=branch_name,
                sha=file.sha
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