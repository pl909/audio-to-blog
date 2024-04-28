from typing import Annotated
from fastapi.responses import JSONResponse
from fastapi import Body, FastAPI, File, UploadFile, HTTPException, Request
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
processing_status = {}

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
                # Reading the content of the file
                file_content = await file.read()
                await s3.put_object(
                    Bucket=S3_BUCKET,
                    Key=filename,
                    Body=file_content,
                    ContentType=file.content_type
                )
                print(f"File uploaded: {filename}")
                return JSONResponse(status_code=200, content={"message": "File uploaded successfully", "filename": filename})
            except Exception as e:
                print(f"Upload failed: {e}")
                return JSONResponse(status_code=500, content={"error": str(e)})
    raise HTTPException(status_code=400, detail="Failed to upload file")


@app.post("/process/{filename}")
async def process_file(filename: str):
    print("Entered /process :D")
    if not filename:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Filename is missing")
    
    print(f"filename: {filename}")
    data = {
        "input": "{\"filename\": \"" + f"s3://{S3_BUCKET}/" + filename + "\"}",
        "stateMachineArn": "arn:aws:states:us-east-1:718203338152:stateMachine:transcribe"
    }
    headers = {'Content-Type': 'application/json'}
    url = 'https://wrnqr49qhe.execute-api.us-east-1.amazonaws.com/beta/execution'
    response = requests.post(url, json=data, headers=headers)

    process_id = response.json().get("executionArn").split("-")[-1]
    processing_status[process_id] = {"complete": False, "result": None}

    print(f"Started process id {process_id}")
    if response.status_code != 200:
        print(f"Failed to start process, status code: {response.status_code}, message: {response.text}")
        raise HTTPException(status_code=500, detail="Failed to start processing")

    return {"message": "Processing started", "process_id": process_id}


@app.post("/callback")
async def callback(process_id: str, text_result: Annotated[str, Body()]):
    if process_id in processing_status:
        processing_status[process_id] = {"complete": True, "result": text_result}
    return {"status": "success", "data": text_result}

@app.get("/status")
async def check_status(process_id: str):
    if process_id in processing_status and processing_status[process_id]['complete']:
        return {"complete": True, "result": processing_status[process_id]['result']}
    else:
        return {"complete": False}