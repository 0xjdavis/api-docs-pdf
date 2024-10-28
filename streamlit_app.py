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
    # Create custom code style
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
    return styles

def process_code_block(code_text):
    # Split the code into lines and add line breaks
    lines = code_text.strip().split('\n')
    # Join lines with explicit line breaks and proper spacing
    formatted_code = '<br/>'.join(line.strip() for line in lines if line.strip())
    return f'<pre>{formatted_code}</pre>'

def clean_heading_text(text):
    # Remove the "#" symbol that appears after headings
    return text.split('#')[0].strip()

def export_llamaindex_docs_to_pdf(url):
    try:
        # Fetch the HTML content
        response = requests.get(url)
        response.raise_for_status()
        html_content = response.text

        # Parse HTML content
        soup = BeautifulSoup(html_content, 'html.parser')
        main_content = soup.find('div', class_='md-content')

        # Create PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = create_custom_styles()
        story = []

        # Keep track of processed code elements
        seen_elements = set()

        def process_element(element):
            # Generate a unique identifier for the element
            element_id = id(element)
            
            if element_id in seen_elements:
                return None
                
            seen_elements.add(element_id)
            
            if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                style = styles['Heading' + element.name[1]]
                # Clean heading text before creating paragraph
                clean_text = clean_heading_text(element.get_text())
                return Paragraph(clean_text, style)
            elif element.name == 'code':
                # Special handling for code blocks with line breaks
                formatted_code = process_code_block(element.get_text())
                return Paragraph(formatted_code, styles['CodeStyle'])
            elif element.name in ['p', 'div']:
                style = styles['Normal']
                return Paragraph(element.get_text().strip(), style)
            return None

        # Process all elements while avoiding duplicates
        for element in main_content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'p', 'code']):
            paragraph = process_element(element)
            if paragraph:
                story.append(paragraph)
                # Add space after each element
                story.append(Spacer(1, 6))

        # Build PDF
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
