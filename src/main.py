from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta

app = FastAPI(title="Musical Collaboration App")

# Simplified models
class User:
    def __init__(self, username: str):
        self.username = username
        self.id = hash(username)  # Simple unique identifier

class Composition:
    def __init__(self, user: User, content: str, round_number: int):
        self.id = hash(content)
        self.user = user
        self.content = content
        self.round_number = round_number
        self.timestamp = datetime.now()
        self.votes = 0

class Round:
    def __init__(self, number: int):
        self.number = number
        self.start_time = datetime.now()
        self.end_time = self.start_time + timedelta(hours=24)
        self.compositions: List[Composition] = []
        self.seed_composition: Optional[Composition] = None

class AppState:
    def __init__(self):
        self.users: List[User] = []
        self.rounds: List[Round] = []
        self.current_round: Optional[Round] = None

# Global app state (in a real app, this would be a database)
app_state = AppState()

@app.post("/users/create")
def create_user(username: str):
    # Check if user already exists
    if any(user.username == username for user in app_state.users):
        raise HTTPException(status_code=400, detail="Username already exists")
    
    new_user = User(username)
    app_state.users.append(new_user)
    return {"username": new_user.username, "user_id": new_user.id}

@app.post("/rounds/start")
def start_new_round():
    # Create a new round
    new_round_number = len(app_state.rounds) + 1
    new_round = Round(new_round_number)
    
    # If there's a previous round, potentially do something with it
    if app_state.current_round:
        # Logic for selecting seed composition would go here
        pass
    
    app_state.rounds.append(new_round)
    app_state.current_round = new_round
    
    return {
        "round_number": new_round.number, 
        "start_time": new_round.start_time, 
        "end_time": new_round.end_time
    }

@app.post("/compositions/upload")
def upload_composition(username: str, content: str):
    # Find user
    user = next((u for u in app_state.users if u.username == username), None)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Ensure we have an active round
    if not app_state.current_round:
        raise HTTPException(status_code=400, detail="No active round")
    
    # Create composition
    composition = Composition(
        user=user, 
        content=content, 
        round_number=app_state.current_round.number
    )
    
    # Add to current round
    app_state.current_round.compositions.append(composition)
    
    return {
        "composition_id": composition.id, 
        "round_number": composition.round_number
    }

@app.post("/compositions/vote")
def vote_composition(composition_id: int):
    # Find composition in current round
    if not app_state.current_round:
        raise HTTPException(status_code=400, detail="No active round")
    
    composition = next((c for c in app_state.current_round.compositions if c.id == composition_id), None)
    if not composition:
        raise HTTPException(status_code=404, detail="Composition not found")
    
    composition.votes += 1
    
    return {"composition_id": composition.id, "votes": composition.votes}

# Optional: Add a simple endpoint to get current round info
@app.get("/rounds/current")
def get_current_round():
    if not app_state.current_round:
        raise HTTPException(status_code=404, detail="No active round")
    
    return {
        "round_number": app_state.current_round.number,
        "start_time": app_state.current_round.start_time,
        "end_time": app_state.current_round.end_time,
        "compositions": [
            {
                "id": c.id, 
                "username": c.user.username, 
                "votes": c.votes
            } for c in app_state.current_round.compositions
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
