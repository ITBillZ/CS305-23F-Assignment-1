from __future__ import annotations

from argparse import ArgumentParser
# from email.mime.text import MIMEText
from queue import Queue
import socket
from socketserver import ThreadingTCPServer, BaseRequestHandler
from threading import Thread

import tomli

import threading, sys, signal, time

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
    def __init__(self, request, client_address, server):
        self.username = None
        self.login = False
        super().__init__(request, client_address, server)
        

    def handle(self):
        conn = self.request

        try:
            self.ok_send("POP3 server ready")
            authentic_user = False

            while True:
                data = conn.recv(1024).decode("utf-8").strip()
                cmd, *args = data.split()
                print(data)

                if not self.login: # 未登录
                    if not authentic_user: # username未验证
                        if cmd == "USER":
                            # 验证 username
                            authentic_user = self.do_user(args[0])

                        else: # 未提供用户名，发送错误信息
                            self.err_send("Please provide a valid username")

                    else: # username已验证，密码未验证
                        if cmd == "PASS":
                            self.login = self.do_pass(args[0])
                        else:
                            self.err_send("Please provide a valid password")

                else: 
                    if cmd == "STAT":
                        self.do_stat()


        except Exception as e:
            print("An error occurred:", str(e))
            self.err_send("An error occurred")
        finally:
            conn.close()

    def do_stat(self):
        mailbox = MAILBOXES[self.username]
        msg = "{} {}".format(len(mailbox), sum(len(mail) for mail in mailbox))
        self.ok_send(msg)

    def do_user(self, username):
        if username in ACCOUNTS.keys():
            self.ok_send("User accepted")
            self.username = username # 更新用户名
            return True
        else:
            self.err_send("Invalid username")
            self.username = None
            return False

    def do_pass(self, password):

        if password == ACCOUNTS[self.username]:
            self.ok_send("Password accepted")
            return True
        else:
            self.err_send("Invalid password")
            return False

    def ok_send(self, msg):
        self.request.send(f"+OK {msg}\r\n".encode("utf-8"))
    def err_send(self, msg):
        self.request.send(f"-ERR {msg}\r\n".encode("utf-8"))

class SMTPServer(BaseRequestHandler):
    # def handle(self):
    #     conn = self.request
    #     try:
    #         while True:
    #             data = conn.recv(1024).decode("utf-8").strip()
    #             print(data)
    #             self.ok_send("get")

    #     except Exception as e:
    #         print("An error occurred:", str(e))
    #         self.err_send("An error occurred")
    #     # finally:
    #     #     conn.close()

    def handle(self):
        conn = self.request

        try:
            # smtp连接必须发一个220
            
            # self.ok_send("220")
            self.request.send(bytes(220))


            data = conn.recv(1024).decode("utf-8").strip()
            print(f"abcabc + '{data}'")

            # self.ok_send("Please provide a valid username")


        except Exception as e:
            print("An error occurred:", str(e))
            self.err_send("An error occurred")
        finally:
            conn.close()


    def ok_send(self, msg):
        self.request.send(f"+OK {msg}\r\n".encode("utf-8"))
    def err_send(self, msg):
        self.request.send(f"-ERR {msg}\r\n".encode("utf-8"))

        
if __name__ == '__main__':
    try:
        if student_id() % 10000 == 0:
            raise ValueError('Invalid student ID')

        smtp_server = ThreadingTCPServer(('', SMTP_PORT), SMTPServer)
        pop_server = ThreadingTCPServer(('', POP_PORT), POP3Server)
        smtp_thread = threading.Thread(target=smtp_server.serve_forever)
        smtp_thread.setDaemon(True)
        smtp_thread.start()

        pop_thread = threading.Thread(target=pop_server.serve_forever)
        pop_thread.setDaemon(True)
        pop_thread.start()

        while True:  # Keep the main thread alive to be able to catch the KeyboardInterrupt
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down servers...")
        smtp_server.shutdown()
        pop_server.shutdown()
        smtp_server.server_close()
        pop_server.server_close()
        print("Servers stopped. Exiting.")

