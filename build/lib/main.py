import sys
import datetime
from colorama import Fore, Style
from core.ai_engine import AIEngine

def main():
    ai = AIEngine()
    print(f"{Fore.GREEN}Yuwontlaykit is online and ready, Boss! (Type 'exit' to quit){Style.RESET_ALL}\n")
    
    while True:
        try:
            user_input = input(f"{Fore.YELLOW}Boss > {Style.RESET_ALL}")
            if user_input.lower().strip() in ["exit", "quit"]:
                print(f"{Fore.CYAN}Yuwontlaykit >{Style.RESET_ALL} Goodbye, Boss!")
                break
            if user_input.strip() == "":
                continue
            
            ai.chat(user_input)
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break

if __name__ == "__main__":
    main()
