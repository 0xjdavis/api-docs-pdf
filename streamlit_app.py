import streamlit as st
import requests 
import base64
import io
import emoji
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer
from bs4 import BeautifulSoup, NavigableString
import html

# Define custom blue color
CUSTOM_BLUE = colors.HexColor('#0068c9')

def create_custom_styles():
    styles = getSampleStyleSheet()
    
    # Create styles for different list levels
    for level in range(1, 4):  # Support up to 3 levels of nesting
        style_name = f'UnorderedList_Level{level}'
        if style_name not in styles:
            list_style = ParagraphStyle(
                style_name,
                parent=styles['Normal'],
                leftIndent=20 * level,  # Increase indentation for each level
                bulletIndent=10 * level,
                spaceAfter=5
            )
            styles.add(list_style)
    
    return styles

def process_list_items(list_element, level=1):
    """Process list items with proper indentation for nested lists."""
    result = []
    items = list_element.find_all('li', recursive=False)
    
    for _, item in enumerate(items, start=1):  # Fixed: Properly unpack enumerate tuple
        # Process the main content of the list item
        content = ''
        for child in item.children:
            if isinstance(child, NavigableString):
                content += str(child).strip()
            elif child.name == 'a':
                href = child.get('href', '')
                link_text = child.get_text()
                content += f'<link href="{href}">{link_text}</link>'
            elif child.name not in ['ul', 'ol']:
                content += child.get_text().strip()
        
        # Add the item with proper indentation
        if content:
            bullet = "•" if level <= 3 else "○"  # Different bullet for deeper nesting
            indent = "    " * (level - 1)
            result.append(f"{indent}{bullet} {content}")
        
        # Process nested lists
        nested_lists = item.find_all(['ul', 'ol'], recursive=False)
        for nested_list in nested_lists:
            nested_items = process_list_items(nested_list, level + 1)
            result.extend(nested_items)
    
    return result

def export_to_pdf(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Create PDF document
        buffer = io.BytesIO()
        doc = BaseDocTemplate(buffer, pagesize=letter)
        frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='normal')
        template = PageTemplate(id='main', frames=[frame])
        doc.addPageTemplates([template])
        
        styles = create_custom_styles()
        story = []
        
        # Process content
        main_content = soup.find('div', class_='md-content')
        if not main_content:
            raise Exception("Could not find main content")
            
        for element in main_content.find_all(['ul', 'ol', 'p', 'h1', 'h2', 'h3']):
            if element.name in ['ul', 'ol']:
                items = process_list_items(element)
                for item in items:
                    level = item.count('    ') + 1
                    style = styles[f'UnorderedList_Level{min(level, 3)}']
                    story.append(Paragraph(item, style))
            else:
                # Handle other elements (paragraphs, headings, etc.)
                text = element.get_text().strip()
                if text:
                    style = styles['Normal']
                    if element.name.startswith('h'):
                        style = styles[f'Heading{element.name[1]}']
                    story.append(Paragraph(text, style))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer
        
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
