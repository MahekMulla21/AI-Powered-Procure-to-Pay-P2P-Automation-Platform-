import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse
import shutil
import tempfile

app = FastAPI(title="PO Processing API", version="1.0.0")


@app.get("/")
async def root():
    return {
        "message": "PO Processing API",
        "version": "1.0.0",
        "endpoints": {
            "/process-pdf": "POST - Upload and process a PO PDF file",
            "/health": "GET - Health check endpoint"
        }
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/process-pdf")
async def process_pdf(
    file: UploadFile = File(...),
    file_id: int = Form(None)
):
    """
    Upload and process a PO PDF file.
    
    Args:
        file: PDF file to process
        file_id: Optional file ID for database reference
    
    Returns:
        JSON response with processing results
    """
    try:
        # Import process_file here to avoid module-level import issues
        from po_main import process_file
        
        # Validate file type
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            shutil.copyfileobj(file.file, tmp_file)
            tmp_file_path = tmp_file.name
        
        try:
            # Process the file
            process_file(tmp_file_path, file_id)
            
            return JSONResponse({
                "status": "success",
                "message": "PO processing completed",
                "filename": file.filename,
                "file_id": file_id
            })
        
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_file_path):
                os.remove(tmp_file_path)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
