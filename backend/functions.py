from sqlalchemy.orm import Session
from tables import (
    engine, User, Player, Tournament, Match, FantasyTeam, FantasyTeamPlayer,
    Contest, ContestParticipant, PlayerPerformance, FantasyPointsHistory
)
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import jwt
from datetime import datetime, timedelta, timezone


# JWT SECRET KEY

SECRET_KEY = "ipl-fantasy-cricket-jwt-secret-key-2026"
ALGORITHM = "HS256"

# Password hashing object

password_hasher = PasswordHasher()


# FANTASY SCORING RULES

POINTS = {
    "run": 1,
    "four": 1,
    "six": 2,
    "wicket": 25,
    "catch": 8,
    "run_out": 12,
    "stumping": 12
}


# FANTASY TEAM RULES

MAX_PLAYERS = 11

ROLE_LIMITS = {
    "wicketkeeper": 4,
    "batsman": 6,
    "bowler": 6,
    "all-rounder": 4
}


# RESPONSE HELPERS

def fail(message, code):
    return {"error": message, "code": code, "data": None}


def ok(data, code=200):
    return {"error": None, "code": code, "data": data}


# CREATE TOKEN

def create_token(email, token_type):

    if token_type == "access":
        expiry = datetime.now(timezone.utc) + timedelta(minutes=30)
    else:
        expiry = datetime.now(timezone.utc) + timedelta(days=7)

    payload = {
        "sub": email,
        "type": token_type,
        "exp": expiry
    }

    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    return token


# VERIFY TOKEN

def verify_token(token, token_type):

    try:

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        email = payload.get("sub")
        actual_type = payload.get("type")

        if email is None or actual_type != token_type:
            return None

        return email

    except jwt.InvalidTokenError:
        return None


# GET LOGGED-IN USER FROM TOKEN

def get_user(session, token):

    if token is None:
        return None

    email = verify_token(token, "access")

    if email is None:
        return None

    return session.query(User).filter(User.email == email).first()


# CHECK THAT THE USER OWNS THE FANTASY TEAM

def team_error(session, user, team_id):

    if user.role != "user":
        return fail("User access required", 403)

    team = session.query(FantasyTeam).filter(FantasyTeam.id == team_id).first()

    if team is None:
        return fail("Fantasy team not found", 404)

    if team.user_id != user.id:
        return fail("This is not your fantasy team", 403)

    return None


# CHECK IF A MATCH DEADLINE HAS PASSED FOR ANY CONTEST THE TEAM JOINED

def team_locked(session, team_id):

    entries = session.query(ContestParticipant).filter(
        ContestParticipant.fantasy_team_id == team_id
    ).all()

    for entry in entries:

        contest = session.query(Contest).filter(Contest.id == entry.contest_id).first()
        match = session.query(Match).filter(Match.id == contest.match_id).first()

        if match.match_date < datetime.now():
            return True

    return False


# CHECK THAT THE ORGANIZER OWNS THE TOURNAMENT OF THE MATCH

def match_error(session, user, match_id):

    if user.role != "organizer":
        return fail("Organizer access required", 403)

    match = session.query(Match).filter(Match.id == match_id).first()

    if match is None:
        return fail("Match not found", 404)

    tournament = session.query(Tournament).filter(
        Tournament.id == match.tournament_id
    ).first()

    if tournament.organizer_id != user.id:
        return fail("This match is not in your tournament", 403)

    return None


def match_dict(match):

    return {
        "id": match.id,
        "tournament_id": match.tournament_id,
        "team1": match.team1,
        "team2": match.team2,
        "match_date": match.match_date
    }


# CREATE DEFAULT ADMIN

def create_admin():

    session = Session(engine)

    admin = session.query(User).filter(User.role == "admin").first()

    if admin is None:
        new_admin = User(
            username="Admin",
            email="admin@ipl.com",
            password=password_hasher.hash("admin123"),
            role="admin"
        )
        session.add(new_admin)
        session.commit()

    session.close()


# A1 - REGISTER USER

def register_user(username, email, password):

    session = Session(engine)

    existing_user = session.query(User).filter(User.email == email).first()

    if existing_user:
        session.close()
        return None

    hashed_password = password_hasher.hash(password)

    new_user = User(
        username=username,
        email=email,
        password=hashed_password,
        role="user"
    )

    session.add(new_user)
    session.commit()

    session.close()

    return True


# A2 - LOGIN USER

def login_user(email, password):

    session = Session(engine)

    user = session.query(User).filter(User.email == email).first()

    if user is None:
        session.close()
        return None

    try:
        password_hasher.verify(user.password, password)

    except VerifyMismatchError:
        session.close()
        return None

    access_token = create_token(user.email, "access")
    refresh_token = create_token(user.email, "refresh")
    role = user.role

    session.close()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "role": role
    }


# A3 - GENERATE NEW ACCESS TOKEN

def refresh_access_token(refresh_token):

    email = verify_token(refresh_token, "refresh")

    if email is None:
        return None

    new_access_token = create_token(email, "access")

    return new_access_token


# E1 - CREATE ORGANIZER ACCOUNT

def create_organizer(token, username, email, password):

    session = Session(engine)

    user = get_user(session, token)

    if user is None:
        session.close()
        return fail("Invalid or missing access token", 401)

    if user.role != "admin":
        session.close()
        return fail("Admin access required", 403)

    existing_user = session.query(User).filter(User.email == email).first()

    if existing_user:
        session.close()
        return fail("Email already exists", 409)

    new_user = User(
        username=username,
        email=email,
        password=password_hasher.hash(password),
        role="organizer"
    )

    session.add(new_user)
    session.commit()
    session.refresh(new_user)

    response = {
        "id": new_user.id,
        "username": new_user.username,
        "email": new_user.email,
        "role": new_user.role
    }

    session.close()

    return ok(response, 201)


# E2 - ADD A CRICKET PLAYER

def add_player(token, name, role, team, base_points):

    session = Session(engine)

    user = get_user(session, token)

    if user is None:
        session.close()
        return fail("Invalid or missing access token", 401)

    if user.role != "organizer":
        session.close()
        return fail("Organizer access required", 403)

    existing_player = session.query(Player).filter(
        Player.name == name,
        Player.team == team
    ).first()

    if existing_player:
        session.close()
        return fail("This player already exists in that team", 409)

    new_player = Player(
        name=name,
        role=role,
        team=team,
        base_points=base_points
    )

    session.add(new_player)
    session.commit()
    session.refresh(new_player)

    response = {
        "id": new_player.id,
        "name": new_player.name,
        "role": new_player.role,
        "team": new_player.team,
        "base_points": new_player.base_points
    }

    session.close()

    return ok(response, 201)


# E3 - GET ALL CRICKET PLAYERS

def get_all_players(token):

    session = Session(engine)

    user = get_user(session, token)

    if user is None:
        session.close()
        return fail("Invalid or missing access token", 401)

    players = session.query(Player).all()

    response = []

    for player in players:

        temp_player = {
            "id": player.id,
            "name": player.name,
            "role": player.role,
            "team": player.team,
            "base_points": player.base_points
        }

        response.append(temp_player)

    session.close()

    return ok(response)


# E4 - GET ONE CRICKET PLAYER

def get_player(token, player_id):

    session = Session(engine)

    user = get_user(session, token)

    if user is None:
        session.close()
        return fail("Invalid or missing access token", 401)

    player = session.query(Player).filter(Player.id == player_id).first()

    if player is None:
        session.close()
        return fail("Player not found", 404)

    response = {
        "id": player.id,
        "name": player.name,
        "role": player.role,
        "team": player.team,
        "base_points": player.base_points
    }

    session.close()

    return ok(response)


# E5 - CREATE A TOURNAMENT (WITH ITS MATCHES)

def create_tournament(token, name, season, matches):

    session = Session(engine)

    user = get_user(session, token)

    if user is None:
        session.close()
        return fail("Invalid or missing access token", 401)

    if user.role != "organizer":
        session.close()
        return fail("Organizer access required", 403)

    for m in matches:
        if m.team1.strip().lower() == m.team2.strip().lower():
            session.close()
            return fail("A match needs two different teams", 400)

    new_tournament = Tournament(
        name=name,
        season=season,
        organizer_id=user.id
    )

    session.add(new_tournament)
    session.commit()
    session.refresh(new_tournament)

    match_list = []

    for m in matches:

        new_match = Match(
            tournament_id=new_tournament.id,
            team1=m.team1,
            team2=m.team2,
            match_date=m.match_date.replace(tzinfo=None)
        )

        session.add(new_match)
        session.commit()
        session.refresh(new_match)

        match_list.append(match_dict(new_match))

    response = {
        "id": new_tournament.id,
        "name": new_tournament.name,
        "season": new_tournament.season,
        "organizer_id": new_tournament.organizer_id,
        "matches": match_list
    }

    session.close()

    return ok(response, 201)


# E6 - GET ALL TOURNAMENTS

def get_all_tournaments(token):

    session = Session(engine)

    user = get_user(session, token)

    if user is None:
        session.close()
        return fail("Invalid or missing access token", 401)

    tournaments = session.query(Tournament).all()

    response = []

    for t in tournaments:

        matches = session.query(Match).filter(Match.tournament_id == t.id).all()

        match_list = []

        for m in matches:
            match_list.append(match_dict(m))

        temp_tournament = {
            "id": t.id,
            "name": t.name,
            "season": t.season,
            "organizer_id": t.organizer_id,
            "matches": match_list
        }

        response.append(temp_tournament)

    session.close()

    return ok(response)


# E7 - CREATE A FANTASY TEAM

def create_team(token, name):

    session = Session(engine)

    user = get_user(session, token)

    if user is None:
        session.close()
        return fail("Invalid or missing access token", 401)

    if user.role != "user":
        session.close()
        return fail("User access required", 403)

    new_team = FantasyTeam(
        name=name,
        user_id=user.id
    )

    session.add(new_team)
    session.commit()
    session.refresh(new_team)

    response = {
        "id": new_team.id,
        "name": new_team.name,
        "user_id": new_team.user_id,
        "players": []
    }

    session.close()

    return ok(response, 201)


# E8 - ADD A PLAYER TO A FANTASY TEAM

def add_player_to_team(token, team_id, player_id):

    session = Session(engine)

    user = get_user(session, token)

    if user is None:
        session.close()
        return fail("Invalid or missing access token", 401)

    problem = team_error(session, user, team_id)

    if problem is not None:
        session.close()
        return problem

    player = session.query(Player).filter(Player.id == player_id).first()

    if player is None:
        session.close()
        return fail("Player not found", 404)

    if team_locked(session, team_id):
        session.close()
        return fail("Match deadline has passed, team cannot be changed", 400)

    existing = session.query(FantasyTeamPlayer).filter(
        FantasyTeamPlayer.fantasy_team_id == team_id,
        FantasyTeamPlayer.player_id == player_id
    ).first()

    if existing:
        session.close()
        return fail("Player is already in this team", 409)

    links = session.query(FantasyTeamPlayer).filter(
        FantasyTeamPlayer.fantasy_team_id == team_id
    ).all()

    if len(links) >= MAX_PLAYERS:
        session.close()
        return fail("A fantasy team can have only " + str(MAX_PLAYERS) + " players", 400)

    role_count = 0

    for link in links:

        team_player = session.query(Player).filter(Player.id == link.player_id).first()

        if team_player.role == player.role:
            role_count += 1

    if role_count >= ROLE_LIMITS[player.role]:
        session.close()
        return fail(
            "Role limit reached: maximum " + str(ROLE_LIMITS[player.role]) + " " + player.role + " players",
            400
        )

    new_link = FantasyTeamPlayer(
        fantasy_team_id=team_id,
        player_id=player_id
    )

    session.add(new_link)
    session.commit()

    response = {
        "fantasy_team_id": team_id,
        "player_id": player_id,
        "players_in_team": len(links) + 1
    }

    session.close()

    return ok(response, 201)


# E9 - REMOVE A PLAYER FROM A FANTASY TEAM

def remove_player_from_team(token, team_id, player_id):

    session = Session(engine)

    user = get_user(session, token)

    if user is None:
        session.close()
        return fail("Invalid or missing access token", 401)

    problem = team_error(session, user, team_id)

    if problem is not None:
        session.close()
        return problem

    link = session.query(FantasyTeamPlayer).filter(
        FantasyTeamPlayer.fantasy_team_id == team_id,
        FantasyTeamPlayer.player_id == player_id
    ).first()

    if link is None:
        session.close()
        return fail("Player is not in this team", 404)

    if team_locked(session, team_id):
        session.close()
        return fail("Match deadline has passed, team cannot be changed", 400)

    session.delete(link)
    session.commit()

    count = session.query(FantasyTeamPlayer).filter(
        FantasyTeamPlayer.fantasy_team_id == team_id
    ).count()

    session.close()

    return ok({"message": "Player removed", "players_in_team": count})


# E10 - GET LOGGED-IN USER'S FANTASY TEAMS

def get_my_teams(token):

    session = Session(engine)

    user = get_user(session, token)

    if user is None:
        session.close()
        return fail("Invalid or missing access token", 401)

    if user.role != "user":
        session.close()
        return fail("User access required", 403)

    teams = session.query(FantasyTeam).filter(FantasyTeam.user_id == user.id).all()

    response = []

    for team in teams:

        links = session.query(FantasyTeamPlayer).filter(
            FantasyTeamPlayer.fantasy_team_id == team.id
        ).all()

        player_list = []

        for link in links:

            player = session.query(Player).filter(Player.id == link.player_id).first()

            temp_player = {
                "id": player.id,
                "name": player.name,
                "role": player.role,
                "team": player.team
            }

            player_list.append(temp_player)

        temp_team = {
            "id": team.id,
            "name": team.name,
            "total_players": len(player_list),
            "players": player_list
        }

        response.append(temp_team)

    session.close()

    return ok(response)


# E11 - CREATE A CONTEST FOR A MATCH

def create_contest(token, name, match_id):

    session = Session(engine)

    user = get_user(session, token)

    if user is None:
        session.close()
        return fail("Invalid or missing access token", 401)

    problem = match_error(session, user, match_id)

    if problem is not None:
        session.close()
        return problem

    new_contest = Contest(
        name=name,
        match_id=match_id,
        organizer_id=user.id
    )

    session.add(new_contest)
    session.commit()
    session.refresh(new_contest)

    response = {
        "id": new_contest.id,
        "name": new_contest.name,
        "match_id": new_contest.match_id,
        "organizer_id": new_contest.organizer_id
    }

    session.close()

    return ok(response, 201)


# E12 - JOIN A CONTEST USING A FANTASY TEAM

def join_contest(token, contest_id, team_id):

    session = Session(engine)

    user = get_user(session, token)

    if user is None:
        session.close()
        return fail("Invalid or missing access token", 401)

    problem = team_error(session, user, team_id)

    if problem is not None:
        session.close()
        return problem

    contest = session.query(Contest).filter(Contest.id == contest_id).first()

    if contest is None:
        session.close()
        return fail("Contest not found", 404)

    match = session.query(Match).filter(Match.id == contest.match_id).first()

    if match.match_date < datetime.now():
        session.close()
        return fail("Match deadline has passed, contest is closed", 400)

    same_team = session.query(ContestParticipant).filter(
        ContestParticipant.contest_id == contest_id,
        ContestParticipant.fantasy_team_id == team_id
    ).first()

    if same_team:
        session.close()
        return fail("This team already joined this contest", 409)

    same_user = session.query(ContestParticipant).filter(
        ContestParticipant.contest_id == contest_id,
        ContestParticipant.user_id == user.id
    ).first()

    if same_user:
        session.close()
        return fail("You already joined this contest with another team", 409)

    new_entry = ContestParticipant(
        contest_id=contest_id,
        fantasy_team_id=team_id,
        user_id=user.id
    )

    new_history = FantasyPointsHistory(
        user_id=user.id,
        contest_id=contest_id,
        match_id=contest.match_id,
        points=0
    )

    session.add(new_entry)
    session.add(new_history)
    session.commit()
    session.refresh(new_entry)

    response = {
        "participant_id": new_entry.id,
        "contest_id": contest_id,
        "fantasy_team_id": team_id,
        "message": "Joined contest successfully"
    }

    session.close()

    return ok(response, 201)


# E13 - PUBLISH PLAYER PERFORMANCE STATISTICS FOR A MATCH

def publish_stats(token, match_id, stats):

    session = Session(engine)

    user = get_user(session, token)

    if user is None:
        session.close()
        return fail("Invalid or missing access token", 401)

    problem = match_error(session, user, match_id)

    if problem is not None:
        session.close()
        return problem

    seen = []

    for s in stats:

        if s.player_id in seen:
            session.close()
            return fail("Player " + str(s.player_id) + " appears more than once", 400)

        seen.append(s.player_id)

        player = session.query(Player).filter(Player.id == s.player_id).first()

        if player is None:
            session.close()
            return fail("Player " + str(s.player_id) + " not found", 404)

    published = []

    for s in stats:

        points = (
            s.runs * POINTS["run"]
            + s.fours * POINTS["four"]
            + s.sixes * POINTS["six"]
            + s.wickets * POINTS["wicket"]
            + s.catches * POINTS["catch"]
            + s.run_outs * POINTS["run_out"]
            + s.stumpings * POINTS["stumping"]
        )

        performance = session.query(PlayerPerformance).filter(
            PlayerPerformance.match_id == match_id,
            PlayerPerformance.player_id == s.player_id
        ).first()

        if performance is None:
            performance = PlayerPerformance(match_id=match_id, player_id=s.player_id)
            session.add(performance)

        performance.runs = s.runs
        performance.fours = s.fours
        performance.sixes = s.sixes
        performance.wickets = s.wickets
        performance.catches = s.catches
        performance.run_outs = s.run_outs
        performance.stumpings = s.stumpings
        performance.fantasy_points = points

        published.append({"player_id": s.player_id, "fantasy_points": points})

    session.commit()

    contests = session.query(Contest).filter(Contest.match_id == match_id).all()

    for contest in contests:

        entries = session.query(ContestParticipant).filter(
            ContestParticipant.contest_id == contest.id
        ).all()

        for entry in entries:

            total = 0

            team_players = session.query(FantasyTeamPlayer).filter(
                FantasyTeamPlayer.fantasy_team_id == entry.fantasy_team_id
            ).all()

            for tp in team_players:

                perf = session.query(PlayerPerformance).filter(
                    PlayerPerformance.match_id == match_id,
                    PlayerPerformance.player_id == tp.player_id
                ).first()

                if perf is not None:
                    total += perf.fantasy_points

            history = session.query(FantasyPointsHistory).filter(
                FantasyPointsHistory.user_id == entry.user_id,
                FantasyPointsHistory.contest_id == contest.id
            ).first()

            if history is None:
                history = FantasyPointsHistory(
                    user_id=entry.user_id,
                    contest_id=contest.id,
                    match_id=match_id
                )
                session.add(history)

            history.points = total

    session.commit()

    session.close()

    return ok({"match_id": match_id, "published": published})


# E14 - GET THE CONTEST LEADERBOARD

def get_leaderboard(token, contest_id):

    session = Session(engine)

    user = get_user(session, token)

    if user is None:
        session.close()
        return fail("Invalid or missing access token", 401)

    contest = session.query(Contest).filter(Contest.id == contest_id).first()

    if contest is None:
        session.close()
        return fail("Contest not found", 404)

    rows = session.query(FantasyPointsHistory).filter(
        FantasyPointsHistory.contest_id == contest_id
    ).order_by(
        FantasyPointsHistory.points.desc(),
        FantasyPointsHistory.id
    ).all()

    leaderboard = []

    position = 0
    rank = 0
    last_points = None

    for row in rows:

        position += 1

        if row.points != last_points:
            rank = position
            last_points = row.points

        player_user = session.query(User).filter(User.id == row.user_id).first()

        entry = session.query(ContestParticipant).filter(
            ContestParticipant.contest_id == contest_id,
            ContestParticipant.user_id == row.user_id
        ).first()

        team = session.query(FantasyTeam).filter(
            FantasyTeam.id == entry.fantasy_team_id
        ).first()

        temp_row = {
            "rank": rank,
            "user_id": player_user.id,
            "username": player_user.username,
            "fantasy_team": team.name,
            "points": row.points
        }

        leaderboard.append(temp_row)

    response = {
        "contest_id": contest.id,
        "contest_name": contest.name,
        "leaderboard": leaderboard
    }

    session.close()

    return ok(response)


# E15 - GET LOGGED-IN USER'S FANTASY POINTS HISTORY

def get_points_history(token):

    session = Session(engine)

    user = get_user(session, token)

    if user is None:
        session.close()
        return fail("Invalid or missing access token", 401)

    if user.role != "user":
        session.close()
        return fail("User access required", 403)

    rows = session.query(FantasyPointsHistory).filter(
        FantasyPointsHistory.user_id == user.id
    ).all()

    history = []

    total = 0

    for row in rows:

        contest = session.query(Contest).filter(Contest.id == row.contest_id).first()
        match = session.query(Match).filter(Match.id == row.match_id).first()

        temp_row = {
            "contest_id": contest.id,
            "contest_name": contest.name,
            "match_id": match.id,
            "match": match.team1 + " vs " + match.team2,
            "match_date": match.match_date,
            "points": row.points
        }

        total += row.points

        history.append(temp_row)

    session.close()

    return ok({"total_points": total, "history": history})