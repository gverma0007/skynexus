"""Print an Argon2 hash from a password prompt, never a plaintext credential."""
import getpass
from argon2 import PasswordHasher
if __name__=='__main__':
    password=getpass.getpass('Demo password (12+ characters): ')
    if len(password)<12:raise SystemExit('Use at least 12 characters')
    print("DEMO_PASSWORD_HASH='"+PasswordHasher().hash(password)+"'")
