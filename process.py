import os
import argparse
from bs4 import BeautifulSoup

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

        return title, img_src, alt_text

def generate_html_structure(folder_path):
    html_content = ''
    
    html_begin = f'''
    <!DOCTYPE html>
    <html class="no-js" lang="en">
    <head>
	<title>Securade.ai - Safety, powered by AI</title>
    <meta charset="utf-8" />
    <meta http-equiv="x-ua-compatible" content="ie=edge" />
    <meta name="description" content="Industry's first generative AI based video analytics platform for worker safety and productivity. Protect your workers and projects with AI technology that predicts and prevents accidents.">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no" />
    <meta property="og:type" content="website">
	<meta property="og:title" content="Securade.ai - Safety, powered by AI">
	<meta property="og:description" content="Industry's first generative AI based video analytics platform for worker safety and productivity. Protect your workers and projects with AI technology that predicts and prevents accidents.">
	<meta property="og:image" content="https://securade.ai/images/logo.png">
	<meta property="og:url" content="https://securade.ai/page2.html">
	
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
		

    <!-- ========================= header start ========================= -->
    <header class="header">
      <div class="navbar-area">
        <div class="container">
          <div class="row align-items-center">
            <div class="col-lg-12">
              <nav class="navbar navbar-expand-lg">
                <a class="navbar-brand" href="index.html">
                  <img src="assets/images/logo/logo.png" alt="Logo" />
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
												<a class="nav-link" href="index.html#home">Home</a>
											</li>
											<li class="nav-item">
												<a class="nav-link" href="index.html#features">Features</a>
											</li>
											<li class="nav-item">
												<a class="nav-link" href="index.html#platform">HUB</a>
											</li>
											<li class="nav-item">
												<a class="nav-link" href="index.html#tower">Tower</a>
											</li>
											<li class="nav-item">
												<a class="nav-link" href="index.html#solutions">Solutions</a>
											</li>
											<li class="nav-item">
												<a class="nav-link" href="resources.html">Resources</a>
											</li>
										</ul>
									</div>
                  
                </div>
								<!-- navbar collapse -->
								<div class="header-btn">
									<button onclick="showPopup()" class="main-btn btn-hover">Request a Demo</button>
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
	<section id="resources" class="feature-section">
	<div class="container">
	    <div class="row mb-2">
   '''
   
    html_end = f'''
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

		<!-- ========================= footer start ========================= -->
		<footer class="footer pt-120">
			<div class="container">
				<div class="row">
					<div class="col-xl-3 col-lg-4 col-md-6 col-sm-10">
						<div class="footer-widget">
							<div class="logo">
								<a href="index.html"> <img src="assets/images/logo/logo.png" alt="logo" 
									style="max-width: 180px;"> </a>
							</div>
							<p class="desc">Safety, powered by AI.</p>
							<ul class="social-links">
								<!-- <li><a href="#0"><i class="lni lni-facebook"></i></a></li>-->
								<li><a href="https://www.linkedin.com/company/securade-ai/"><i class="lni lni-linkedin"></i></a></li>
								<!--<li><a href="#0"><i class="lni lni-instagram"></i></a></li>
								<li><a href="#0"><i class="lni lni-twitter"></i></a></li>-->
							</ul>
						</div>
					</div>
					<div class="col-xl-2 col-lg-2 col-md-6 col-sm-6 offset-xl-1">
						<div class="footer-widget">
							<h3>Company</h3>
							<ul class="links">
								<li><a href="index.html#home">Home</a></li>
								<li><a href="index.html#features">Features</a></li>
								<li><a href="index.html#platform">HUB</a></li>
								<li><a href="index.html#tower">Tower</a></li>
								<li><a href="index.html#solutions">Solutions</a></li>
							</ul>
						</div>
					</div>
					<div class="col-xl-3 col-lg-2 col-md-6 col-sm-6">
						<div class="footer-widget">
							<h3>About Us</h3>
							<ul class="links">
								<!--
								<li><a href="#team">Team</a></li>
								-->
								<li><a href="resources.html">Resources</a></li>
								<li>Contact Us</li>
								<li><a href="mailto:hello@securade.ai">hello@securade.ai</a></li>
								<li>OkyaSoft Pte. Ltd.</li>
								<!--<li><a href="#0">Awesome Design</a></li>
								<li><a href="#0">Ready to Use</a></li>
								<li><a href="#0">Essential Selection</a></li>-->
							</ul>
						</div>
					</div>
					<div class="col-xl-3 col-lg-4 col-md-6">
						<div class="footer-widget">
							<h3>Subscribe for Updates</h3>
							<!-- Begin Mailchimp Signup Form -->
							<form action="https://securade.us8.list-manage.com/subscribe/post?u=c1838467fb5c2b0a86380a903&amp;id=223c7c53e5&amp;f_id=001ea8e3f0" method="post" id="mc-embedded-subscribe-form" name="mc-embedded-subscribe-form" class="validate" target="_blank" novalidate>
								<input type="email" value="" name="EMAIL" class="required email" id="mce-EMAIL" required placeholder="Email">
								<div id="mce-responses" class="clear foot">
									<div class="response" id="mce-error-response" style="display:none"></div>
									<div class="response" id="mce-success-response" style="display:none"></div>
								</div>    <!-- real people should not fill this in and expect good things - do not remove this or risk form bot signups-->
								<button type="submit" value="Subscribe" name="subscribe" id="mc-embedded-subscribe" class="main-btn btn-hover">Subscribe</button>
						</form>
						<!--End mc_embed_signup-->
						</div>
					</div>
				</div>
			</div>
		</footer>
		<!-- ========================= footer end ========================= -->


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

    for file in os.listdir(folder_path):
        if file.endswith('.html'):
            file_path = os.path.join(folder_path, file)
            title, img_src, alt_text = extract_info_from_html(file_path)

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
            html_content += html_block

    return html_begin + html_content + html_end

def main():
    parser = argparse.ArgumentParser(description="Generate HTML structure from HTML files in a folder.")
    parser.add_argument('folder_path', type=str, help="Path to the folder containing HTML files.")
    parser.add_argument('-o', '--output', type=str, help="Path to output the generated HTML content.")

    args = parser.parse_args()

    html_content = generate_html_structure(args.folder_path)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as file:
            file.write(html_content)
        print(f"HTML content written to {args.output}")
    else:
        print(html_content)

if __name__ == "__main__":
    main()