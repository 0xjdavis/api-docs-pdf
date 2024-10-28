import streamlit as st
import requests 
import base64
import io
import emoji
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer
from bs4 import BeautifulSoup, NavigableString
import html

# Define custom blue color
CUSTOM_BLUE = colors.HexColor('#0068c9')

def remove_emojis(text):
    """Remove emojis from text."""
    return emoji.replace_emoji(text, '')

def clean_heading_text(text):
    """Clean heading text by removing emojis and extra whitespace."""
    text = remove_emojis(text)
    return text.split('#')[0].strip()

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
    
    # Create styles for different list levels
    for level in range(1, 4):
        style_name = f'UnorderedList_Level{level}'
        if style_name not in styles:
            list_style = ParagraphStyle(
                style_name,
                parent=styles['Normal'],
                leftIndent=20 * level,  # Increase indentation for each level
                bulletIndent=15 * level,
                spaceAfter=5
            )
            styles.add(list_style)
    
    if 'LinkStyle' not in styles:
        link_style = ParagraphStyle(
            'LinkStyle',
            parent=styles['Normal'],
            textColor=CUSTOM_BLUE,
            underline=True
        )
        styles.add(link_style)
    
    return styles

def process_links(element):
    """Process anchor tags and span elements with styles."""
    if isinstance(element, NavigableString):
        return html.escape(str(element))
    
    if element.name == 'a':
        href = element.get('href', '')
        link_text = element.get_text()
        escaped_href = html.escape(href)
        escaped_text = html.escape(link_text)
        if href.startswith('#'):
            return f'<a href="#{escaped_href[1:]}" color="#{CUSTOM_BLUE.hexval()[2:]}" underline="1">{escaped_text}</a>'
        else:
            return f'<a href="{escaped_href}" color="#{CUSTOM_BLUE.hexval()[2:]}" underline="1">{escaped_text}</a>'
    
    text = ""
    for child in element.children:
        if isinstance(child, NavigableString):
            text += html.escape(str(child))
        elif child.name == 'span':
            span_text = child.get_text()
            style = child.get('style', '')
            if 'font-size: 200%' in style:
                text += f'<font size="14">{html.escape(span_text)}</font>'
            else:
                text += html.escape(span_text)
        elif child.name not in ['pre', 'code']:
            text += process_links(child)
    
    return text

def process_list_items(list_element, level=1):
    """Process list items with proper indentation for nested lists."""
    result = []
    items = list_element.find_all('li', recursive=False)
    
    for item in items:
        # Process the main content of the list item
        content_parts = []
        
        for child in item.children:
            if isinstance(child, NavigableString):
                text = child.strip()
                if text:
                    content_parts.append(html.escape(text))
            elif child.name == 'a':
                content_parts.append(process_links(child))
            elif child.name not in ['ul', 'ol']:
                content_parts.append(process_links(child))
        
        content = ' '.join(content_parts).strip()
        
        # Add the item with proper level-based style
        if content:
            style_name = f'UnorderedList_Level{min(level, 3)}'
            bullet = "•" if level <= 3 else "○"
            result.append((content, style_name))
        
        # Process nested lists
        nested_lists = item.find_all(['ul', 'ol'], recursive=False)
        for nested_list in nested_lists:
            nested_items = process_list_items(nested_list, level + 1)
            result.extend(nested_items)
    
    return result

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

def export_to_pdf(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        html_content = response.text

        soup = BeautifulSoup(html_content, 'html.parser')
        main_content = soup.find('div', class_='md-content')
        if not main_content:
            raise Exception("Could not find main content div")

        buffer = io.BytesIO()
        doc = BaseDocTemplate(buffer, pagesize=letter)
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
            
            if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                style = styles['Heading' + element.name[1]]
                clean_text = clean_heading_text(element.get_text())
                p = Paragraph(clean_text, style)
                paragraphs.append(p)
            
            elif element.name in ['pre', 'code']:
                code_content = element.get_text().strip()
                if code_content and code_content not in seen_code_blocks:
                    seen_code_blocks.add(code_content)
                    formatted_code = process_code_block(code_content)
                    if formatted_code:
                        paragraphs.append(Paragraph(formatted_code, styles['CodeStyle']))
            
            elif element.name in ['ul', 'ol']:
                if not element.find_parent(['ul', 'ol']):  # Only process top-level lists
                    items = process_list_items(element)
                    for content, style_name in items:
                        if content.strip():
                            paragraphs.append(Paragraph(content, styles[style_name]))
            
            elif element.name in ['p', 'div']:
                if not element.find_parent(['ul', 'ol']):
                    text_content = process_links(element)
                    if text_content.strip():
                        paragraphs.append(Paragraph(text_content, styles['Normal']))
            
            return paragraphs

        for element in main_content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'p', 'pre', 'code', 'ul', 'ol']):
            if not any(parent.name in ['ul', 'ol'] for parent in element.parents):
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

st.title("Documentation PDF Generator")

url = st.text_input("Enter URL", "https://docs.llamaindex.ai/en/stable/")
st.write("This app generates a PDF from the documentation at the provided URL.")

if st.button("Generate PDF"):
    try:
        with st.spinner("Generating PDF..."):
            pdf_buffer = export_to_pdf(url)
            
        st.success("PDF generated successfully!")
        st.markdown(
            get_binary_file_downloader_html(pdf_buffer, "documentation.pdf"), 
            unsafe_allow_html=True
        )
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
