import io
import pandas as pd
from pypdf import PdfReader

def parse_uploaded_file(uploaded_file) -> str:
    """
    Parse uploaded Streamlit file (PDF, CSV, TXT, MD).
    Returns extracted plain text content.
    """
    if uploaded_file is None:
        return ""
        
    filename = uploaded_file.name.lower()
    file_bytes = uploaded_file.getvalue()
    
    content_text = f"=== 附件內容檔名: {uploaded_file.name} ===\n"
    
    try:
        if filename.endswith(".pdf"):
            reader = PdfReader(io.BytesIO(file_bytes))
            pages_text = []
            for i, page in enumerate(reader.pages[:10]):  # Read up to 10 pages
                text = page.extract_text()
                if text:
                    pages_text.append(f"--- 頁碼 {i+1} ---\n{text}")
            content_text += "\n".join(pages_text)
            
        elif filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_bytes))
            content_text += df.to_string(index=False, max_rows=30)
            
        elif filename.endswith(".txt") or filename.endswith(".md"):
            content_text += file_bytes.decode("utf-8", errors="ignore")
            
        else:
            content_text += file_bytes.decode("utf-8", errors="ignore")
            
    except Exception as e:
        content_text += f"解析檔案時發生錯誤: {str(e)}"
        
    return content_text.strip()
