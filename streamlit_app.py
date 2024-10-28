import streamlit as st
import requests 
import base64
import io
import emoji
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from bs4 import BeautifulSoup, NavigableString

# Define custom blue color
CUSTOM_BLUE = colors.HexColor('#0068c9')

def remove_emojis(text):
    """Remove emojis from text."""
    return emoji.replace_emoji(text, '')

def create_custom_styles():
    styles = getSampleStyleSheet()
    
    if 'CodeStyle' not in styles:
        code_style = ParagraphStyle(
            'CodeStyle',
            parent=styles['Normal'],
            fontName='Courier',
            fontSize=10,
            leftIndent=20,
            spaceAfter=10,
            spaceBefore=10,
            alignment=TA_LEFT,
            backColor=colors.Color(0.95, 0.95, 0.95)
        )
        styles.add(code_style)
    
    if 'CustomUnorderedList' not in styles:
        unordered_list_style = ParagraphStyle(
            'CustomUnorderedList',
            parent=styles['Normal'],
            leftIndent=35,
            bulletIndent=20,
            spaceAfter=5,
            bulletFontName='Helvetica',
        )
        styles.add(unordered_list_style)
    
    if 'CustomOrderedList' not in styles:
        ordered_list_style = ParagraphStyle(
            'CustomOrderedList',
            parent=styles['Normal'],
            leftIndent=35,
            bulletIndent=20,
            spaceAfter=5,
        )
        styles.add(ordered_list_style)
    
    if 'LinkStyle' not in styles:
        link_style = ParagraphStyle(
            'LinkStyle',
            parent=styles['Normal'],
            textColor=CUSTOM_BLUE,
            underline=True
        )
        styles.add(link_style)
    
    return styles

class DocumentWithBookmarks(BaseDocTemplate):
    def __init__(self, filename, **kwargs):
        super().__init__(filename, **kwargs)
        self.bookmarks = []
        
    def afterFlowable(self, flowable):
        if getattr(flowable, 'bookmark_key', None) is not None:
            self.bookmarks.append((flowable.bookmark_level, flowable.bookmark_key, self.page))

def clean_code_block(code_text):
    """Clean and format code block text."""
    lines = [line.rstrip() for line in code_text.strip().split('\n')]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return '\n'.join(lines)

def process_code_block(code_text):
    """Process a code block with proper formatting."""
    cleaned_code = clean_code_block(code_text)
    if not cleaned_code:
        return ''
    escaped_code = (cleaned_code
                   .replace('&', '&amp;')
                   .replace('<', '&lt;')
                   .replace('>', '&gt;')
                   .replace('\n', '<br/>'))
    return f'<pre>{escaped_code}</pre>'

def clean_heading_text(text):
    text = remove_emojis(text)
    return text.split('#')[0].strip()

def process_list_items(list_element, ordered=False):
    result = []
    for i, item in enumerate(list_element.find_all('li', recursive=False)):
        bullet = f"{i+1}." if ordered else "•"
        
        paragraphs = item.find_all('p')
        if paragraphs:
            for p in paragraphs:
                text = process_links(p)
                text = remove_emojis(text)
                if text.strip():
                    result.append(f"{bullet} {text.strip()}")
        else:
            text = process_links(item)
            text = remove_emojis(text)
            if text.strip():
                result.append(f"{bullet} {text.strip()}")
            
    return result

def process_links(element):
    """Process anchor tags and span elements with styles."""
    text = ""
    try:
        for content in element.contents:
            if isinstance(content, NavigableString):
                text += str(content)
            elif content.name == 'a':
                href = content.get('href', '')
                link_text = content.get_text()
                if href.startswith('#'):
                    text += f'<link href="{href[1:]}" color="#{CUSTOM_BLUE.hexval()[2:]}">{link_text}</link>'
                else:
                    text += f'<link href="{href}" color="#{CUSTOM_BLUE.hexval()[2:]}">{link_text}</link>'
            elif content.name == 'span':
                span_text = content.get_text()
                style = content.get('style', '')
                if 'font-size: 200%' in style:
                    text += f'<font size="14">{span_text}</font>'
                else:
                    text += span_text
            elif content.name in ['pre', 'code']:
                continue
            else:
                text += content.get_text()
    except AttributeError:
        text += str(content)
    return text

def get_text_content(element):
    """Extract text content from element, excluding code blocks."""
    text = ""
    for content in element.contents:
        if isinstance(content, NavigableString):
            text += str(content)
        elif content.name not in ['pre', 'code']:
            text += content.get_text()
    return text.strip()

def export_llamaindex_docs_to_pdf(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        html_content = response.text

        soup = BeautifulSoup(html_content, 'html.parser')
        main_content = soup.find('div', class_='md-content')
        if not main_content:
            raise Exception("Could not find main content div")

        buffer = io.BytesIO()
        doc = DocumentWithBookmarks(buffer, pagesize=letter)
        frame = Frame(doc.leftMargin, doc.bottomMargin,
                     doc.width, doc.height,
                     id='normal')
        template = PageTemplate(id='main', frames=frame)
        doc.addPageTemplates([template])
        
        styles = create_custom_styles()
        story = []
        seen_elements = set()
        seen_code_blocks = set()

        def process_element(element):
            element_id = id(element)
            
            if element_id in seen_elements:
                return None
                
            seen_elements.add(element_id)
            
            paragraphs = []
            
            # Handle headings
            if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                style = styles['Heading' + element.name[1]]
                clean_text = clean_heading_text(element.get_text())
                p = Paragraph(clean_text, style)
                if 'id' in element.attrs:
                    p.bookmark_key = element['id']
                    p.bookmark_level = int(element.name[1])
                paragraphs.append(p)
            
            # Handle code blocks
            elif element.name in ['pre', 'code']:
                code_content = element.get_text().strip()
                if code_content and code_content not in seen_code_blocks:
                    seen_code_blocks.add(code_content)
                    formatted_code = process_code_block(code_content)
                    if formatted_code:
                        paragraphs.append(Paragraph(formatted_code, styles['CodeStyle']))
            
            # Handle lists
            elif element.name == 'ul':
                items = process_list_items(element, ordered=False)
                paragraphs.extend([Paragraph(item, styles['CustomUnorderedList']) for item in items])
            
            elif element.name == 'ol':
                items = process_list_items(element, ordered=True)
                paragraphs.extend([Paragraph(item, styles['CustomOrderedList']) for item in items])
            
            # Handle paragraphs and divs
            elif element.name in ['p', 'div']:
                # Process text content
                text_content = process_links(element)
                if text_content.strip():
                    paragraphs.append(Paragraph(text_content, styles['Normal']))
                
                # Process code blocks separately
                code_blocks = element.find_all(['pre', 'code'])
                for code_block in code_blocks:
                    code_content = code_block.get_text().strip()
                    if code_content and code_content not in seen_code_blocks:
                        seen_code_blocks.add(code_content)
                        formatted_code = process_code_block(code_content)
                        if formatted_code:
                            paragraphs.append(Paragraph(formatted_code, styles['CodeStyle']))
            
            return paragraphs

        # Process all elements
        for element in main_content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'p', 'pre', 'code']):
            # Skip if element is a child of a processed element
            parent_processed = False
            for parent in element.parents:
                if id(parent) in seen_elements:
                    parent_processed = True
                    break
            
            if not parent_processed:
                paragraphs = process_element(element)
                if paragraphs:
                    story.extend(paragraphs)
                    story.append(Spacer(1, 6))

        doc.build(story)
        buffer.seek(0)
        return buffer
    
    except requests.RequestException as e:
        raise Exception(f"Failed to fetch the webpage: {str(e)}")
    except Exception as e:
        raise Exception(f"Error generating PDF: {str(e)}")

def get_binary_file_downloader_html(bin_file, file_label='File'):
    bin_str = base64.b64encode(bin_file.read()).decode()
    href = f'<a href="data:application/octet-stream;base64,{bin_str}" download="{file_label}">Download {file_label}</a>'
    return href

st.title("LlamaIndex Documentation PDF Generator")

url = st.text_input("Enter URL", "https://docs.llamaindex.ai/en/stable/")
st.write(f"This app generates a PDF from the documentation at the provided URL.")

if st.button("Generate PDF"):
    try:
        with st.spinner("Generating PDF..."):
            pdf_buffer = export_llamaindex_docs_to_pdf(url)
            
        st.success("PDF generated successfully!")
        st.markdown(
            get_binary_file_downloader_html(pdf_buffer, "documentation.pdf"), 
            unsafe_allow_html=True
        )
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
