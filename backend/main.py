from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, EmailStr
import functions


app = FastAPI(
    title="IPL - Fantasy Cricket League"
    )

functions.create_admin()


# REQUEST MODELS

class RegisterModel(BaseModel):
    username: str = Field(min_length=1)
    email: EmailStr
    password: str = Field(min_length=1)


class LoginModel(BaseModel):
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)


class RefreshToken(BaseModel):
    refresh_token: str


class PlayerModel(BaseModel):
    name: str = Field(min_length=1)
    role: str = Field(pattern="^(batsman|bowler|all-rounder|wicketkeeper)$")
    team: str = Field(min_length=1)
    base_points: int = Field(ge=0)


class MatchModel(BaseModel):
    team1: str = Field(min_length=1)
    team2: str = Field(min_length=1)
    match_date: datetime


class TournamentModel(BaseModel):
    name: str = Field(min_length=1)
    season: Optional[str] = None
    matches: List[MatchModel] = Field(min_length=1)


class TeamModel(BaseModel):
    name: str = Field(min_length=1)


class AddPlayerModel(BaseModel):
    player_id: int


class ContestModel(BaseModel):
    name: str = Field(min_length=1)
    match_id: int


class JoinModel(BaseModel):
    fantasy_team_id: int


class StatModel(BaseModel):
    player_id: int
    runs: int = Field(default=0, ge=0)
    fours: int = Field(default=0, ge=0)
    sixes: int = Field(default=0, ge=0)
    wickets: int = Field(default=0, ge=0)
    catches: int = Field(default=0, ge=0)
    run_outs: int = Field(default=0, ge=0)
    stumpings: int = Field(default=0, ge=0)


class StatsModel(BaseModel):
    stats: List[StatModel] = Field(min_length=1)


# A1 - REGISTER USER

@app.post("/auth/register", status_code=201)
def register_user(data: RegisterModel):

    result = functions.register_user(
        data.username,
        data.email,
        data.password
    )

    if result is None:
        raise HTTPException(status_code=409, detail="Email already exists")

    return {
        "message": "User registered successfully"
    }


# A2 - LOGIN USER

@app.post("/auth/login")
def login_user(data: LoginModel):

    result = functions.login_user(
        data.email,
        data.password
    )

    if result is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return result


# A3 - GENERATE NEW ACCESS TOKEN

@app.post("/auth/refresh")
def refresh_token(data: RefreshToken):

    new_access_token = functions.refresh_access_token(data.refresh_token)

    if new_access_token is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    return {
        "access_token": new_access_token
    }


# E1 - CREATE ORGANIZER ACCOUNT

@app.post("/admin/organizers", status_code=201)
def create_organizer(data: RegisterModel, token: str = Header(None)):

    result = functions.create_organizer(
        token,
        data.username,
        data.email,
        data.password
    )

    if result["error"] is not None:
        raise HTTPException(status_code=result["code"], detail=result["error"])

    return result["data"]


# E2 - ADD A CRICKET PLAYER

@app.post("/players", status_code=201)
def add_player(data: PlayerModel, token: str = Header(None)):

    result = functions.add_player(
        token,
        data.name,
        data.role,
        data.team,
        data.base_points
    )

    if result["error"] is not None:
        raise HTTPException(status_code=result["code"], detail=result["error"])

    return result["data"]


# E3 - GET ALL CRICKET PLAYERS

@app.get("/players")
def get_all_players(token: str = Header(None)):

    result = functions.get_all_players(token)

    if result["error"] is not None:
        raise HTTPException(status_code=result["code"], detail=result["error"])

    return {
        "players": result["data"]
    }


# E4 - GET ONE CRICKET PLAYER

@app.get("/players/{player_id}")
def get_player(player_id: int, token: str = Header(None)):

    result = functions.get_player(token, player_id)

    if result["error"] is not None:
        raise HTTPException(status_code=result["code"], detail=result["error"])

    return result["data"]


# E5 - CREATE A TOURNAMENT (WITH ITS MATCHES)

@app.post("/tournaments", status_code=201)
def create_tournament(data: TournamentModel, token: str = Header(None)):

    result = functions.create_tournament(
        token,
        data.name,
        data.season,
        data.matches
    )

    if result["error"] is not None:
        raise HTTPException(status_code=result["code"], detail=result["error"])

    return result["data"]


# E6 - GET ALL TOURNAMENTS

@app.get("/tournaments")
def get_all_tournaments(token: str = Header(None)):

    result = functions.get_all_tournaments(token)

    if result["error"] is not None:
        raise HTTPException(status_code=result["code"], detail=result["error"])

    return {
        "tournaments": result["data"]
    }


# E7 - CREATE A FANTASY TEAM

@app.post("/fantasy-teams", status_code=201)
def create_team(data: TeamModel, token: str = Header(None)):

    result = functions.create_team(token, data.name)

    if result["error"] is not None:
        raise HTTPException(status_code=result["code"], detail=result["error"])

    return result["data"]


# E8 - ADD A PLAYER TO A FANTASY TEAM

@app.post("/fantasy-teams/{team_id}/players", status_code=201)
def add_player_to_team(team_id: int, data: AddPlayerModel, token: str = Header(None)):

    result = functions.add_player_to_team(token, team_id, data.player_id)

    if result["error"] is not None:
        raise HTTPException(status_code=result["code"], detail=result["error"])

    return result["data"]


# E9 - REMOVE A PLAYER FROM A FANTASY TEAM

@app.delete("/fantasy-teams/{team_id}/players/{player_id}")
def remove_player_from_team(team_id: int, player_id: int, token: str = Header(None)):

    result = functions.remove_player_from_team(token, team_id, player_id)

    if result["error"] is not None:
        raise HTTPException(status_code=result["code"], detail=result["error"])

    return result["data"]


# E10 - GET LOGGED-IN USER'S FANTASY TEAMS

@app.get("/fantasy-teams")
def get_my_teams(token: str = Header(None)):

    result = functions.get_my_teams(token)

    if result["error"] is not None:
        raise HTTPException(status_code=result["code"], detail=result["error"])

    return {
        "teams": result["data"]
    }


# E11 - CREATE A CONTEST FOR A MATCH

@app.post("/contests", status_code=201)
def create_contest(data: ContestModel, token: str = Header(None)):

    result = functions.create_contest(token, data.name, data.match_id)

    if result["error"] is not None:
        raise HTTPException(status_code=result["code"], detail=result["error"])

    return result["data"]


# E12 - JOIN A CONTEST USING A FANTASY TEAM

@app.post("/contests/{contest_id}/join", status_code=201)
def join_contest(contest_id: int, data: JoinModel, token: str = Header(None)):

    result = functions.join_contest(token, contest_id, data.fantasy_team_id)

    if result["error"] is not None:
        raise HTTPException(status_code=result["code"], detail=result["error"])

    return result["data"]


# E13 - PUBLISH PLAYER PERFORMANCE STATISTICS FOR A MATCH

@app.post("/matches/{match_id}/stats")
def publish_stats(match_id: int, data: StatsModel, token: str = Header(None)):

    result = functions.publish_stats(token, match_id, data.stats)

    if result["error"] is not None:
        raise HTTPException(status_code=result["code"], detail=result["error"])

    return result["data"]


# E14 - GET THE CONTEST LEADERBOARD

@app.get("/contests/{contest_id}/leaderboard")
def get_leaderboard(contest_id: int, token: str = Header(None)):

    result = functions.get_leaderboard(token, contest_id)

    if result["error"] is not None:
        raise HTTPException(status_code=result["code"], detail=result["error"])

    return result["data"]


# E15 - GET LOGGED-IN USER'S FANTASY POINTS HISTORY

@app.get("/users/me/points-history")
def get_points_history(token: str = Header(None)):

    result = functions.get_points_history(token)

    if result["error"] is not None:
        raise HTTPException(status_code=result["code"], detail=result["error"])

    return result["data"]