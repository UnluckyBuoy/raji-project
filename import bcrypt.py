import bcrypt

password = b"admin123"  # change this
hashed = bcrypt.hashpw(password, bcrypt.gensalt())
print(hashed)
