import os, tempfile
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import create_engine, String, Text, DateTime, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

URL=os.getenv('DATABASE_URL','sqlite:///./transcriptions.db')
if URL.startswith('mysql://'): URL=URL.replace('mysql://','mysql+pymysql://',1)
engine=create_engine(URL,connect_args={'check_same_thread':False} if URL.startswith('sqlite') else {},pool_pre_ping=True)
Session=sessionmaker(bind=engine,autoflush=False,autocommit=False)
class Base(DeclarativeBase): pass
class Transcript(Base):
    __tablename__='transcriptions'
    id:Mapped[int]=mapped_column(Integer,primary_key=True,index=True)
    text:Mapped[str]=mapped_column(Text,nullable=False)
    language:Mapped[Optional[str]]=mapped_column(String(80),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,nullable=False)
Base.metadata.create_all(engine)
app=FastAPI(title='Speechly Speech-to-Text API',version='1.0.0')
app.mount('/static',StaticFiles(directory='app/static'),name='static')
_model=None
def model():
    global _model

    if _model is None:
        import os
        from faster_whisper import WhisperModel

        os.environ["HF_HOME"] = "/tmp/huggingface"
        os.environ["HUGGINGFACE_HUB_CACHE"] = "/tmp/huggingface/hub"
        os.environ["TMPDIR"] = "/tmp"

        device = os.getenv("WHISPER_DEVICE", "cpu")
        compute_type = os.getenv(
            "WHISPER_COMPUTE_TYPE",
            "int8" if device == "cpu" else "float16"
        )

        _model = WhisperModel(
            os.getenv("WHISPER_MODEL", "tiny"),
            device=device,
            compute_type=compute_type,
            download_root="/tmp/faster-whisper"
        )

    return _model
@app.get('/')
def home(): return FileResponse('app/static/index.html')
@app.get('/api/health')
def health(): return {'status':'ok'}
@app.post('/api/transcribe')
async def transcribe(audio:UploadFile=File(...),save:bool=True):
    if not audio.content_type or not (audio.content_type.startswith('audio/') or audio.content_type=='application/octet-stream'): raise HTTPException(415,'Please upload audio.')
    raw=await audio.read()
    if not raw: raise HTTPException(400,'Audio is empty.')
    if len(raw)>15*1024*1024: raise HTTPException(413,'Audio chunk exceeds 15 MB.')
    path=None
    try:
        with tempfile.NamedTemporaryFile(suffix='.webm',delete=False) as f: f.write(raw); path=f.name
        segments, info = model().transcribe(
    path,
    beam_size=1,
    vad_filter=False
)

        text=' '.join(s.text.strip() for s in segments).strip(); lang=getattr(info,'language',None)
    except Exception as e: raise HTTPException(500,'Transcription failed: '+str(e)[:200])
    finally:
        if path and os.path.exists(path): os.unlink(path)
    record_id=None
    if save and text:
        db=Session()
        try:
            row=Transcript(text=text,language=lang); db.add(row); db.commit(); db.refresh(row); record_id=row.id
        finally: db.close()
    return {'id':record_id,'text':text,'language':lang}
def serialize(r): return {'id':r.id,'text':r.text,'language':r.language,'created_at':r.created_at.isoformat()+'Z'}
@app.get('/api/transcriptions')
def listing(q:Optional[str]=None,limit:int=100,offset:int=0):
    db=Session()
    try:
        query=db.query(Transcript)
        if q: query=query.filter(Transcript.text.ilike(f'%{q}%'))
        total=query.count(); rows=query.order_by(Transcript.created_at.desc()).offset(max(0,offset)).limit(min(max(1,limit),200)).all()
        return {'items':[serialize(r) for r in rows],'total':total}
    finally: db.close()
@app.post('/api/transcriptions/manual')
def create(body:dict):
    text=str(body.get('text','')).strip()
    if not text: raise HTTPException(400,'Text cannot be empty')
    db=Session()
    try:
        r=Transcript(text=text); db.add(r); db.commit(); db.refresh(r); return serialize(r)
    finally: db.close()
@app.get('/api/transcriptions/{record_id}')
def get_one(record_id:int):
    db=Session()
    try:
        r=db.get(Transcript,record_id)
        if not r: raise HTTPException(404,'Transcription not found')
        return serialize(r)
    finally: db.close()
class UpdateBody(BaseModel): text:str
@app.put('/api/transcriptions/{record_id}')
def update(record_id:int,body:UpdateBody):
    text=body.text.strip()
    if not text: raise HTTPException(400,'Text cannot be empty')
    db=Session()
    try:
        r=db.get(Transcript,record_id)
        if not r: raise HTTPException(404,'Transcription not found')
        r.text=text; db.commit(); db.refresh(r); return serialize(r)
    finally: db.close()
@app.delete('/api/transcriptions/{record_id}')
def delete(record_id:int):
    db=Session()
    try:
        r=db.get(Transcript,record_id)
        if not r: raise HTTPException(404,'Transcription not found')
        db.delete(r); db.commit(); return {'deleted':True,'id':record_id}
    finally: db.close()
