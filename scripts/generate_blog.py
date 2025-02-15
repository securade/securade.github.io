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

MODEL = "gemini-2.0-flash"

def get_existing_categories():
    """Get list of existing blog categories from the blog directory."""
    blog_path = Path("blog")
    if not blog_path.exists():
        return []
    
    return [d.name for d in blog_path.iterdir() if d.is_dir()]

def analyze_content_for_category(title, description, existing_categories):
    """Analyze content to determine the most appropriate category."""
    categories_str = ", ".join(existing_categories) if existing_categories else "none"
    
    prompt = f"""Analyze this blog post and determine the most appropriate high-level category.

Existing categories: {categories_str}

Guidelines for categorization:
1. Use broad, generic categories that can encompass multiple related topics
2. Prefer existing categories if the content reasonably fits
3. Only suggest a new category if the content truly doesn't fit existing ones
4. Think in terms of main themes rather than specific topics

Example categories and their scope:
- workplace-safety: Any content about safety protocols, procedures, prevention, PPE, etc.
- technology: AI, machine learning, video analytics, software solutions, etc.
- industry-solutions: Specific implementations, case studies, industry-specific applications
- best-practices: Guidelines, standards, recommendations, how-tos
- compliance: Regulations, standards, certifications, legal requirements
- innovations: New developments, cutting-edge solutions, future trends

Format Requirements:
1. Use lowercase letters only
2. Replace spaces with hyphens
3. Keep it concise and generic
4. No special characters except hyphens

Title: {title}
Description: {description}

Return your response in this JSON format:
{{
    "category": "suggested-category-name",
    "is_new_category": boolean,
    "reasoning": "brief explanation of why this category is most appropriate and how it fits into the broader content structure"
}}"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a content categorization expert with a focus on creating broad, reusable categories."},
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
    
def save_image_from_base64(image_data, file_path):
    """Convert and save image data as JPEG."""
    try:
        # Open image using PIL
        image = Image.open(BytesIO(image_data))
        
        # Convert to RGB if needed (in case of PNG with transparency)
        if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
            image = background
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Save as JPEG file
        image.save(file_path, format='JPEG', quality=85)
        
        # Return the file content for GitHub
        with open(file_path, 'rb') as f:
            return f.read()
    except Exception as e:
        print(f"Error processing image: {e}")
        raise

def generate_image_name(title, description, image_data):
    """Generate a descriptive name for the image based on its actual content and context."""
    try:
        # Convert binary image data to base64
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        # First analyze the image content
        vision_response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Analyze this image and describe its key elements. Focus on workplace safety, AI technology, or industrial elements if present."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ]
        )
        
        image_description = vision_response.choices[0].message.content

        # Now generate a filename based on both image content and blog context
        prompt = f"""Generate a descriptive filename for an image used in a blog post.

Context:
Blog Title: {title}
Blog Description: {description}
Image Content Analysis: {image_description}

Requirements:
1. Use descriptive words that reflect the actual image content
2. Use camelCase format
3. Include 'securadeai' as prefix
4. Must end with .jpeg
5. No spaces, hyphens, or special characters
6. Example format: securadeaiWorkplaceSafetyDashboard.jpeg, securadeaiAiCameraSystem.jpeg

Return only the filename, nothing else."""

        name_response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are an expert at creating descriptive and SEO-friendly image filenames."},
                {"role": "user", "content": prompt}
            ]
        )
        
        filename = name_response.choices[0].message.content.strip()
        # Ensure it meets our requirements
        if not filename.startswith("securadeai") or not filename.endswith(".jpeg"):
            filename = f"securadeaiGenericBlog.jpeg"
        return filename
    except Exception as e:
        print(f"Error generating image name: {e}")
        return f"securadeaiGenericBlog.jpeg"
    
def generate_blog_content(title, description, category):
    """Generate SEO-optimized blog content in structured format with HTML."""
    prompt = f"""Create a comprehensive, SEO-optimized blog post with the following requirements:

Topic: {title}
Category: {category}
Details: {description}

Important Format Requirements:
1. Use proper HTML formatting instead of Markdown
2. For lists, use <ul> and <li> tags
3. For emphasis, use <em> or <strong> tags
4. For links, use <a href="..."> tags
5. For paragraphs, use <p> tags
6. Use proper HTML heading tags (<h2>, <h3>)
7. Ensure all HTML is properly closed
8. Do not use markdown formatting (*, _, [], etc.)

Content Guidelines:
1. Content should be at least 1500 words
2. Use proper heading hierarchy
3. Include relevant keywords naturally
4. Add internal links to securade.ai where relevant
5. Include clear calls-to-action

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
        "introduction": "<p>Opening paragraphs...</p>",
        "sections": [
            {{
                "heading": "<h2>Section heading</h2>",
                "content": "<p>Section content...</p>",
                "subsections": [
                    {{
                        "heading": "<h3>Subsection heading</h3>",
                        "content": "<p>Subsection content...</p>"
                    }}
                ]
            }}
        ],
        "conclusion": "<p>Closing paragraphs...</p>",
        "cta": "<p class='cta'>Call to action text...</p>"
    }}
}}"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are an SEO expert and technical writer specializing in workplace safety and AI technology. Always format content in HTML, not Markdown."},
                {"role": "user", "content": prompt}
            ],
            response_format={ "type": "json_object" }
        )
        
        return json.loads(response.choices[0].message.content)
    except json.JSONDecodeError:
        raise ValueError("Failed to generate properly formatted blog content")

def format_blog_content(content_json):
    """Convert JSON blog content into final HTML format."""
    html_content = f"""
        <div class="blog-content">
            <div class="introduction">
                {content_json['content']['introduction']}
            </div>
    """
    
    for section in content_json['content']['sections']:
        html_content += f"""
            {section['heading']}
            <div class="section-content">
                {section['content']}
            </div>
        """
        
        if 'subsections' in section:
            for subsection in section['subsections']:
                html_content += f"""
                    {subsection['heading']}
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
    # Get repository root (one level up from scripts directory)
    repo_root = Path(__file__).parent.parent
    slug = slugify(title)
    
    if category:
        # If category is specified, create in category subfolder
        blog_path = f"blog/{category}/{slug}.html"
        image_path = f"assets/images/blog/{category}/{image_filename}"
        
        # Create category directories if they don't exist
        (repo_root / "blog" / category).mkdir(parents=True, exist_ok=True)
        (repo_root / "assets" / "images" / "blog" / category).mkdir(parents=True, exist_ok=True)
    else:
        # If no category, create directly in blog folder
        blog_path = f"blog/{slug}.html"
        image_path = f"assets/images/blog/{image_filename}"
        
        # Ensure base directories exist
        (repo_root / "blog").mkdir(parents=True, exist_ok=True)
        (repo_root / "assets" / "images" / "blog").mkdir(parents=True, exist_ok=True)
    
    return blog_path, image_path

def create_pull_request(repo, blog_path, image_path, content, image_data, branch_name):
    """Create new branch and PR with blog post and image."""
    try:
        # Create new branch
        base = repo.get_branch("main")
        repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=base.commit.sha)
        
        # Save image to disk first
        temp_image_path = f"temp_{os.path.basename(image_path)}"
        processed_image_data = save_image_from_base64(image_data, temp_image_path)
        
        # Create image file in repo
        repo.create_file(
            path=image_path,
            message=f"Add blog image: {image_path}",
            content=processed_image_data,
            branch=branch_name
        )
        
        # Create blog post file
        repo.create_file(
            path=blog_path,
            message=f"Add blog post: {blog_path}",
            content=content,
            branch=branch_name
        )
        
        # Clean up temporary image file
        if os.path.exists(temp_image_path):
            os.remove(temp_image_path)
        
        # Create pull request
        pr = repo.create_pull(
            title=f"Add new blog post: {blog_path}",
            body="Automatically generated blog post from issue",
            head=branch_name,
            base="main"
        )
        
        return pr
    except Exception as e:
        print(f"Error creating PR: {e}")
        # Clean up temporary file in case of error
        if os.path.exists(temp_image_path):
            os.remove(temp_image_path)
        raise

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
        
        # Generate image name
        image_name = generate_image_name(
            issue_details['title'],
            issue_details['description'],
            image_data
        )
    else:
        raise ValueError("No image found in the issue. Please attach an image to the issue.")
    
    # Create paths
    blog_path, image_path = create_file_paths(
        issue_details['title'],
        category_info['category'],
        image_name
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