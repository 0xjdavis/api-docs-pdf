import streamlit as st
import requests 
import base64
import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from bs4 import BeautifulSoup

# Create a custom style for code blocks
def create_code_style():
    styles = getSampleStyleSheet()
    code_style = ParagraphStyle(
        'CodeStyle',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=10,
        leftIndent=20,
        spaceAfter=20,
        spaceBefore=20,
        alignment=TA_LEFT
    )
    return code_style

def process_code_block(code_text):
    # Split the code into lines and add line breaks
    lines = code_text.strip().split('\n')
    # Join lines with explicit line breaks and proper spacing
    return '<br/>'.join(line.strip() for line in lines if line.strip())

def export_code_blocks_to_pdf(url):
    try:
        # Fetch the HTML content
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes
        html_content = response.text

        # Parse HTML content
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Create PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        story = []
        
        # Get custom code style
        code_style = create_code_style()
        
        # Find all code blocks
        code_blocks = soup.find_all('code')
        
        # Process each code block
        for code_block in code_blocks:
            code_text = code_block.get_text()
            if code_text.strip():  # Only process non-empty code blocks
                formatted_code = process_code_block(code_text)
                # Create paragraph with formatted code
                code_para = Paragraph(formatted_code, code_style)
                story.append(code_para)
                # Add space between code blocks
                story.append(Spacer(1, 20))

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

st.title("Code Block PDF Generator")

url = st.text_input("Enter URL", "https://docs.llamaindex.ai/en/stable/")
st.write(f"This app extracts code blocks from the provided URL and generates a PDF.")

if st.button("Generate PDF"):
    try:
        with st.spinner("Generating PDF..."):
            pdf_buffer = export_code_blocks_to_pdf(url)
            
        st.success("PDF generated successfully!")
        st.markdown(
            get_binary_file_downloader_html(pdf_buffer, "code_blocks.pdf"), 
            unsafe_allow_html=True
        )
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")

st.write("Enter a URL and click 'Generate PDF' to extract and download code blocks.")
