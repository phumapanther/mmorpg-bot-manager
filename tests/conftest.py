import os, sys

# bot/utils.py (and bot/main.py) use the pre-refactor absolute import
# `import models.player_model as player_model`, which only resolves when the
# `bot/` directory itself is on sys.path (as it is when main.py is run
# directly as a script, or via the sys.path.append trick already used in
# bot/controller/*.py). Mirror that here so `from bot import utils` works
# under pytest too. This old import gets fixed project-wide in Task 6 --
# do not "clean this up" by editing bot/utils.py's imports in the meantime.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bot"))
