from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base
import os

os.makedirs("data", exist_ok=True)

DATABASE_URL = "sqlite:///./data/ipl.db"

engine = create_engine(DATABASE_URL)

Base = declarative_base()

# USER TABLE
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, default="user")


# PLAYER TABLE
class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    team = Column(String, nullable=False)
    base_points = Column(Integer, default=0)


# TOURNAMENT TABLE
class Tournament(Base):
    __tablename__ = "tournaments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    season = Column(String)
    organizer_id = Column(Integer, ForeignKey("users.id"))


# MATCH TABLE
class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"))
    team1 = Column(String, nullable=False)
    team2 = Column(String, nullable=False)
    match_date = Column(DateTime)


# FANTASY TEAM TABLE
class FantasyTeam(Base):
    __tablename__ = "fantasy_teams" 

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))


# FANTASY TEAM PLAYERS TABLE
class FantasyTeamPlayer(Base):
    __tablename__ = "fantasy_team_players"

    id = Column(Integer, primary_key=True, index=True)
    fantasy_team_id = Column(Integer, ForeignKey("fantasy_teams.id"))
    player_id = Column(Integer, ForeignKey("players.id"))


# CONTEST TABLE
class Contest(Base):
    __tablename__ = "contests"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    match_id = Column(Integer, ForeignKey("matches.id"))
    organizer_id = Column(Integer, ForeignKey("users.id"))


# CONTEST PARTICIPANTS TABLE
class ContestParticipant(Base):
    __tablename__ = "contest_participants"

    id = Column(Integer, primary_key=True, index=True)
    contest_id = Column(Integer, ForeignKey("contests.id"))
    fantasy_team_id = Column(Integer, ForeignKey("fantasy_teams.id"))
    user_id = Column(Integer, ForeignKey("users.id"))


# PLAYER PERFORMANCE TABLE
class PlayerPerformance(Base):
    __tablename__ = "player_performances"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id"))
    player_id = Column(Integer, ForeignKey("players.id"))
    runs = Column(Integer, default=0)
    fours = Column(Integer, default=0)
    sixes = Column(Integer, default=0)
    wickets = Column(Integer, default=0)
    catches = Column(Integer, default=0)
    run_outs = Column(Integer, default=0)
    stumpings = Column(Integer, default=0)
    fantasy_points = Column(Integer, default=0)


# FANTASY POINTS HISTORY TABLE
class FantasyPointsHistory(Base):
    __tablename__ = "fantasy_points_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    contest_id = Column(Integer, ForeignKey("contests.id"))
    match_id = Column(Integer, ForeignKey("matches.id"))
    points = Column(Integer, default=0)


Base.metadata.create_all(engine)
