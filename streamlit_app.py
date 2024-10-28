import streamlit as st
import requests 
import base64
import io
import emoji
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from bs4 import BeautifulSoup

# Define custom blue color
#CUSTOM_BLUE = colors.HexColor('#0068c9')

def remove_emojis(text):
    """Remove emojis from text."""
    return emoji.replace_emoji(text, '')

def create_custom_styles():
    styles = getSampleStyleSheet()
    
    if 'CodeStyle' not in styles:
        code_style = ParagraphStyle(
            'CodeStyle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leftIndent=20,
            spaceAfter=10,
            spaceBefore=10,
            alignment=TA_LEFT
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
            textColor="#0068c9",  # Using our custom blue color
            underline=True
        )
        styles.add(link_style)
    
    if 'LargeText' not in styles:
        large_text_style = ParagraphStyle(
            'LargeText',
            parent=styles['Normal'],
            fontSize=16,
            spaceAfter=10,
            spaceBefore=10
        )
        styles.add(large_text_style)
    
    return styles

class DocumentWithBookmarks(BaseDocTemplate):
    def __init__(self, filename, **kwargs):
        super().__init__(filename, **kwargs)
        self.bookmarks = []
        
    def afterFlowable(self, flowable):
        if getattr(flowable, 'bookmark_key', None) is not None:
            self.bookmarks.append((flowable.bookmark_level, flowable.bookmark_key, self.page))

def process_code_block(code_text):
    lines = code_text.strip().split('\n')
    formatted_code = '<br/>'.join(line.strip() for line in lines if line.strip())
    return f'<pre>{formatted_code}</pre>'

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
            if isinstance(content, str):
                text += content
            elif content.name == 'a':
                href = content.get('href', '')
                link_text = content.get_text()
                if href.startswith('#'):
                    # Internal link with custom color
                    text += f'<link href="{href[1:]}" color="#0068c9">{link_text}</link>'
                else:
                    # External link with custom color
                    text += f'<link href="{href}" color="#0068c9">{link_text}</link>'
            elif content.name == 'span':
                span_text = content.get_text()
                style = content.get('style', '')
                if 'font-size: 200%' in style:
                    text += f'<font size="14">{span_text}</font>'
                else:
                    text += span_text
            else:
                text += content.get_text()
    except AttributeError:
        text += str(content)
    return text

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
        
        # Create custom document template with bookmarks support
        doc = DocumentWithBookmarks(buffer, pagesize=letter)
        frame = Frame(doc.leftMargin, doc.bottomMargin,
                     doc.width, doc.height,
                     id='normal')
        template = PageTemplate(id='main', frames=frame)
        doc.addPageTemplates([template])
        
        styles = create_custom_styles()
        story = []

        seen_elements = set()

        def process_element(element):
            element_id = id(element)
            
            if element_id in seen_elements:
                return None
                
            seen_elements.add(element_id)
            
            if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                style = styles['Heading' + element.name[1]]
                clean_text = clean_heading_text(element.get_text())
                p = Paragraph(clean_text, style)
                if 'id' in element.attrs:
                    p.bookmark_key = element['id']
                    p.bookmark_level = int(element.name[1])
                return [p]
            
            elif element.name == 'code':
                formatted_code = process_code_block(element.get_text())
                return [Paragraph(formatted_code, styles['CodeStyle'])]
            
            elif element.name == 'ul':
                items = process_list_items(element, ordered=False)
                return [Paragraph(item, styles['CustomUnorderedList']) for item in items]
            
            elif element.name == 'ol':
                items = process_list_items(element, ordered=True)
                return [Paragraph(item, styles['CustomOrderedList']) for item in items]
            
            elif element.name in ['p', 'div']:
                text = process_links(element)
                text = remove_emojis(text)
                if text:
                    return [Paragraph(text, styles['Normal'])]
            
            return []

        # Process all elements
        for element in main_content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'p', 'code', 'ul', 'ol']):
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
