import os
import sys
import datetime

class Logger:
    @staticmethod
    def setup():
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Use date only for filename
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(log_dir, f"{date_str}.log")
        
        # Capture stdout and stderr
        sys.stdout = Tee(sys.stdout, log_file)
        sys.stderr = Tee(sys.stderr, log_file)
        
        print(f"日志已初始化: {log_file}")

class Tee:
    def __init__(self, original_stream, log_file):
        self.original_stream = original_stream
        self.log_file = open(log_file, 'a', encoding='utf-8')
        self.new_line = True

    def write(self, message):
        try:
            self.original_stream.write(message)
            
            # Add timestamp to file log
            if message:
                if self.new_line:
                    timestamp = datetime.datetime.now().strftime("[%H:%M:%S] ")
                    self.log_file.write(timestamp)
                    self.new_line = False
                
                self.log_file.write(message)
                
                if message.endswith('\n'):
                    self.new_line = True
                    
            self.log_file.flush()
        except Exception:
            pass

    def flush(self):
        try:
            self.original_stream.flush()
            self.log_file.flush()
        except Exception:
            pass
