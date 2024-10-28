import streamlit as st
import requests 
import base64
import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from bs4 import BeautifulSoup

with open("styles.css") as f:
    st.markdown(f'<style>{f.read}</style>', unsafe_allow_html=True)
    
def export_llamaindex_docs_to_pdf(url):
    # Fetch the HTML content
    response = requests.get(url)
    html_content = response.text

    # Parse HTML content
    soup = BeautifulSoup(html_content, 'html.parser')
    main_content = soup.find('div', class_='md-content')
    
    # Create PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
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
            return Paragraph(element.get_text().strip(), style)
        elif element.name == 'code':
            # Special handling for code blocks
            style = styles['Code']  # You might need to define this style
            return Paragraph(f"<pre>{element.get_text().strip()}</pre>", style)
        elif element.name in ['p', 'div']:
            style = styles['Normal']
            return Paragraph(element.get_text().strip(), style)
        return None

    # Process elements while avoiding duplicates
    for element in main_content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'p', 'code']):
        paragraph = process_element(element)
        if paragraph:
            story.append(paragraph)

    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer

def get_binary_file_downloader_html(bin_file, file_label='File'):
    bin_str = base64.b64encode(bin_file.read()).decode()
    href = f'<a href="data:application/octet-stream;base64,{bin_str}" download="{file_label}">Download {file_label}</a>'
    return href

st.title("LlamaIndex Documentation PDF Generator")

url = "https://docs.llamaindex.ai/en/stable/"
st.write(f"This app generates a PDF from the LlamaIndex documentation at: {url}")

if st.button("Generate PDF"):
    try:
        with st.spinner("Generating PDF..."):
            pdf_buffer = export_llamaindex_docs_to_pdf(url)
            
        st.success("PDF generated successfully!")
        st.markdown(
            get_binary_file_downloader_html(pdf_buffer, "llamaindex_documentation.pdf"), 
            unsafe_allow_html=True
        )
    except Exception as e:
        st.error(f"An error occurred while generating the PDF: {str(e)}")

st.write("Click the 'Generate PDF' button to create and download the LlamaIndex documentation PDF.")
