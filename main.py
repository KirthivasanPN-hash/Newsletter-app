from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import models, schemas
from database import engine, get_db
from datetime import datetime
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os
from s3_config import upload_file_to_s3, delete_file_from_s3
from dotenv import load_dotenv
from fastapi.openapi.models import Reference



load_dotenv()

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Newsletter Management API",
    description="API for managing newsletters with image upload capability"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return RedirectResponse(url="/docs")

# Template routes
@app.post("/templates/", response_model=schemas.Template)
def create_template(template: schemas.TemplateCreate, db: Session = Depends(get_db)):
    db_template = models.Template(**template.dict())
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template

# for retreiving the all relevant newsletters sent
@app.get("/templates/", response_model=List[schemas.Template])
def read_templates(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    templates = db.query(models.Template).offset(skip).limit(limit).all()
    return templates


# newsletters by id
@app.get("/templates/{template_id}", response_model=schemas.Template)
def read_template(template_id: int, db: Session = Depends(get_db)):
    template = db.query(models.Template).filter(models.Template.id == template_id).first()
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return template

@app.delete("/templates/{template_id}")
def delete_template(template_id: int, db: Session = Depends(get_db)):
    template = db.query(models.Template).filter(models.Template.id == template_id).first()
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found") 
    db.delete(template)
    db.commit()
    return {"message": "Template deleted successfully"}

# Newsletter routes with image upload
@app.post("/newsletters/with-image/", 
    response_model=schemas.Newsletter,
    summary="Create a new newsletter with image",
    description="Create a new newsletter with optional image upload. The image will be stored in S3.",
    openapi_extra={
        'requestBody': {
            'content': {
                'multipart/form-data': {
                    'schema': {
                        'type': 'object',
                        'properties': {
                            'title': {'type': 'string', 'description': 'Newsletter title'},
                            'content': {'type': 'string', 'description': 'Newsletter content'},
                            'status': {'type': 'string', 'description': 'Newsletter status (draft, scheduled, sent)'},
                            'scheduled_date': {'type': 'string', 'format': 'date-time', 'description': 'Schedule date for the newsletter'},
                            'template_id': {'type': 'integer', 'description': 'Template ID if using a template'},
                            'image': {'type': 'string', 'format': 'binary', 'description': 'Image file to upload'},
                        },
                        'required': ['title', 'content', 'status']
                    }
                }
            }
        }
    }
)
async def create_newsletter_with_image(
    title: str = Form(..., description="Newsletter title"),
    content: str = Form(..., description="Newsletter content"),
    status: str = Form(..., description="Newsletter status (draft, scheduled, sent)"),
    scheduled_date: Optional[datetime] = Form(None, description="Schedule date for the newsletter"),
    template_id: Optional[int] = Form(None, description="Template ID if using a template"),
    image: Optional[UploadFile] = File(None, description="Image file to upload"),
    db: Session = Depends(get_db)
):
    try:
        # Create newsletter object
        newsletter_data = {
            "title": title,
            "content": content,
            "status": status,
            "scheduled_date": scheduled_date,
            "template_id": template_id,
            "image_url": None
        }
        
        # Handle image upload if provided
        if image:
            try:
                                # Validate MIME type and extension
                allowed_types = ["image/jpeg", "image/png"]
                allowed_extensions = [".jpg", ".jpeg", ".png"]
                content_type = image.content_type
                file_extension = os.path.splitext(image.filename)[1].lower()

                if content_type not in allowed_types or file_extension not in allowed_extensions:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid image. Only JPG and PNG formats are supported."
                    )

                
                # Generate a unique filename
                file_extension = os.path.splitext(image.filename)[1]
                unique_filename = f"newsletter_{datetime.now().strftime('%Y%m%d_%H%M%S')}{file_extension}"
                
                print(f"Attempting to upload file {unique_filename} to S3...")
                
                # Upload to S3
                image_url = upload_file_to_s3(image.file, unique_filename)
                if image_url:
                    print(f"Successfully uploaded to S3. URL: {image_url}")
                    newsletter_data["image_url"] = image_url
                else:
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to upload image to S3. Please check S3 credentials and bucket configuration."
                    )
            except Exception as upload_error:
                print(f"Error during file upload: {str(upload_error)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Error during file upload: {str(upload_error)}"
                )
        
        # Create newsletter in database
        try:
            db_newsletter = models.Newsletter(**newsletter_data)
            db.add(db_newsletter)
            db.commit()
            db.refresh(db_newsletter)
            return db_newsletter
        except Exception as db_error:
            print(f"Database error: {str(db_error)}")
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Database error: {str(db_error)}"
            )
            
    except HTTPException as http_error:
        # Re-raise HTTP exceptions
        raise http_error
    except Exception as e:
        # If anything fails, rollback the database changes
        print(f"Unexpected error: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )

@app.put("/newsletters/{newsletter_id}/with-image/", 
    response_model=schemas.Newsletter,
    summary="Update a newsletter with image",
    description="Update an existing newsletter with optional image upload. The image will be stored in S3.",
    openapi_extra={
        'requestBody': {
            'content': {
                'multipart/form-data': {
                    'schema': {
                        'type': 'object',
                        'properties': {
                            'title': {'type': 'string', 'description': 'Updated newsletter title'},
                            'content': {'type': 'string', 'description': 'Updated newsletter content'},
                            'status': {'type': 'string', 'description': 'Updated status (draft, scheduled, sent)'},
                            'scheduled_date': {'type': 'string', 'format': 'date-time', 'description': 'Updated schedule date'},
                            'template_id': {'type': 'integer', 'description': 'Updated template ID'},
                            'image': {'type': 'string', 'format': 'binary', 'description': 'New image file to upload'},
                        }
                    }
                }
            }
        }
    }
)
async def update_newsletter_with_image(
    newsletter_id: int,
    title: Optional[str] = Form(None, description="Updated newsletter title"),
    content: Optional[str] = Form(None, description="Updated newsletter content"),
    status: Optional[str] = Form(None, description="Updated status (draft, scheduled, sent)"),
    scheduled_date: Optional[datetime] = Form(None, description="Updated schedule date"),
    template_id: Optional[int] = Form(None, description="Updated template ID"),
    image: Optional[UploadFile] = File(None, description="New image file to upload"),
    db: Session = Depends(get_db)
):
    try:
        # Get existing newsletter
        db_newsletter = db.query(models.Newsletter).filter(models.Newsletter.id == newsletter_id).first()
        if db_newsletter is None:
            raise HTTPException(status_code=404, detail="Newsletter not found")
        
        # Update fields if provided
        if title is not None:
            db_newsletter.title = title
        if content is not None:
            db_newsletter.content = content
        if status is not None:
            db_newsletter.status = status
        if scheduled_date is not None:
            db_newsletter.scheduled_date = scheduled_date
        if template_id is not None:
            db_newsletter.template_id = template_id
        
        # Handle image upload if provided
        if image:
            # Delete old image from S3 if exists
            if db_newsletter.image_url:
                old_filename = db_newsletter.image_url.split('/')[-1]
                delete_file_from_s3(old_filename)
            
            # Generate a unique filename
            file_extension = os.path.splitext(image.filename)[1]
            unique_filename = f"newsletter_{datetime.now().strftime('%Y%m%d_%H%M%S')}{file_extension}"
            
            # Upload to S3
            image_url = upload_file_to_s3(image.file, unique_filename)
            if image_url:
                db_newsletter.image_url = image_url
            else:
                raise HTTPException(status_code=500, detail="Failed to upload image to S3")
        
        db.commit()
        db.refresh(db_newsletter)
        
        return db_newsletter
    except Exception as e:
        # If anything fails, rollback the database changes
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# Get image for a newsletter
from fastapi.responses import StreamingResponse
import boto3

@app.get("/newsletters/{newsletter_id}/image")
async def get_newsletter_image(newsletter_id: int, db: Session = Depends(get_db)):
    newsletter = db.query(models.Newsletter).filter(models.Newsletter.id == newsletter_id).first()
    if newsletter is None or not newsletter.image_url:
        raise HTTPException(status_code=404, detail="Image not found")

    # Extract filename from URL
    filename = newsletter.image_url.split('/')[-1]

    # Download file from S3
    s3 = boto3.client('s3')
    try:
        s3_response = s3.get_object(Bucket=os.getenv("S3_BUCKET_NAME"), Key=filename)
        return StreamingResponse(
            s3_response['Body'],
            media_type=s3_response['ContentType']
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stream image: {str(e)}")

@app.get("/newsletters/", response_model=List[schemas.Newsletter])
def read_newsletters(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    newsletters = db.query(models.Newsletter).offset(skip).limit(limit).all()
    return newsletters

@app.get("/newsletters/{newsletter_id}", response_model=schemas.Newsletter)
def read_newsletter(newsletter_id: int, db: Session = Depends(get_db)):
    newsletter = db.query(models.Newsletter).filter(models.Newsletter.id == newsletter_id).first()
    if newsletter is None:
        raise HTTPException(status_code=404, detail="Newsletter not found")
    return newsletter

@app.put("/newsletters/{newsletter_id}", response_model=schemas.Newsletter)
def update_newsletter(newsletter_id: int, newsletter: schemas.NewsletterUpdate, db: Session = Depends(get_db)):
    db_newsletter = db.query(models.Newsletter).filter(models.Newsletter.id == newsletter_id).first()
    if db_newsletter is None:
        raise HTTPException(status_code=404, detail="Newsletter not found")
    
    for key, value in newsletter.dict(exclude_unset=True).items():
        setattr(db_newsletter, key, value)
    
    db.commit()
    db.refresh(db_newsletter)
    return db_newsletter

@app.delete("/newsletters/{newsletter_id}")
def delete_newsletter(newsletter_id: int, db: Session = Depends(get_db)):
    newsletter = db.query(models.Newsletter).filter(models.Newsletter.id == newsletter_id).first()
    if newsletter is None:
        raise HTTPException(status_code=404, detail="Newsletter not found")
    
    # Delete image from S3 if exists
    if newsletter.image_url:
        # Extract the filename from the URL
        filename = newsletter.image_url.split('/')[-1]
        delete_file_from_s3(filename)
    
    db.delete(newsletter)
    db.commit()
    return {"message": "Newsletter deleted successfully"}

@app.get("/newsletters/status/{status}", response_model=List[schemas.Newsletter])
def read_newsletters_by_status(status: str, db: Session = Depends(get_db)):
    newsletters = db.query(models.Newsletter).filter(models.Newsletter.status == status).all()
    return newsletters 