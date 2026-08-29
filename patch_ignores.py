import os

git_path = "/Users/ankushgautam/Documents/Code_Space/My_Projects/async_tool_bot/jomoai2/BackEnd/.gitignore"
docker_path = "/Users/ankushgautam/Documents/Code_Space/My_Projects/async_tool_bot/jomoai2/BackEnd/.dockerignore"

python_ignores = """
# Python / Environment
__pycache__/
*.py[cod]
*$py.class
venv/
.venv/
env/
.pytest_cache/

# OS Files
.DS_Store
"""

# Update .gitignore
with open(git_path, "a") as f:
    f.write("\n" + python_ignores)

# Update .dockerignore
docker_additions = python_ignores + """
# Docker / Git
.git/
Dockerfile
docker-compose.yml
"""
with open(docker_path, "a") as f:
    f.write("\n" + docker_additions)

print("Updated both files successfully.")
