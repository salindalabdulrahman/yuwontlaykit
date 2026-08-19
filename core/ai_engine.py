import sys
import datetime
from colorama import Fore, Style

class AIEngine:
    def __init__(self):
        self.context = {
            "user_name": "Boss",
            "session_start": datetime.datetime.now().strftime("%H:%M:%S")
        }

    def chat(self, user_input):
        text = user_input.lower().strip()
        
        # 1. Identity & Persona Rules
        if any(w in text for who in ["who are you", "your name", "what are you"] for w in [who]):
            reply = "I am Yuwontlaykit, your custom-coded, independent command-line AI assistant. I run entirely on local logic without external neural networks."

        # 2. Dynamic Time & System Check
        elif "time" in text:
            current_time = datetime.datetime.now().strftime("%I:%M %p")
            reply = f"The current system time is {current_time}."
            
        elif "date" in text:
            current_date = datetime.datetime.now().strftime("%A, %B %d, %Y")
            reply = f"Today's date is {current_date}."

        # 3. Custom Capabilities / Help Menu
        elif any(w in text for w in ["help", "what can you do", "commands"]):
            reply = (
                "Here is what I can do natively:\n"
                "  - Ask me 'what time is it?' or 'what is today's date?'\n"
                "  - Tell me 'calc [math]' (e.g., calc 45 * 12)\n"
                "  - Say 'remember [something]' to save a temporary note.\n"
                "  - Type 'exit' or 'quit' to close."
            )

        # 4. Built-in Calculator Rule
        elif text.startswith("calc "):
            expression = text.replace("calc ", "").strip()
            try:
                # Safe evaluation of basic math expressions
                allowed_chars = set("0123456789+-*/(). ")
                if all(c in allowed_chars for c in expression):
                    result = eval(expression)
                    reply = f"Result: {expression} = {result}"
                else:
                    reply = "I can only calculate safe mathematical expressions using numbers and basic operators (+, -, *, /)."
            except Exception:
                reply = "I couldn't calculate that. Check your expression syntax."

        # 5. Fallback / Default Pattern Matching
        else:
            reply = f"I processed your input via my custom logic engine: '{user_input}'. Try typing 'help' to see my built-in commands!"

        # Print Output cleanly
        print(f"\n{Fore.CYAN}Yuwontlaykit >{Style.RESET_ALL} {reply}\n")