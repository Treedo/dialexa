"""Точка входу PyInstaller-бандла Dialexa.app.

freeze_support() потрібен, бо деякі бібліотеки (зокрема стек розпізнавання)
створюють multiprocessing-диття: без нього заморожений бінарник перезапускає
нашу main() з argv bootstrap-коду і argparse падає з «unrecognized arguments».
"""
import multiprocessing

from lecture_translator.app import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
