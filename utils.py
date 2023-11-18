import os

def is_file_exist(path: str) -> bool:
    if os.path.isfile(path):
        return True
    else:
        return False
