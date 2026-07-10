"""
conftest.py
Muss im PROJEKT-ROOT liegen (gleiche Ebene wie lexware_parser.py, periods.py,
main.py). pytest liest conftest.py automatisch beim Start ein - KEIN Import
notwendig, KEIN manuelles Aufrufen.

Zweck: Fuegt den Projekt-Root explizit zu sys.path hinzu, BEVOR irgendein
Testmodul importiert wird. Das ist robuster als sys.path-Manipulation
innerhalb einzelner Testdateien, weil es unabhaengig davon funktioniert,
ob pytest die Tests als Package (mit tests/__init__.py) oder als lose
Module einliest - beides fuehrt sonst zu unterschiedlichem sys.path-
Verhalten (siehe pytest "import modes").
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
