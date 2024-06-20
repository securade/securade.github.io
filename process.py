import os
import argparse
import numpy as np
import xml.etree.ElementTree as ET
import requests
import spacy
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from collections import defaultdict
from prettytable import PrettyTable
from bs4 import BeautifulSoup
from spacy.matcher import Matcher
from datetime import datetime

# Load a Spacy model for NLP tasks
nlp = spacy.load('en_core_web_lg')

def format_link_opportunities(deduplicated_opportunities):
    """Format and print the link opportunities in a table, one row per keyword-target URL pair for each source URL."""
    table = PrettyTable()
    table.field_names = ["Source URL", "Keyword", "Target URL"]
    
    for source_url, opportunities in deduplicated_opportunities.items():
        for keyword, target_url in opportunities:
            # Add a row for each keyword-target pair under the current source URL
            table.add_row([source_url, keyword, target_url])
    
    # Check if there are any opportunities to display
    if len(table._rows) == 0:
        print("No internal linking opportunities found.")
    else:
        print(table)

def extract_keywords(text, common_words_set, min_length=2, max_length=32):
    """
    Extract relevant SEO keywords using SpaCy, excluding common English nouns and filtering out excessively long keywords.
    
    :param text: Text to extract keywords from.
    :param common_words_set: A set of common words to exclude.
    :param min_length: Minimum length of keywords to consider.
    :param max_length: Maximum length of keywords to allow.
    :return: A list of unique, relevant keywords.
    """
    doc = nlp(text)
    keywords = []
    matcher = Matcher(nlp.vocab)

    # Define POS patterns for matcher
    patterns = [
        [{"POS": "ADJ"}, {"POS": "NOUN"}],  # Adjective followed by a noun
        [{"POS": "PROPN"}, {"POS": "PROPN"}]  # Sequence of proper nouns
    ]
    matcher.add("POS_PATTERNS", patterns)

    # Use matcher to find patterns in text
    matches = matcher(doc)
    for _, start, end in matches:
        span = doc[start:end].text.lower()
        if len(span) >= min_length and len(span) <= max_length and span not in common_words_set:
            keywords.append(span)

    # Named Entity Recognition and dependency parsing integration
    for ent in doc.ents:
        if ent.label_ in ['PERSON', 'NORP', 'ORG', 'GPE', 'LOC', 'PRODUCT', 'EVENT', 'WORK_OF_ART']:
            ent_text = ent.text.lower()
            if len(ent_text) <= max_length:
                keywords.append(ent_text)

    for token in doc:
        if token.dep_ in ["nsubj", "dobj", "pobj"] and not token.is_stop:
            subtree_span = doc[token.left_edge.i : token.right_edge.i + 1].text.lower()
            if len(subtree_span) >= min_length and len(subtree_span) <= max_length and subtree_span not in common_words_set:
                keywords.append(subtree_span)

    # Remove duplicates and return
    return list(set(keywords))

def find_most_relevant_link(keyword, header_texts):
    """Find the most relevant link for a keyword based on similarity scores."""
    tfidf_vectorizer = TfidfVectorizer()
    tfidf_matrix = tfidf_vectorizer.fit_transform(header_texts + [keyword])
    cosine_similarities = cosine_similarity(tfidf_matrix[-1], tfidf_matrix[:-1]).flatten()
    return cosine_similarities

def calculate_relevance_score(source_url, keyword, target_url, contents):
    """
    Calculate a relevance score for a keyword between a source and target URL.
    The score is based on the frequency of the keyword in the target's content and semantic similarity.
    """
    target_content = contents[target_url]['headers'] + " " + contents[target_url]['paragraphs']
    source_content = contents[source_url]['headers'] + " " + contents[source_url]['paragraphs']

    # Calculate keyword frequency in the target content
    keyword_frequency = target_content.lower().count(keyword.lower())

    # Calculate semantic similarity (placeholder, see note below)
    doc_source = nlp(source_content)
    doc_target = nlp(target_content)
    similarity = doc_source.similarity(doc_target)

    # Combine frequency and similarity into a single score
    relevance_score = (keyword_frequency * 0.7) + (similarity * 0.3)

    return relevance_score

def analyze_content_and_identify_links(contents):
    """Analyze content and identify internal linking opportunities based on header texts."""
    link_opportunities = defaultdict(list)
    urls = list(contents.keys())
    header_texts = [contents[url]['headers'] for url in urls]
    common_words = spacy.lang.en.stop_words.STOP_WORDS

    for source_url in urls:
        print("Analyzing URL: " + source_url)
        paragraph_text = contents[source_url]['paragraphs']
        existing_links = {link[1] for link in contents[source_url].get('links', [])}  # Extract existing link URLs
        existing_anchor_texts = {link[0].lower() for link in contents[source_url].get('links', [])}  # Extract existing anchor texts

        keywords = extract_keywords(paragraph_text, common_words)
        
        for keyword in keywords:
            # Filter out keywords that are already used as anchor text
            if keyword.lower() in existing_anchor_texts:
                continue

            # Ignore the source URL's header text when searching for the most relevant link
            relevant_header_texts = [text if url != source_url else '' for url, text in zip(urls, header_texts)]
            cosine_similarities = find_most_relevant_link(keyword, relevant_header_texts)
            
            for target_idx, similarity_score in enumerate(cosine_similarities):
                if similarity_score > 0:  # Consider only positive similarity scores
                    target_url = urls[target_idx]
                    # Filter out target links that are already linked from the source URL
                    if target_url not in existing_links:
                        link_opportunities[keyword].append((source_url, target_url))

    # Deduplicate: For each keyword, keep only the most relevant (first) source-target pair
    deduplicated_opportunities = {k: v[0] for k, v in link_opportunities.items() if v}
    # Now, filter to keep only the top 3 keywords for each source URL
    final_opportunities = defaultdict(list)

    for keyword, links in deduplicated_opportunities.items():
        source_url, target_url = links
        # Assuming some relevance score calculation is available; using placeholder
        relevance_score = calculate_relevance_score(source_url, keyword, target_url, contents)
        final_opportunities[source_url].append((relevance_score, keyword, target_url))
    
    # Sort and keep top 3 for each source URL
    for source_url, opportunities in final_opportunities.items():
        sorted_opportunities = sorted(opportunities, reverse=True)[:3]  # Sort based on relevance score
        final_opportunities[source_url] = [(keyword, target_url) for _, keyword, target_url in sorted_opportunities]

    return final_opportunities

def parse_sitemap(sitemap_path):
    """Parse sitemap.xml and extract URLs."""
    urls = []
    tree = ET.parse(sitemap_path)
    root = tree.getroot()
    for url in root.findall('{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
        loc = url.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
        if loc is not None:
            # Include URLs ending with .html, .htm, or having no file extension
            if loc.text.endswith('.html') or loc.text.endswith('.htm') or ('.' not in loc.text.split('/')[-1]):
                urls.append(loc.text.strip())
    return urls
  
def scrape_urls(urls):
    """Scrape content from a list of URLs, focusing on <p>, <h1>, and <a> tags within <article>."""
    contents = {}
    # User-Agent string of a Chrome browser
    chrome_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.150 Safari/537.36"
    # Set headers to mimic Chrome browser
    request_headers = {
        "User-Agent": chrome_user_agent
    }
    for url in urls:
        response = requests.get(url, headers=request_headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            # Find the <article> section
            article = soup.find('article')
            if article:
                # Extract text from <h1> and <p> tags within the found <article>
                headers = article.find_all(['h1'])
                header_text = ' '.join(header.get_text().strip() for header in headers)
                
                paragraphs = article.find_all('p')
                paragraph_text = ' '.join(p.get_text().strip() for p in paragraphs)
                
                # Extract existing anchor texts and URLs they point to
                links = article.find_all('a')
                anchor_texts_urls = [(a.get_text().strip(), a.get('href')) for a in links if a.get('href')]

                # Store extracted texts and links in a structured manner
                contents[url] = {
                    'headers': header_text,
                    'paragraphs': paragraph_text,
                    'links': anchor_texts_urls  # Add the extracted anchor texts and URLs
                }
            else:
                print(f"No article found in {url}")
        else:
            print(f"Failed to fetch {url}")
    return contents

def extract_info_from_html(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        soup = BeautifulSoup(file, 'html.parser')
        title_tag = soup.find('title')
        title = title_tag.string if title_tag else 'No Title'

        figure_tag = soup.find('figure')
        img_tag = figure_tag.find('img') if figure_tag else None
        img_src = img_tag['src'] if img_tag and img_tag.has_attr('src') else '../assets/images/default-image.jpeg'
        img_src = img_src[3:]
        alt_text = img_tag['alt'] if img_tag and img_tag.has_attr('alt') else 'Default alt text'
        date_div = soup.find('div', class_='text-muted fst-italic mb-2')
        date_text = date_div.text.strip() if date_div else 'No Date'
        date_pattern = r'Posted on (\w+ \d+, \d+)'
        match = re.search(date_pattern, date_text)
        date = match.group(1) if match else 'No Date'

        return title, img_src, alt_text, date

def generate_html_structure(folder_path, HEADER_HTML, FOOTER_HTML):
    html_content = ''
    
    html_begin = '''
    <!DOCTYPE html>
    <html class="no-js" lang="en">
    <head>
	<title>Securade.ai - Resources</title>
    <meta charset="utf-8" />
    <meta http-equiv="x-ua-compatible" content="ie=edge" />
    <meta name="description" content="Revolutionizing worker safety and productivity with the first generative AI video analytics platform, predicting and preventing workplace accidents.">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no" />
    <meta property="og:type" content="website">
	<meta property="og:title" content="Securade.ai - Resources">
	<meta property="og:description" content="Revolutionizing worker safety and productivity with the first generative AI video analytics platform, predicting and preventing workplace accidents.">
	<meta property="og:image" content="https://securade.ai/images/logo.png">
	<meta property="og:url" content="https://securade.ai/page3.html">
	
    <link rel="shortcut icon" type="image/x-icon" href="assets/images/favicon.ico"/>
    <!-- Place favicon.ico in the root directory -->

    <!-- ========================= CSS here ========================= -->
    <link rel="stylesheet" href="assets/css/bootstrap-5.0.0-beta2.min.css" />
    <link rel="stylesheet" href="assets/css/LineIcons.2.0.css"/>
    <link rel="stylesheet" href="assets/css/tiny-slider.css"/>
    <link rel="stylesheet" href="assets/css/animate.css"/>
    <link rel="stylesheet" href="assets/css/main.css"/>
	<!-- Add icon library -->
	<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css">

	<script id="mcjs">
	function showPopup() {{ 
		!function(c,h,i,m,p){{m=c.createElement(h),p=c.getElementsByTagName(h)[0],m.async=1,m.src=i,p.parentNode.insertBefore(m,p)}}
		(document,"script","https://chimpstatic.com/mcjs-connected/js/users/c1838467fb5c2b0a86380a903/9bce73c0b98ece59d41dfe5e5.js");
	
		//unsetting the cookie
		document.cookie = "MCPopupClosed=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";                  
		document.cookie = "MCPopupSubscribed=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
	}}
		
	//document.getElementById("show-popup").onclick = function() {{ showPopup(); }}
	</script>
    </head>
    <body>
        <!--[if lte IE 9]>
        <p class="browserupgrade">
            You are using an <strong>outdated</strong> browser. Please
            <a href="https://browsehappy.com/">upgrade your browser</a> to improve
            your experience and security.
        </p>
        <![endif]-->

    <!-- ========================= preloader start ========================= -->
    <div class="preloader">
      <div class="loader">
        <div class="spinner">
          <div class="spinner-container">
            <div class="spinner-rotator">
              <div class="spinner-left">
                <div class="spinner-circle"></div>
              </div>
              <div class="spinner-right">
                <div class="spinner-circle"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
		<!-- preloader end -->
    '''

    feature_section= '''
	<section id="resources" class="feature-section">
	<div class="container">
	    <div class="row mb-2">
        <h1 class="fw-bolder mb-1">Resources</h1>
   '''
   
    page_end = '''
   </div>
   </div>
	  </section>

	  <nav aria-label="Page navigation">
		<ul class="pagination justify-content-center">
		<li class="page-item"><a class="page-link" href="resources.html">1</a></li>
		<li class="page-item"><a class="page-link" href="page2.html">2</a></li>
        <li class="page-item active"><a class="page-link" href="page3.html">3</a></li>
		</ul>
	  </nav>
    '''

    last_section = '''
    <!-- ========================= scroll-top ========================= -->
    <a href="#" class="scroll-top btn-hover">
      <i class="lni lni-chevron-up"></i>
    </a>

    <!-- ========================= JS here ========================= -->
    <script src="assets/js/bootstrap-5.0.0-beta2.min.js"></script>
    <script src="assets/js/tiny-slider.js"></script>
    <script src="assets/js/wow.min.js"></script>
    <script src="assets/js/polyfill.js"></script>
    <script src="assets/js/main.js"></script>
  </body>
</html>
'''

    html_blocks = []

    for file in os.listdir(folder_path):
        if file.endswith('.html'):
            file_path = os.path.join(folder_path, file)
            title, img_src, alt_text, date = extract_info_from_html(file_path)
            html_block = f'''
<div class="col-12">
    <div class="row g-0 border rounded overflow-hidden flex-md-row mb-4 shadow-sm h-md-250 position-relative">
        <div class="col p-4 d-flex flex-column position-static">
            <a href="{file_path}" class="icon-link gap-1 icon-link-hover stretched-link">
                <h3 class="mb-0">{title}</h3>
            </a>
        </div>
        <div class="col-auto d-none d-lg-block">
            <img class="rounded" width="120" height="80" src="{img_src}" alt="{alt_text}" />
        </div>
    </div>
</div>
'''
            date_obj = datetime.strptime(date, '%B %d, %Y')  # Assuming the date format is 'Month Day, Year'
            html_blocks.append((date_obj, html_block))

    html_blocks.sort(reverse=True)

    for _, html_block in html_blocks:
        html_content += html_block
    
    return html_begin + HEADER_HTML + feature_section + html_content + page_end + FOOTER_HTML + last_section

def main():
    parser = argparse.ArgumentParser(description="Generate HTML structure from HTML files in a folder.")
    parser.add_argument('-f', '--folder_path', type=str, help="Path to the folder containing HTML files.")
    parser.add_argument('--add-footer', action='store_true', help="Add footers to the HTML files in the specified folder.")
    parser.add_argument('--add-header', action='store_true', help="Add headers to the HTML files in the specified folder.")
    parser.add_argument('-o', '--output', type=str, help="Path to output the generated HTML content.")
    parser.add_argument('-s', '--sitemap', type=str, help="Path to the sitemap.xml file.")

    args = parser.parse_args()
    
    if args.output:
        path_prefix = ""
    else:
        path_prefix = "../"

    FOOTER_HTML = f"""
    <!-- ========================= footer start ========================= -->
    <footer class="footer pt-120">
        <div class="container">
            <div class="row">
                <div class="col-xl-3 col-lg-4 col-md-6 col-sm-10">
                    <div class="footer-widget">
                        <div class="logo">
                            <a href="{path_prefix}index.html"> <img src="{path_prefix}assets/images/logo/logo.png" alt="logo" 
                                style="max-width: 180px;"> </a>
                        </div>
                        <p class="desc">Safety, powered by AI.</p>
                        <ul class="social-links">
                            <li><a href="https://www.linkedin.com/company/securade-ai/"><i class="lni lni-linkedin"></i></a></li>
                        </ul>
                    </div>
                </div>
                <div class="col-xl-2 col-lg-2 col-md-6 col-sm-6 offset-xl-1">
                    <div class="footer-widget">
                        <h3>Company</h3>
                        <ul class="links">
                            <li><a href="{path_prefix}index.html#home">Home</a></li>
                            <li><a href="{path_prefix}safety-copilot.html">Safety Copilot&trade;</a></li>
                            <li><a href="{path_prefix}resources.html">Resources</a></li>
                        </ul>
                    </div>
                </div>
                <div class="col-xl-3 col-lg-2 col-md-6 col-sm-6">
                    <div class="footer-widget">
                        <h3>About Us</h3>
                        <ul class="links">
                            <li>Contact Us</li>
                            <li><a href="mailto:hello@securade.ai">hello@securade.ai</a></li>
                        </ul>
                    </div>
                </div>
                <div class="col-xl-3 col-lg-4 col-md-6">
                    <div class="footer-widget">
                        <h3>Subscribe for Updates</h3>
                        <form action="https://securade.us8.list-manage.com/subscribe/post?u=c1838467fb5c2b0a86380a903&amp;id=223c7c53e5&amp;f_id=001ea8e3f0" method="post" id="mc-embedded-subscribe-form" name="mc-embedded-subscribe-form" class="validate" target="_blank" novalidate>
                            <input type="email" value="" name="EMAIL" class="required email" id="mce-EMAIL" required placeholder="Email">
                            <div id="mce-responses" class="clear foot">
                                <div class="response" id="mce-error-response" style="display:none"></div>
                                <div class="response" id="mce-success-response" style="display:none"></div>
                            </div>
                            <button type="submit" value="Subscribe" name="subscribe" id="mc-embedded-subscribe" class="main-btn btn-hover">Subscribe</button>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </footer>
    <!-- ========================= footer end ========================= -->
    """

    HEADER_HTML = f"""
    <!-- ========================= header start ========================= -->
    <header class="header">
    <div class="navbar-area">
        <div class="container">
        <div class="row align-items-center">
            <div class="col-lg-12">
            <nav class="navbar navbar-expand-lg">
                <a class="navbar-brand" href="{path_prefix}index.html">
                <img src="{path_prefix}assets/images/logo/logo.png" alt="Logo" />
                </a>
                <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarSupportedContent" aria-controls="navbarSupportedContent" aria-expanded="false" aria-label="Toggle navigation">
                <span class="toggler-icon"></span>
                <span class="toggler-icon"></span>
                <span class="toggler-icon"></span>
                </button>
                <div class="collapse navbar-collapse sub-menu-bar" id="navbarSupportedContent">
                    <div class="ms-auto">
                        <ul id="nav" class="navbar-nav ms-auto">
                            <li class="nav-item">
                                <a class="nav-link" href="{path_prefix}index.html#home">Home</a>
                            </li>
                            <li class="nav-item">
                                <a class="nav-link" href="{path_prefix}index.html#platform">HUB</a>
                            </li>
                            <li class="nav-item">
                                <a class="nav-link" href="{path_prefix}index.html#tower">Tower</a>
                            </li>
                            <li class="nav-item">
                                <a class="nav-link" href="{path_prefix}index.html#sentinel">Sentinel</a>
                            </li>
                            <li class="nav-item">
                                <a class="nav-link" href="{path_prefix}safety-copilot.html">Safety Copilot&trade;</a>
                            </li>
                            <li class="nav-item">
                                <a class="nav-link active" href="{path_prefix}resources.html">Resources</a>
                            </li>
                        </ul>
                    </div>
                </div>
            </nav>
            <!-- navbar -->
            </div>
        </div>
        <!-- row -->
        </div>
        <!-- container -->
    </div>
    <!-- navbar area -->
    </header>
    <!-- ========================= header end ========================= -->
    """

    if args.sitemap:
        urls = parse_sitemap(args.sitemap)
        contents = scrape_urls(urls)
        link_opportunities = analyze_content_and_identify_links(contents)
        format_link_opportunities(link_opportunities)
    elif args.folder_path:
        if args.add_header:
            generate_headers(args.folder_path, HEADER_HTML)
            
        if args.add_footer:
            generate_footers(args.folder_path, FOOTER_HTML)
            
        if args.output:
            html_content = generate_html_structure(args.folder_path, HEADER_HTML, FOOTER_HTML)
            with open(args.output, 'w', encoding='utf-8') as file:
                file.write(html_content)
            print(f"HTML content written to {args.output}")

def generate_footers(folder_path, FOOTER_HTML):
    footer_start = "<!-- ========================= footer start ========================= -->"
    footer_end = "<!-- ========================= footer end ========================= -->"
    
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.endswith(".html"):
                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                start_index = content.find(footer_start)
                end_index = content.find(footer_end) + len(footer_end)
                
                if start_index != -1 and end_index != -1:
                    updated_content = content[:start_index] + FOOTER_HTML + content[end_index:]
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(updated_content)
                    print(f"Footer updated in {file_path}")
                else:
                    print(f"No footer found in {file_path}")
                    
def generate_headers(folder_path, HEADER_HTML):
    header_start = "<!-- ========================= header start ========================= -->"
    header_end = "<!-- ========================= header end ========================= -->"
    
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.endswith(".html"):
                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                start_index = content.find(header_start)
                end_index = content.find(header_end) + len(header_end)
                
                if start_index != -1 and end_index != -1:
                    updated_content = content[:start_index] + HEADER_HTML + content[end_index:]
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(updated_content)
                    print(f"Header updated in {file_path}")
                else:
                    print(f"No header found in {file_path}")

if __name__ == "__main__":
    main()
