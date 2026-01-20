
import sys
import os

# Add the project root to the python path
sys.path.append(os.getcwd())

from app.utils.auth import generate_token_for_user

def main():
    # Disable logging
    from loguru import logger
    logger.remove()
    
    email = "test-user@example.com"
    token = generate_token_for_user(email)
    print(token)
    with open("token_output.txt", "w") as f:
        f.write(token)

if __name__ == "__main__":
    main()
