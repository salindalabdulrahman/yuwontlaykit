import sys
import datetime
from colorama import Fore, Style

class AIEngine:
    def __init__(self):
        self.context = {
            "user_name": "Boss",
            "session_start": datetime.datetime.now().strftime("%H:%M:%S")
        }
        # INSTRUCTION: Initialize a list or dictionary to store memories during the session
        self.memories = []

    def chat(self, user_input):
        text = user_input.lower().strip()
        
        # 1. Identity & Persona Rules
        if any(w in text for who in ["who are you", "your name", "what are you"] for w in [who]):
            reply = "I'm Yuwontlaykit, Nikko's good friend and right-hand assistant!"

        # 1.5. Nikko's Detailed Bio Profile
        elif any(phrase in text for phrase in [
            "what do you know about nikko", 
            "who is nikko", 
            "tell me about nikko",
            "what do you know about him",
            "tell me about him",
            "who is he"
        ]):
            reply = (
                "Here is everything I know about my best friend, Nikko:\n\n"
                "  • Full Name: Abdulrahman Bedis Kumam Salindal\n"
                "  • Birthday: January 2, 2000\n"
                "  • Height: 5'7\"\n"
                "  • Favorite Food: Spaghetti\n"
                "  • Education: Bachelor of Science in Information Communication Technology, Graduated from MSU Maguindanao - Dalican\n"
                "  • Current Role: Computer Operator I at BARMM OCM-ICO (Office of the Chief Minister - Information and Communication Office)\n\n"
                "That's my main guy right there!"
            )

        # 2. Dynamic Time & System Check
        elif "time" in text:
            current_time = datetime.datetime.now().strftime("%I:%M %p")
            reply = f"The current system time is {current_time}."
            
        elif "date" in text:
            current_date = datetime.datetime.now().strftime("%A, %B %d, %Y")
            reply = f"Today's date is {current_date}."

        # --- MEMORY FEATURE CODE BLOCK ---
        # Instruction: Check if the user wants Yuwontlaykit to remember something
        elif text.startswith("remember "):
            # Extract the text after "remember "
            memory_item = user_input[9:].strip()
            if memory_item:
                self.memories.append(memory_item)
                reply = f"Got it! I've saved this to my memory: \"{memory_item}\""
            else:
                reply = "What would you like me to remember? Try typing 'remember [something]'."

        # Instruction: Check if the user wants to view their saved memories
        elif any(phrase in text for phrase in ["show memories", "what do you remember", "my memories"]):
            if self.memories:
                memory_list = "\n".join([f"  • {m}" for m in self.memories])
                reply = f"Here are the things you asked me to remember:\n\n{memory_list}"
            else:
                reply = "My memory is currently empty. Tell me to 'remember [something]' to save a note!"
        # ---------------------------------

        # 3. Custom Capabilities / Help Menu
        elif any(w in text for w in ["help", "what can you do", "commands"]):
            reply = (
                "Here is what I can do natively:\n"
                "  - Ask me 'what time is it?' or 'what is today's date?'\n"
                "  - Tell me 'calc [math]' (e.g., calc 45 * 12)\n"
                "  - Say 'remember [something]' to save a temporary note.\n"
                "  - Say 'show memories' to view saved notes.\n"
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