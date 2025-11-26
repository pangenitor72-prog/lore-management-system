# ai_service.py

import os
import google.generativeai as genai

gemini_model = None

def generate_content(prompt_text, system_prompt="You are a helpful assistant."):
    """
    A single function to call the AI, using the backend
    specified in the AI_BACKEND environment variable.
    """
    AI_BACKEND = os.environ.get("AI_BACKEND", "local")

    if AI_BACKEND == "gemini":
        global gemini_model
        if gemini_model is None:
            GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")
            if not GEMINI_API_KEY:
                raise ValueError("AI_BACKEND is 'gemini' but GOOGLE_API_KEY is not set or valid in .env")
            
            genai.configure(api_key=GEMINI_API_KEY)
            gemini_model = genai.GenerativeModel('models/gemini-pro-latest')
            print("AI Service: Gemini 1.5 Flash configured successfully.")

        print("--- [Calling Gemini API] ---")
        full_prompt = f"{system_prompt}\n\nUser: {prompt_text}"
        response = gemini_model.generate_content(full_prompt)
        return response.text

    elif AI_BACKEND == "local":
        import ollama
        print("--- [Calling Local Model] ---")
        try:
            response = ollama.chat(
                model='llama3:8b', # Or your preferred local model
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': prompt_text}
                ],
                stream=False
            )
            return response['message']['content']
        except Exception as e:
            print(f"Ollama local model error: {e}")
            return "Error: Local model is not running. (Did you run 'ollama pull' and is Ollama running?)"

    else:
        raise ValueError(f"Unknown AI_BACKEND: {AI_BACKEND}")
