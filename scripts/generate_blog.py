import os
import re
import json
import base64
from datetime import datetime
from pathlib import Path
import requests
from github import Github
from PIL import Image
from io import BytesIO
from openai import OpenAI
from slugify import slugify
from jinja2 import Template, Environment, FileSystemLoader

# Configure OpenAI client
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

MODEL = "gemini-2.0-flash-lite-preview-02-05"

def get_existing_categories():
    """Get list of existing blog categories from the blog directory."""
    blog_path = Path("blog")
    if not blog_path.exists():
        return []
    
    return [d.name for d in blog_path.iterdir() if d.is_dir()]

def analyze_content_for_category(title, description, existing_categories):
    """Analyze content to determine the most appropriate category."""
    categories_str = ", ".join(existing_categories) if existing_categories else "none"
    
    prompt = f"""Analyze this blog post and determine the most appropriate category.

Existing categories: {categories_str}

If the content doesn't fit well into any existing category, suggest a new category name that is concise and descriptive.

Consider:
1. The main topic and focus of the content
2. The target audience
3. The type of information being presented
4. How similar content is typically categorized

Title: {title}
Description: {description}

Return your response in this JSON format:
{{
    "category": "suggested-category-name",
    "is_new_category": boolean,
    "reasoning": "brief explanation of your choice"
}}"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a content categorization expert."},
                {"role": "user", "content": prompt}
            ],
            response_format={ "type": "json_object" }
        )
        
        return json.loads(response.choices[0].message.content)
    except json.JSONDecodeError:
        # Fallback if JSON parsing fails
        return {
            "category": "general",
            "is_new_category": len(existing_categories) == 0,
            "reasoning": "Fallback category due to processing error"
        }

def generate_blog_content(title, description, category):
    """Generate SEO-optimized blog content in structured format."""
    prompt = f"""Create a comprehensive, SEO-optimized blog post with the following requirements:

Topic: {title}
Category: {category}
Details: {description}

Follow these guidelines:
1. Content should be at least 1500 words
2. Use proper heading hierarchy (H1, H2, H3)
3. Include relevant keywords naturally
4. Add internal links to securade.ai where relevant
5. Include clear calls-to-action
6. Optimize for both readability and search engines

Return the content in this JSON format:
{{
    "meta": {{
        "title": "SEO optimized title",
        "description": "Meta description (150-160 characters)",
        "keywords": ["keyword1", "keyword2", ...],
        "og_title": "Open Graph title",
        "og_description": "Open Graph description"
    }},
    "content": {{
        "introduction": "Opening paragraphs",
        "sections": [
            {{
                "heading": "Section heading",
                "content": "Section content",
                "subsections": [
                    {{
                        "heading": "Subsection heading",
                        "content": "Subsection content"
                    }}
                ]
            }}
        ],
        "conclusion": "Closing paragraphs",
        "cta": "Call to action text"
    }}
}}"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are an SEO expert and technical writer specializing in workplace safety and AI technology."},
                {"role": "user", "content": prompt}
            ],
            response_format={ "type": "json_object" }
        )
        print(response)
        return json.loads(response.choices[0].message.content)
    except json.JSONDecodeError:
        raise ValueError("Failed to generate properly formatted blog content")

def format_blog_content(content_json):
    """Convert JSON blog content into HTML format."""
    html_content = f"""
        <div class="blog-content">
            <div class="introduction">
                {content_json['content']['introduction']}
            </div>
    """
    
    for section in content_json['content']['sections']:
        html_content += f"""
            <h2 class="fw-bolder mb-4 mt-5">{section['heading']}</h2>
            <div class="section-content">
                {section['content']}
            </div>
        """
        
        if 'subsections' in section:
            for subsection in section['subsections']:
                html_content += f"""
                    <h3 class="fw-bolder mb-3 mt-4">{subsection['heading']}</h3>
                    <div class="subsection-content">
                        {subsection['content']}
                    </div>
                """
    
    html_content += f"""
            <div class="conclusion">
                {content_json['content']['conclusion']}
            </div>
            <div class="cta mt-5">
                {content_json['content']['cta']}
            </div>
        </div>
    """
    
    return html_content

def get_issue_details():
    """Get details from GitHub issue."""
    g = Github(os.getenv('GITHUB_TOKEN'))
    repo = g.get_repo(os.getenv('REPO'))
    issue = repo.get_issue(number=int(os.getenv('ISSUE_NUMBER')))
    
    # Extract blog title from issue title
    blog_title = issue.title.replace('Create a new blog on ', '').strip()
    
    # Parse the issue body to find image URLs
    image_urls = []
    if issue.body:
        image_pattern = r'!\[(?P<alt>[^\]]*)\]\((?P<url>[^)]+)\)'
        matches = re.finditer(image_pattern, issue.body)
        for match in matches:
            image_urls.append({
                'url': match.group('url'),
                'alt': match.group('alt'),
                'name': match.group('url').split('/')[-1]
            })
    
    return {
        'title': blog_title,
        'description': issue.body,
        'images': image_urls
    }

def create_file_paths(title, category, image_filename):
    """Create appropriate file paths for blog and images."""
    slug = slugify(title)
    
    # Create category directory if it doesn't exist
    category_path = Path(f"blog/{category}")
    category_path.mkdir(parents=True, exist_ok=True)
    
    # Create images category directory if it doesn't exist
    image_category_path = Path(f"assets/images/blog/{category}")
    image_category_path.mkdir(parents=True, exist_ok=True)
    
    blog_path = f"blog/{category}/{slug}.html"
    image_path = f"assets/images/blog/{category}/{image_filename}"
    
    return blog_path, image_path

def create_pull_request(repo, blog_path, image_path, content, image_data, branch_name):
    # Create new branch
    base = repo.get_branch("main")
    repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=base.commit.sha)
    
    # Create blog post file
    repo.create_file(
        path=blog_path,
        message=f"Add blog post: {blog_path}",
        content=content,
        branch=branch_name
    )
    
    # Create image file
    repo.create_file(
        path=image_path,
        message=f"Add blog image: {image_path}",
        content=base64.b64encode(image_data).decode(),
        branch=branch_name
    )
    
    # Create pull request
    pr = repo.create_pull(
        title=f"Add new blog post: {blog_path}",
        body="Automatically generated blog post from issue",
        head=branch_name,
        base="main"
    )
    
    return pr

def get_template_path():
    """Get the absolute path to the templates directory from any script location."""
    # Get the repo root directory (where the script is running from)
    repo_root = Path(os.getcwd())
    
    # If we're in the scripts directory, go up one level
    if repo_root.name == 'scripts':
        repo_root = repo_root.parent
    
    return repo_root / 'templates'

def main():
    # Get issue details
    issue_details = get_issue_details()
    
    # Get existing categories
    existing_categories = get_existing_categories()
    
    # Analyze content for category
    category_info = analyze_content_for_category(
        issue_details['title'],
        issue_details['description'],
        existing_categories
    )
    
    # Generate blog content
    blog_data = generate_blog_content(
        issue_details['title'],
        issue_details['description'],
        category_info['category']
    )
    
    # Process image
    if issue_details['images']:
        image = issue_details['images'][0]
        image_data = requests.get(image['url']).content
        image_name = image['name']
    else:
        raise ValueError("No image found in the issue. Please attach an image to the issue.")
    
    # Create paths
    blog_path, image_path = create_file_paths(
        issue_details['title'],
        category_info['category'],
        f"{slugify(image_name)}"
    )
    
    # Format blog content into HTML
    formatted_content = format_blog_content(blog_data)
    
    # Load and render template
    template_path = get_template_path()
    env = Environment(loader=FileSystemLoader(str(template_path)))
    template = env.get_template('blog_template.html')
    
    final_html = template.render(
        title=blog_data['meta']['title'],
        meta_description=blog_data['meta']['description'],
        keywords=', '.join(blog_data['meta']['keywords']),
        og_title=blog_data['meta']['og_title'],
        og_description=blog_data['meta']['og_description'],
        image_url=f"/{image_path}",
        image_alt=image['alt'] if 'alt' in image else '',
        content=formatted_content,
        date=datetime.now().strftime('%B %d, %Y'),
        author="Securade.ai Team"
    )
    
    # Initialize GitHub client
    g = Github(os.getenv('GITHUB_TOKEN'))
    repo = g.get_repo(os.getenv('REPO'))
    
    # Create branch name
    branch_name = f"blog-{slugify(issue_details['title'])}"
    
    # Create pull request
    pr = create_pull_request(
        repo,
        blog_path,
        image_path,
        final_html,
        image_data,
        branch_name
    )
    
    print(f"Created PR: {pr.html_url}")
    print(f"Category: {category_info['category']} ({'new' if category_info['is_new_category'] else 'existing'})")
    print(f"Reasoning: {category_info['reasoning']}")

if __name__ == "__main__":
    main()