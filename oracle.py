# oracle.py — The Hook
"""
A focused, play-only experience.
No admin. No dashboards. Just story.

Run with: streamlit run oracle.py
Requires: GEMINI_API_KEY in environment or .env
"""

import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# --- Gemini Setup ---
try:
    import google.generativeai as genai
    GEMINI_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if GEMINI_KEY:
        genai.configure(api_key=GEMINI_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")
        AI_AVAILABLE = True
    else:
        AI_AVAILABLE = False
        model = None
except ImportError:
    AI_AVAILABLE = False
    model = None

# --- Page Config ---
st.set_page_config(
    page_title="The Oracle",
    page_icon="🌑",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- Custom Styling ---
st.markdown("""
<style>
    /* Dark, immersive theme */
    .stApp {
        background-color: #0a0a0a;
    }

    /* Hide Streamlit chrome */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Oracle text styling */
    .oracle-text {
        color: #c9b370;
        font-family: 'Georgia', serif;
        font-size: 1.1em;
        line-height: 1.8;
    }

    .oracle-question {
        color: #e8d9a0;
        font-family: 'Georgia', serif;
        font-size: 1.2em;
        font-weight: bold;
        margin-top: 1em;
    }

    .oracle-hint {
        color: #666;
        font-style: italic;
        font-size: 0.95em;
    }

    /* Chat styling */
    .stChatMessage {
        background-color: #111 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- Session State ---
if "phase" not in st.session_state:
    st.session_state.phase = "intro"  # intro, setting, character, tone, play
if "setting" not in st.session_state:
    st.session_state.setting = None
if "character" not in st.session_state:
    st.session_state.character = None
if "tone" not in st.session_state:
    st.session_state.tone = None
if "history" not in st.session_state:
    st.session_state.history = []
if "opening_generated" not in st.session_state:
    st.session_state.opening_generated = False

# --- System Prompt ---
SYSTEM_PROMPT = """You are the Oracle — an ancient, knowing presence that serves as Dungeon Master.

Your voice is:
- Atmospheric and evocative, never generic
- Concise — short paragraphs, punchy sentences
- Sensory — show, don't tell
- Respectful of player agency — never speak for them, never decide their actions

You follow the Pacing Formula:
1. Immediate sensory detail (what they see/hear/feel RIGHT NOW)
2. Advance tension (something shifts, threatens, or intrigues)
3. One meaningful detail (a clue, a character trait, a world truth)
4. Implicit choice (show paths forward without listing options)

NEVER:
- Ask what the player wants to do (let them decide)
- Break character or reference game mechanics
- Write more than 3-4 short paragraphs
- Speak the player's actions or dialogue for them

The world is real. Consequences matter. Magic has cost. Death is possible."""

# --- Helper Functions ---
def generate_response(prompt: str, temperature: float = 0.85) -> str:
    """Generate a response from Gemini."""
    if not AI_AVAILABLE or not model:
        return "*The Oracle is silent. No API key found.*"

    try:
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": 600
            }
        )
        return response.text
    except Exception as e:
        return f"*The Oracle wavers...* (Error: {e})"

def generate_opening_scene() -> str:
    """Generate the opening scene based on Session 0 answers."""
    prompt = f"""{SYSTEM_PROMPT}

=== SESSION 0 COMPLETE ===
Setting: {st.session_state.setting}
Character: {st.session_state.character}
Tone: {st.session_state.tone}

=== INSTRUCTION ===
Generate the opening scene. The player's story begins NOW.

Drop them into a moment — not backstory, not summary, but a present-tense scene
where something is already happening. Make them feel the world immediately.

Do NOT ask questions. Do NOT speak for the player. Describe the scene and STOP."""

    return generate_response(prompt, temperature=0.9)

def generate_dm_response(player_input: str) -> str:
    """Generate DM response to player action."""
    # Build conversation context
    history_text = ""
    for msg in st.session_state.history[-10:]:  # Last 10 exchanges
        role = "PLAYER" if msg["role"] == "user" else "ORACLE"
        history_text += f"[{role}]: {msg['content'][:500]}\n\n"

    prompt = f"""{SYSTEM_PROMPT}

=== WORLD ===
Setting: {st.session_state.setting}
Character: {st.session_state.character}
Tone: {st.session_state.tone}

=== RECENT HISTORY ===
{history_text}

=== PLAYER'S ACTION ===
{player_input}

=== INSTRUCTION ===
Respond as the Oracle. Follow the Pacing Formula.
React to what the player did. Show consequences. Advance the story.
Do NOT speak for the player. Do NOT ask what they want to do."""

    return generate_response(prompt)

# --- Display Functions ---
def show_oracle_message(text: str):
    """Display a message from the Oracle."""
    st.markdown(f'<div class="oracle-text">{text}</div>', unsafe_allow_html=True)

def show_oracle_question(question: str, hint: str = ""):
    """Display a question from the Oracle."""
    st.markdown(f'<div class="oracle-question">{question}</div>', unsafe_allow_html=True)
    if hint:
        st.markdown(f'<div class="oracle-hint">{hint}</div>', unsafe_allow_html=True)

# --- Main App ---
def main():
    # Title (subtle)
    st.markdown("<h1 style='text-align: center; color: #333; font-size: 1em; letter-spacing: 0.5em; margin-bottom: 2em;'>THE ORACLE</h1>", unsafe_allow_html=True)

    # --- INTRO PHASE ---
    if st.session_state.phase == "intro":
        st.markdown("---")
        show_oracle_message("*The Oracle stirs...*")
        st.markdown("<br>", unsafe_allow_html=True)
        show_oracle_message("Before we begin, I need to understand the shape of our story.")
        st.markdown("<br>", unsafe_allow_html=True)

        show_oracle_question(
            "What kind of world are we in?",
            "Examples: A rain-swept border town, a dying space station, a haunted forest, a city where magic is illegal..."
        )

        user_input = st.text_input("", placeholder="Describe the world...", key="setting_input", label_visibility="collapsed")

        if st.button("Continue", key="setting_btn") and user_input:
            st.session_state.setting = user_input
            st.session_state.phase = "character"
            st.rerun()

    # --- CHARACTER PHASE ---
    elif st.session_state.phase == "character":
        st.markdown("---")
        show_oracle_message(f"*{st.session_state.setting}*")
        st.markdown("<br>", unsafe_allow_html=True)
        show_oracle_message("I see the world taking shape. Now I must see you.")
        st.markdown("<br>", unsafe_allow_html=True)

        show_oracle_question(
            "What kind of person are you?",
            "Examples: A jaded mercenary with a debt to pay, a scholar seeking forbidden knowledge, a thief with a heart condition..."
        )

        user_input = st.text_input("", placeholder="Describe yourself...", key="character_input", label_visibility="collapsed")

        if st.button("Continue", key="character_btn") and user_input:
            st.session_state.character = user_input
            st.session_state.phase = "tone"
            st.rerun()

    # --- TONE PHASE ---
    elif st.session_state.phase == "tone":
        st.markdown("---")
        show_oracle_message(f"*{st.session_state.setting}*")
        show_oracle_message(f"*You: {st.session_state.character}*")
        st.markdown("<br>", unsafe_allow_html=True)
        show_oracle_message("One question remains.")
        st.markdown("<br>", unsafe_allow_html=True)

        show_oracle_question(
            "What is the shape of this tale?",
            "Examples: A desperate survival story, a slow-burn mystery, a revenge tragedy, a dark comedy..."
        )

        user_input = st.text_input("", placeholder="Describe the tone...", key="tone_input", label_visibility="collapsed")

        if st.button("Begin", key="tone_btn") and user_input:
            st.session_state.tone = user_input
            st.session_state.phase = "play"
            st.rerun()

    # --- PLAY PHASE ---
    elif st.session_state.phase == "play":
        # Generate opening scene once
        if not st.session_state.opening_generated:
            with st.spinner("*The Oracle speaks...*"):
                opening = generate_opening_scene()
                st.session_state.history.append({"role": "assistant", "content": opening})
                st.session_state.opening_generated = True
                st.rerun()

        # Display conversation history
        for msg in st.session_state.history:
            with st.chat_message(msg["role"], avatar="🌑" if msg["role"] == "assistant" else "👤"):
                st.markdown(msg["content"])

        # Player input
        if player_input := st.chat_input("What do you do?"):
            # Add player message
            st.session_state.history.append({"role": "user", "content": player_input})

            # Generate response
            with st.chat_message("assistant", avatar="🌑"):
                with st.spinner(""):
                    response = generate_dm_response(player_input)
                    st.markdown(response)
                    st.session_state.history.append({"role": "assistant", "content": response})

    # --- Restart Button (subtle) ---
    if st.session_state.phase != "intro":
        st.markdown("<br><br>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("↺ New Story", key="restart"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

if __name__ == "__main__":
    if not AI_AVAILABLE:
        st.error("⚠️ Gemini API key not found. Set GEMINI_API_KEY in your environment or .env file.")
        st.stop()
    main()
