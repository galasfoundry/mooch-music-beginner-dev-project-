from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import sqlite3

app = FastAPI(title="Musical Collaboration App")

# Add this to your existing main.py, typically near the top of the file, after the imports

@app.get("/")
def read_root():
    return {
        "message": "Welcome to the Musical Collaboration App",
        "available_endpoints": [
            "/users/create",
            "/rounds/start",
            "/compositions/upload",
            "/compositions/vote",
            "/rounds/current"
        ]
    }
    
# Database Connection Dependency
def get_db():
    conn = sqlite3.connect('music_collab.db')
    try:
        yield conn
    finally:
        conn.close()

# Pydantic Models for Request/Response Validation
class UserCreate(BaseModel):
    username: str

class CompositionCreate(BaseModel):
    username: str
    content: str

class CompositionResponse(BaseModel):
    id: int
    username: str
    content: str
    votes: int

# Database Initialization Function
def init_db(conn):
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL
        )
    ''')

    # Create compositions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS compositions (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            content TEXT,
            round_number INTEGER,
            timestamp DATETIME,
            votes INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    # Create rounds table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rounds (
            number INTEGER PRIMARY KEY,
            start_time DATETIME,
            end_time DATETIME,
            seed_composition_id INTEGER,
            FOREIGN KEY(seed_composition_id) REFERENCES compositions(id)
        )
    ''')

    conn.commit()

# User Creation Endpoint
@app.post("/users/create")
def create_user(user: UserCreate, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    try:
        cursor.execute("INSERT INTO users (username) VALUES (?)", (user.username,))
        db.commit()
        return {"username": user.username, "user_id": cursor.lastrowid}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Username already exists")

# Start New Round Endpoint
@app.post("/rounds/start")
def start_new_round(db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    
    # Determine the next round number
    cursor.execute("SELECT COALESCE(MAX(number), 0) + 1 FROM rounds")
    next_round_number = cursor.fetchone()[0]
    
    # Get current timestamp
    now = datetime.now()
    end_time = now + timedelta(hours=24)
    
    # Insert new round
    cursor.execute(
        "INSERT INTO rounds (number, start_time, end_time) VALUES (?, ?, ?)", 
        (next_round_number, now, end_time)
    )
    db.commit()
    
    return {
        "round_number": next_round_number, 
        "start_time": now.isoformat(), 
        "end_time": end_time.isoformat()
    }

# Composition Upload Endpoint
@app.post("/compositions/upload")
def upload_composition(
    composition: CompositionCreate, 
    db: sqlite3.Connection = Depends(get_db)
):
    cursor = db.cursor()
    
    # Find user
    cursor.execute("SELECT id FROM users WHERE username = ?", (composition.username,))
    user_result = cursor.fetchone()
    if not user_result:
        raise HTTPException(status_code=404, detail="User not found")
    user_id = user_result[0]
    
    # Find current round
    cursor.execute("SELECT number FROM rounds ORDER BY number DESC LIMIT 1")
    current_round = cursor.fetchone()
    if not current_round:
        raise HTTPException(status_code=400, detail="No active round")
    round_number = current_round[0]
    
    # Insert composition
    cursor.execute(
        "INSERT INTO compositions (user_id, content, round_number, timestamp, votes) VALUES (?, ?, ?, ?, 0)", 
        (user_id, composition.content, round_number, datetime.now())
    )
    db.commit()
    
    return {
        "composition_id": cursor.lastrowid, 
        "round_number": round_number
    }

# Voting Endpoint
@app.post("/compositions/vote")
def vote_composition(composition_id: int, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    
    # Check if composition exists
    cursor.execute("SELECT * FROM compositions WHERE id = ?", (composition_id,))
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="Composition not found")
    
    # Vote
    cursor.execute("UPDATE compositions SET votes = votes + 1 WHERE id = ?", (composition_id,))
    db.commit()
    
    # Fetch updated vote count
    cursor.execute("SELECT votes FROM compositions WHERE id = ?", (composition_id,))
    votes = cursor.fetchone()[0]
    
    return {"composition_id": composition_id, "votes": votes}

# Get Current Round Compositions
@app.get("/rounds/current", response_model=List[CompositionResponse])
def get_current_round(db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    
    # Find current round
    cursor.execute("SELECT number FROM rounds ORDER BY number DESC LIMIT 1")
    current_round = cursor.fetchone()
    if not current_round:
        raise HTTPException(status_code=404, detail="No active round")
    round_number = current_round[0]
    
    # Fetch compositions for current round
    cursor.execute("""
        SELECT c.id, u.username, c.content, c.votes 
        FROM compositions c
        JOIN users u ON c.user_id = u.id
        WHERE c.round_number = ?
    """, (round_number,))
    
    compositions = [
        CompositionResponse(
            id=row[0], 
            username=row[1], 
            content=row[2], 
            votes=row[3]
        ) for row in cursor.fetchall()
    ]
    
    return compositions

# Initialize database on startup
@app.on_event("startup")
def startup():
    conn = sqlite3.connect('music_collab.db')
    init_db(conn)
    conn.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
