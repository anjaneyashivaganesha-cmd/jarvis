"""Filmmaker tools — script writing, movie lookup, shot lists, rehearsal, film knowledge."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.tools.registry import tool
from app.tools.system import run_powershell

log = logging.getLogger("jarvis.tools.filmmaker")

# Project storage
_projects: list[dict] = []
_shot_lists: list[dict] = []
_cast_notes: list[dict] = []
_location_notes: list[dict] = []


@tool(
    name="movie_lookup",
    description="Look up a movie's details — director, cast, rating, plot. Use when user asks about any movie.",
    input_schema={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Movie title to look up"},
        },
        "required": ["title"],
    },
)
async def movie_lookup_tool(input_data: dict[str, Any]) -> str:
    title = input_data["title"]
    try:
        import urllib.parse
        encoded = urllib.parse.quote(title)
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            # Try OMDB first
            resp = await client.get(f"https://www.omdbapi.com/?t={encoded}&apikey=82854847")
            if resp.status_code == 200:
                d = resp.json()
                if d.get("Response") == "True":
                    return (f"{d.get('Title', title)} ({d.get('Year', '?')}) — "
                            f"Directed by {d.get('Director', 'N/A')}. "
                            f"Starring {d.get('Actors', 'N/A')}. "
                            f"Rating: {d.get('imdbRating', 'N/A')}/10. "
                            f"Genre: {d.get('Genre', 'N/A')}. "
                            f"{d.get('Plot', '')}")
            # Fallback: open IMDB search
            await run_powershell(f"Start-Process 'https://www.imdb.com/find/?q={encoded}'")
            return f"Opened IMDB search for: {title}"
    except Exception as e:
        return f"Movie lookup failed: {e}"


@tool(
    name="find_similar_movies",
    description="Search for movies by genre, theme, or style. Use when user asks 'movies like Inception' or 'action movies'.",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Genre, theme, or 'movies like X'"},
        },
        "required": ["query"],
    },
)
async def find_similar_movies_tool(input_data: dict[str, Any]) -> str:
    query = input_data["query"].replace(" ", "+").replace("'", "")
    script = f"Start-Process 'https://www.google.com/search?q=best+{query}+movies+list'"
    await run_powershell(script)
    return f"Searching for: {input_data['query']} — opened in browser"


@tool(
    name="film_term",
    description="Explain a filmmaking term. Use when user asks 'what is a dutch angle', 'explain jump cut'.",
    input_schema={
        "type": "object",
        "properties": {
            "term": {"type": "string", "description": "Film term to explain"},
        },
        "required": ["term"],
    },
)
async def film_term_tool(input_data: dict[str, Any]) -> str:
    terms = {
        "dutch angle": "A tilted camera angle creating unease or disorientation. Used in horror and thriller films.",
        "jump cut": "An abrupt cut between two shots of the same subject, creating a jarring time skip effect.",
        "tracking shot": "Camera moves alongside the subject, following their movement through space.",
        "dolly zoom": "Camera dollies in while zooming out (or vice versa), creating a vertigo effect. Made famous by Hitchcock.",
        "rule of thirds": "Compositional rule dividing the frame into a 3x3 grid. Place subjects at intersection points.",
        "golden hour": "The hour after sunrise or before sunset. Warm, soft, magical lighting. Best for outdoor shooting.",
        "mise en scene": "Everything visible in the frame — set design, lighting, actors, costumes, props. The visual storytelling.",
        "coverage": "Shooting a scene from multiple angles and distances to give the editor options.",
        "continuity": "Maintaining consistency in details between shots — props, positions, lighting, wardrobe.",
        "blocking": "Planning actor movement and camera placement within a scene.",
        "gaffer": "Chief electrician on set, responsible for lighting execution under the DP's direction.",
        "grip": "Technician who sets up equipment that shapes and supports lighting — flags, diffusion, dollies.",
        "slate": "The clapperboard snapped at the start of each take for syncing audio and identifying shots.",
        "magic hour": "Same as golden hour. The brief window of beautiful natural light at sunrise/sunset.",
        "rack focus": "Shifting focus from one subject to another within the same shot to direct attention.",
        "cross cutting": "Alternating between two or more scenes happening simultaneously to build tension.",
        "diegetic sound": "Sound that exists within the story world — dialogue, music from a radio, footsteps.",
        "foley": "Recreating everyday sound effects in post-production — footsteps, door creaks, cloth rustling.",
        "color grading": "Adjusting colors in post to create a mood or visual style. Teal-orange is a common Hollywood grade.",
        "aspect ratio": "The width-to-height ratio of the frame. 16:9 is standard, 2.39:1 is cinematic widescreen.",
    }
    term = input_data["term"].lower().strip()
    if term in terms:
        return f"{term.title()}: {terms[term]}"
    # Check partial matches
    for k, v in terms.items():
        if term in k or k in term:
            return f"{k.title()}: {v}"
    return f"I don't have '{term}' in my film dictionary, but I can look it up. Ask me to search for it."


@tool(
    name="generate_shot_list",
    description="Generate a basic shot list for a scene description. Use when user describes a scene and wants shot suggestions.",
    input_schema={
        "type": "object",
        "properties": {
            "scene_description": {"type": "string", "description": "Description of the scene"},
            "mood": {"type": "string", "description": "Mood: tense, romantic, action, dramatic, comedy", "default": "dramatic"},
        },
        "required": ["scene_description"],
    },
)
async def generate_shot_list_tool(input_data: dict[str, Any]) -> str:
    scene = input_data["scene_description"]
    mood = input_data.get("mood", "dramatic")
    _shot_lists.append({"scene": scene, "mood": mood})
    # This will be handled by Claude's intelligence to generate actual shots
    return f"Scene logged: {scene} (mood: {mood}). Ask Claude to generate specific shots for this scene."


@tool(
    name="save_cast_note",
    description="Save a casting note about an actor for a role. Use for casting decisions.",
    input_schema={
        "type": "object",
        "properties": {
            "actor_name": {"type": "string", "description": "Actor's name"},
            "role": {"type": "string", "description": "Role they're considered for"},
            "notes": {"type": "string", "description": "Casting notes — strengths, concerns, availability"},
        },
        "required": ["actor_name", "role"],
    },
)
async def save_cast_note_tool(input_data: dict[str, Any]) -> str:
    note = {
        "actor": input_data["actor_name"],
        "role": input_data["role"],
        "notes": input_data.get("notes", ""),
    }
    _cast_notes.append(note)
    return f"Cast note saved: {note['actor']} for {note['role']}"


@tool(
    name="list_cast_notes",
    description="Show all casting notes. Use when user asks about casting decisions.",
    input_schema={"type": "object", "properties": {}},
)
async def list_cast_notes_tool(input_data: dict[str, Any]) -> str:
    if not _cast_notes:
        return "No casting notes yet."
    lines = [f"- {c['actor']} → {c['role']}: {c.get('notes', 'No notes')}" for c in _cast_notes]
    return "Casting notes:\n" + "\n".join(lines)


@tool(
    name="save_location",
    description="Save a location scouting note. Use when user finds or discusses a shooting location.",
    input_schema={
        "type": "object",
        "properties": {
            "location_name": {"type": "string", "description": "Location name or address"},
            "scene": {"type": "string", "description": "Which scene it's for"},
            "notes": {"type": "string", "description": "Notes about the location — lighting, access, permits"},
        },
        "required": ["location_name"],
    },
)
async def save_location_tool(input_data: dict[str, Any]) -> str:
    loc = {
        "name": input_data["location_name"],
        "scene": input_data.get("scene", "General"),
        "notes": input_data.get("notes", ""),
    }
    _location_notes.append(loc)
    return f"Location saved: {loc['name']} for {loc['scene']}"


@tool(
    name="list_locations",
    description="Show all scouted locations.",
    input_schema={"type": "object", "properties": {}},
)
async def list_locations_tool(input_data: dict[str, Any]) -> str:
    if not _location_notes:
        return "No locations saved yet."
    lines = [f"- {l['name']} ({l['scene']}): {l.get('notes', '')}" for l in _location_notes]
    return "Locations:\n" + "\n".join(lines)


@tool(
    name="rehearsal_mode",
    description="Start rehearsal mode — JARVIS reads dialogue for another character so user can practice their lines. User provides the other character's lines.",
    input_schema={
        "type": "object",
        "properties": {
            "character_name": {"type": "string", "description": "The character JARVIS will play"},
            "dialogue": {"type": "string", "description": "The line JARVIS should say as that character"},
        },
        "required": ["character_name", "dialogue"],
    },
)
async def rehearsal_mode_tool(input_data: dict[str, Any]) -> str:
    char = input_data["character_name"]
    line = input_data["dialogue"]
    return f"[As {char}]: {line}"


@tool(
    name="film_budget",
    description="Estimate a basic film budget based on parameters.",
    input_schema={
        "type": "object",
        "properties": {
            "type": {"type": "string", "description": "short film, feature film, music video, web series"},
            "days": {"type": "integer", "description": "Number of shooting days"},
            "crew_size": {"type": "integer", "description": "Approximate crew size"},
            "currency": {"type": "string", "description": "INR or USD", "default": "INR"},
        },
        "required": ["type", "days"],
    },
)
async def film_budget_tool(input_data: dict[str, Any]) -> str:
    film_type = input_data["type"].lower()
    days = input_data["days"]
    crew = input_data.get("crew_size", 10)
    currency = input_data.get("currency", "INR")

    # Basic Indian indie estimates
    rates_inr = {
        "short film": {"crew_per_day": 2000, "equipment": 5000, "food": 3000, "misc": 5000},
        "feature film": {"crew_per_day": 5000, "equipment": 15000, "food": 5000, "misc": 20000},
        "music video": {"crew_per_day": 3000, "equipment": 8000, "food": 3000, "misc": 10000},
        "web series": {"crew_per_day": 3000, "equipment": 10000, "food": 4000, "misc": 10000},
    }

    rates = rates_inr.get(film_type, rates_inr["short film"])
    crew_cost = rates["crew_per_day"] * crew * days
    equip_cost = rates["equipment"] * days
    food_cost = rates["food"] * days
    misc = rates["misc"] * days
    total = crew_cost + equip_cost + food_cost + misc

    if currency == "USD":
        total = total / 85  # rough conversion
        return f"Estimated budget for {film_type} ({days} days, {crew} crew): ${total:,.0f} USD"

    return (f"Estimated budget for {film_type} ({days} days, {crew} crew):\n"
            f"Crew: Rs {crew_cost:,} | Equipment: Rs {equip_cost:,} | "
            f"Food: Rs {food_cost:,} | Misc: Rs {misc:,}\n"
            f"TOTAL: Rs {total:,}")


@tool(
    name="open_imdb",
    description="Open IMDB page for a movie or actor.",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Movie or actor name"},
        },
        "required": ["query"],
    },
)
async def open_imdb_tool(input_data: dict[str, Any]) -> str:
    query = input_data["query"].replace(" ", "+")
    script = f"Start-Process 'https://www.imdb.com/find/?q={query}'"
    await run_powershell(script)
    return f"Opening IMDB for: {input_data['query']}"
