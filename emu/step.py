"""Interactive helper: py -3 step.py start <rom> | py -3 step.py <rom> <shotname> <cmd>... (runs cmds, then screenshots)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'suite'))
from lib import Game
if sys.argv[1] == 'start':
    Game(sys.argv[2]).start(fresh_save=True)
else:
    g = Game(sys.argv[1])
    g.run(*sys.argv[3:])
    print(g.shot(sys.argv[2]))
