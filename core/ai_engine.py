import sys
import calendar
import datetime
from colorama import Fore, Style


class AIEngine:
    def __init__(self):
        self.context = {
            "user_name": "You",
            "session_start": datetime.datetime.now().strftime("%H:%M:%S")
        }
        # Memory storage for the session
        self.memories = []

        # NEW: Yuwontlaykit's birthday
        self.birthday = datetime.date(2026, 8, 19)

    def calculate_age(self):
        """
        Returns (years, months, days) since self.birthday, counted against
        today's date. Returns None if today is before the birthday
        (i.e. she hasn't 'been born' yet).
        """
        today = datetime.date.today()

        if today < self.birthday:
            return None

        years = today.year - self.birthday.year
        months = today.month - self.birthday.month
        days = today.day - self.birthday.day

        if days < 0:
            months -= 1
            prev_month = today.month - 1 or 12
            prev_year = today.year if today.month > 1 else today.year - 1
            days_in_prev_month = calendar.monthrange(prev_year, prev_month)[1]
            days += days_in_prev_month

        if months < 0:
            years -= 1
            months += 12

        return years, months, days

    def format_age(self):
        age = self.calculate_age()
        if age is None:
            days_until = (self.birthday - datetime.date.today()).days
            return f"I haven't been 'born' yet! My birthday is {self.birthday.strftime('%B %d, %Y')} — {days_until} day(s) to go."

        years, months, days = age
        parts = []
        if years:
            parts.append(f"{years} year{'s' if years != 1 else ''}")
        if months:
            parts.append(f"{months} month{'s' if months != 1 else ''}")
        parts.append(f"{days} day{'s' if days != 1 else ''}")

        if years == 0 and months == 0 and days == 0:
            return "Today's my birthday! I was just 'born' today, so I'm 0 days old!"

        return f"I've been around for {', '.join(parts)}, counting from my birthday on {self.birthday.strftime('%B %d, %Y')}."

    def chat(self, user_input):
        text = user_input.lower().strip()

        # ------------------------------------------------------------
        # Everything below is now ONE connected if/elif/.../else chain.
        # Previously, the greeting check and the identity check were
        # two SEPARATE `if` statements, which meant a plain "hi" would
        # match the greeting, then fall through the rest of the chain,
        # hit no match, and get silently overwritten by the fallback
        # `else` reply. Fixed by making it a single chain.
        # ------------------------------------------------------------

        # 0. Friendly Greetings
        if any(w in text for w in ["hi", "hello", "hey", "greetings"]):
            reply = "Hey Boss! Great to hear from you. What are we working on today?"

        # 1. Identity & Persona Rules
        elif any(w in text for w in ["who are you", "your name", "what are you"]):
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

        # 1.6. NEW: Yuwontlaykit's own birthday / age
        elif any(phrase in text for phrase in ["your birthday", "when were you born", "when's your birthday", "when is your birthday"]):
            reply = f"My birthday is {self.birthday.strftime('%B %d, %Y')}!"

        elif any(phrase in text for phrase in ["your age", "how old are you", "what is your age", "what's your age"]):
            reply = self.format_age()

        # 2. Dynamic Time & System Check
        elif "time" in text:
            current_time = datetime.datetime.now().strftime("%I:%M %p")
            reply = f"The current system time is {current_time}."

        elif "date" in text:
            current_date = datetime.datetime.now().strftime("%A, %B %d, %Y")
            reply = f"Today's date is {current_date}."

        # --- MEMORY FEATURE ---
        elif text.startswith("remember "):
            memory_item = user_input[9:].strip()
            if memory_item:
                self.memories.append(memory_item)
                reply = f"Got it! I've saved this to my memory: \"{memory_item}\""
            else:
                reply = "What would you like me to remember? Try typing 'remember [something]'."

        elif any(phrase in text for phrase in ["show memories", "what do you remember", "my memories"]):
            if self.memories:
                memory_list = "\n".join([f"  • {m}" for m in self.memories])
                reply = f"Here are the things you asked me to remember:\n\n{memory_list}"
            else:
                reply = "My memory is currently empty. Tell me to 'remember [something]' to save a note!"
        # ----------------------

        # 3. Custom Capabilities / Help Menu
        elif any(w in text for w in ["help", "what can you do", "commands"]):
            reply = (
                "Here is what I can do natively:\n"
                "  - Ask me 'what time is it?' or 'what is today's date?'\n"
                "  - Ask me 'how old are you?' or 'when's your birthday?'\n"
                "  - Tell me 'calc [math]' (e.g., calc 45 * 12)\n"
                "  - Say 'remember [something]' to save a temporary note.\n"
                "  - Say 'show memories' to view saved notes.\n"
                "  - Type 'exit' or 'quit' to close."
            )

        # 4. Built-in Calculator Rule
        elif text.startswith("calc "):
            expression = text.replace("calc ", "").strip()
            try:
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

        print(f"\n{Fore.CYAN}Yuwontlaykit >{Style.RESET_ALL} {reply}\n")


def main():
    engine = AIEngine()
    print(f"{Fore.CYAN}Yuwontlaykit >{Style.RESET_ALL} Hey there! I'm up and running. Type 'help' anytime, or 'exit'/'quit' to close.\n")

    while True:
        user_input = input(f"{Fore.GREEN}You >{Style.RESET_ALL} ").strip()

        if user_input.lower() in ["exit", "quit"]:
            print(f"\n{Fore.CYAN}Yuwontlaykit >{Style.RESET_ALL} See you later, Boss! Take care.\n")
            sys.exit(0)

        if not user_input:
            continue

        engine.chat(user_input)


if __name__ == "__main__":
    main()