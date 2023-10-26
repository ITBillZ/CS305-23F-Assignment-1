from __future__ import annotations

from argparse import ArgumentParser
# from email.mime.text import MIMEText
from queue import Queue
import socket
from socketserver import ThreadingTCPServer, BaseRequestHandler
from threading import Thread

import tomli

import threading, sys, signal

def student_id() -> int:
    return 12110817  # TODO: replace with your SID


parser = ArgumentParser()
parser.add_argument('--name', '-n', type=str, required=True)
parser.add_argument('--smtp', '-s', type=int)
parser.add_argument('--pop', '-p', type=int)

args = parser.parse_args()

with open('data/config.toml', 'rb') as f:
    _config = tomli.load(f)
    SMTP_PORT = args.smtp or int(_config['server'][args.name]['smtp'])
    POP_PORT = args.pop or int(_config['server'][args.name]['pop'])
    ACCOUNTS = _config['accounts'][args.name]
    MAILBOXES = {account: [] for account in ACCOUNTS.keys()}

with open('data/fdns.toml', 'rb') as f:
    FDNS = tomli.load(f)

ThreadingTCPServer.allow_reuse_address = True


def fdns_query(domain: str, type_: str) -> str | None:
    domain = domain.rstrip('.') + '.'
    return FDNS[type_][domain]


class POP3Server(BaseRequestHandler):
    def handle(self):
        conn = self.request

        try:
            conn.send(b"+OK POP3 server ready\r\n")
            authenticated = False
            username = None

            while True:
                data = conn.recv(1024).decode("utf-8").strip()
                if not data:
                    break

                if not authenticated:
                    if data.upper().startswith("USER "):
                        # 提取用户名并进行身份验证
                        username = data[5:].strip()
                        if username in ACCOUNTS.keys():
                            conn.send(b"+OK User accepted\r\n")
                            authenticated = True
                        else:
                            conn.send(b"-ERR Invalid username\r\n")
                    else:
                        conn.send(b"-ERR Please provide a valid username\r\n")
                else:
                    if data.upper().startswith("PASS "):
                        # 提取密码并进行验证
                        password = data[5:].strip()
                        if password == ACCOUNTS[username]:
                            conn.send(b"+OK Password accepted\r\n")
                            # 在此之后，可以处理其他邮件操作，如检索邮件等
                        else:
                            conn.send(b"-ERR Invalid password\r\n")
                        

        except Exception as e:
            print("An error occurred:", str(e))
            conn.send(b"-ERR An error occurred\r\n")
        finally:
            conn.close()



class SMTPServer(BaseRequestHandler):
    def handle(self):
        conn = self.request

        print(conn.recv(1024).decode("utf-8").strip())

        
def stop_servers(signum, frame):
    print("Received SIGINT. Stopping servers.")
    smtp_server.shutdown()
    pop_server.shutdown()
    smtp_server.server_close()
    pop_server.server_close()
    smtp_thread.join()
    pop_thread.join()
    print("Servers stopped. Exiting.")
    exit(0)

if __name__ == '__main__':
    signal.signal(signal.SIGINT, stop_servers)
    
    if student_id() % 10000 == 0:
        raise ValueError('Invalid student ID')

    smtp_server = ThreadingTCPServer(('', SMTP_PORT), SMTPServer)
    pop_server = ThreadingTCPServer(('', POP_PORT), POP3Server)
    smtp_thread = threading.Thread(target=smtp_server.serve_forever)
    pop_thread = threading.Thread(target=pop_server.serve_forever)
    
    smtp_thread.start()
    pop_thread.start()

    smtp_thread.join()
    pop_thread.join()

# if __name__ == '__main__':
#     if student_id() % 10000 == 0:
#         raise ValueError('Invalid student ID')
    
#     smtp_server = ThreadingTCPServer(('', SMTP_PORT), SMTPServer)
#     pop_server = ThreadingTCPServer(('', POP_PORT), POP3Server)
#     Thread(target=smtp_server.serve_forever).start()
#     Thread(target=pop_server.serve_forever).start()

