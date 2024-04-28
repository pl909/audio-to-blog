from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.staticfiles import StaticFiles
from starlette.status import HTTP_400_BAD_REQUEST
import os
import uuid
import requests
from aiobotocore.session import get_session

app = FastAPI()
templates = Jinja2Templates(directory='templates')


S3_BUCKET = 'transcribe-ids721'
session = get_session()

async def s3_client():
    return session.create_client(
        's3',
        aws_access_key_id=os.getenv('S3_KEY'),
        aws_secret_access_key=os.getenv('S3_SECRET'),
    )

@app.get("/")
async def read_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
    
@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    client = await s3_client()
    filename = file.filename
    if file:
        async with client as s3:
            try:
                await s3.upload_fileobj(
                    file.file,
                    S3_BUCKET,
                    filename,
                    ExtraArgs={"ContentType": file.content_type}
                )
                print(f"File uploaded: {filename}")
                return JSONResponse(status_code=200, content={"message": "File uploaded successfully", "filename": filename})
            except Exception as e:
                print(f"Upload failed: {e}")
                return JSONResponse(status_code=500, content={"error": str(e)})
    raise HTTPException(status_code=400, detail="Failed to upload file")


@app.post("/process")
async def process_file(filename: str):
    if filename:
        process_id = str(uuid.uuid4())
        data = {
            "input": "{\"filename\": \"" + f"s3://{S3_BUCKET}/" + filename + "\"}",
            "name": "Execution-" + process_id,
            "stateMachineArn": "arn:aws:states:us-east-1:718203338152:stateMachine:transcribe"
        }
        headers = {'Content-Type': 'application/json'}
        url = 'https://wrnqr49qhe.execute-api.us-east-1.amazonaws.com/beta/execution'
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            return JSONResponse(status_code=200, content={"message": "Processing started", "processId": process_id})
        else:
            return JSONResponse(status_code=400, content={"error": "Error initiating processing"})
    raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Filename is missing")
