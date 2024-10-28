import streamlit as st
import requests 
import base64
import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from bs4 import BeautifulSoup

def create_custom_styles():
    styles = getSampleStyleSheet()
    
    # Only add styles if they don't exist
    if 'CodeStyle' not in styles:
        code_style = ParagraphStyle(
            'CodeStyle',
            parent=styles['Normal'],
            fontName='Courier',
            fontSize=10,
            leftIndent=20,
            spaceAfter=10,
            spaceBefore=10,
            alignment=TA_LEFT
        )
        styles.add(code_style)
    
    # Create list styles only if they don't exist
    if 'CustomUnorderedList' not in styles:
        unordered_list_style = ParagraphStyle(
            'CustomUnorderedList',
            parent=styles['Normal'],
            leftIndent=35,
            bulletIndent=20,
            spaceAfter=5,
            bulletFontName='Symbol',
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
    
    return styles

def process_code_block(code_text):
    lines = code_text.strip().split('\n')
    formatted_code = '<br/>'.join(line.strip() for line in lines if line.strip())
    return f'<pre>{formatted_code}</pre>'

def clean_heading_text(text):
    return text.split('#')[0].strip()

def process_list_items(list_element, ordered=False):
    items = []
    for i, item in enumerate(list_element.find_all('li', recursive=False)):
        bullet = f"{i+1}." if ordered else "•"
        text = item.get_text().strip()
        # Handle nested lists
        nested_lists = item.find_all(['ul', 'ol'], recursive=False)
        if nested_lists:
            text += '<br/>' + '<br/>'.join(
                process_list_items(nested_list, isinstance(nested_list, 'ol'))
                for nested_list in nested_lists
            )
        items.append(f"{bullet} {text}")
    return items

def export_llamaindex_docs_to_pdf(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        html_content = response.text

        soup = BeautifulSoup(html_content, 'html.parser')
        main_content = soup.find('div', class_='md-content')

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
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
                return Paragraph(clean_text, style)
            
            elif element.name == 'code':
                formatted_code = process_code_block(element.get_text())
                return Paragraph(formatted_code, styles['CodeStyle'])
            
            elif element.name == 'ul':
                items = process_list_items(element, ordered=False)
                return [Paragraph(item, styles['CustomUnorderedList']) for item in items]
            
            elif element.name == 'ol':
                items = process_list_items(element, ordered=True)
                return [Paragraph(item, styles['CustomOrderedList']) for item in items]
            
            elif element.name in ['p', 'div']:
                style = styles['Normal']
                text = element.get_text().strip()
                if text:  # Only create paragraph if there's actual text
                    return Paragraph(text, style)
            
            return None

        for element in main_content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'p', 'code', 'ul', 'ol']):
            result = process_element(element)
            if result:
                if isinstance(result, list):
                    story.extend(result)
                else:
                    story.append(result)
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

st.write("Enter a URL and click 'Generate PDF' to create and download the documentation PDF.")
