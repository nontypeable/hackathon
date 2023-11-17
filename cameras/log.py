import time
from config import Config

class Log:
    @staticmethod
    def add(info):
        print(f"*** {info} ***\n\n")
        try:
            with open(Config.log_file, 'a') as f:
                f.write(f'{time.strftime("%Y-%m-%d %H:%M:%S")} {info}\n')
        except Exception as e:
            print(f"log error: {e}\n\n")
            pass
