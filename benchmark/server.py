from __future__ import annotations

from argparse import ArgumentParser
# from email.mime.text import MIMEText
from queue import Queue
import socket
from socketserver import ThreadingTCPServer, BaseRequestHandler
from threading import Thread

import tomli

import threading, re, time, base64
from traceback import print_exc

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
        self.mailbox = None
        self.predel = []
        super().__init__(request, client_address, server)
        

    def handle(self):
        conn = self.request

        self.ok_send("POP3 server ready")
        authentic_user = False

        while True:
            try:
                self.recv = conn.recv(1024)
                data = self.recv.decode("utf-8").strip()
                cmd = data[:4].upper()
                arg = data[5:] if len(data) > 4 else None

                if not self.login: # 未登录
                    if not authentic_user: # username未验证
                        if cmd == "USER":
                            # 验证 username
                            authentic_user = self.do_user(arg)

                        else: # 未提供用户名，发送错误信息
                            self.err_send("Please provide a valid username")

                    else: # username已验证，密码未验证
                        if cmd == "PASS":
                            self.login = self.do_pass(arg)
                        else:
                            self.err_send("Please provide a valid password")

                else: 
                    if cmd == "STAT":
                        self.do_stat()
                    elif cmd == "LIST":
                        self.do_list(arg)
                    elif cmd == "RETR":
                        self.do_retr(arg)
                    elif cmd == "DELE":
                        self.do_dele(arg)
                    elif cmd == "RSET":
                        self.do_rset()
                    elif cmd == "NOOP":
                        self.ok_send()
                    elif cmd == "QUIT":
                        self.do_quit()
                        break

            except Exception as e:
                print("An error occurred:", str(e))
                self.err_send("An error occurred")


    def do_dele(self, arg):
        self.predel.append(int(arg) - 1)  # 预删除，注意index
        self.ok_send()
    
    def do_rset(self):
        self.predel.clear()
        self.ok_send()

    def do_quit(self):
        # 清除邮件
        # 需要这样删除，才能直接影响MAILBOXS
        for idx in sorted(self.predel, reverse=True):
            del self.mailbox[idx]
        # 清空self.predel
        self.predel.clear()
        self.ok_send("Bye")
        self.request.close()
    
    def do_list(self, which):
        if which:
            self.ok_send(f"{which} {len(self.mailbox[int(which) - 1])}")
        else:
            msg = f"{len(self.mailbox)} messages\r\n" + \
            "\r\n".join([f"{i + 1} {len(mail)}" for i, mail in enumerate(self.mailbox) if i not in self.predel]) + \
            "\r\n."
            self.ok_send(msg)
    
    def do_retr(self, which):
        mail = self.mailbox[int(which) - 1]
        msg = f"{len(mail)} bytes\r\n" + mail
        self.ok_send(msg)

    def do_stat(self):
        msg = "{} {}".format(len(self.mailbox), sum(len(mail) for i, mail in enumerate(self.mailbox) if i not in self.predel))
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
            self.mailbox = MAILBOXES[self.username]
            return True
        else:
            self.err_send("Invalid password")
            return False

    def do_help(self):
        # 命令列表及其描述
        commands_description = {
            "USER": "Provide a username for authentication.",
            "PASS": "Provide a password to complete the authentication process.",
            "STAT": "Retrieve mailbox status in the form of number of messages and total mailbox size.",
            "LIST": "List messages in the mailbox. If an argument is provided, list details of that specific message.",
            "RETR": "Retrieve a specific message. The message number should be provided as an argument.",
            "DELE": "Delete a specific message. The message number should be provided as an argument.",
            "RSET": "Reset the session. Any messages that were marked for deletion are unmarked.",
            "NOOP": "No operation. The server will simply reply with a positive response.",
            "QUIT": "Quit the session and close the connection."
        }

        # 发送命令列表及其描述
        for cmd, desc in commands_description.items():
            response = f"{cmd}: {desc}"
            self.ok_send(response)


    def ok_send(self, msg=None):
        # !!!!!!!!!!!一定要加strip() strip() strip() strip()
        if msg:
            self.request.send(f"+OK {str(msg).strip()}\r\n".encode("utf-8"))
        else:
            self.request.send(f"+OK\r\n".encode("utf-8"))
    
    def err_send(self, msg):
        self.request.send(f"-ERR {str(msg)}\r\n".encode("utf-8"))


class SMTPServer(BaseRequestHandler):
    def __init__(self, request, client_address, server):
        self.recv = None
        self.socket = None
        self.forwarding = False
        self.forwarded = False
        super().__init__(request, client_address, server)

    def handle(self):
        continue_loop = True
        conn = self.request
        self.send(220, "SMTP server ready")

        while continue_loop:
            try:

                self.recv = conn.recv(1024)
                data = self.recv.decode("utf-8").strip()
                cmd = data[:4].upper()
                arg = data[5:] if len(data) > 4 else None

                if cmd == "HELO" or cmd == "EHLO":
                    self.send(250, "HELLO")
                elif cmd == "FRWD":  # 转发状态
                    self.send(250, "Forward ready")
                    self.forwarded = True
                elif cmd == "MAIL":
                    mail_from = re.search(r'<([^>]+)>', arg).group(1)
                    mail_from_domail = mail_from.split("@")[-1]

                    if self.forwarded or mail_from in ACCOUNTS:
                        # 被转发状态不检验，或者在ACCOUNTS里
                        self.send(250, "OK")
                    else:
                        self.send(421, f"Sender refused: {mail_from}")

                elif cmd == "RCPT":
                    rcpt_to = re.search(r'<([^>]+)>', arg).group(1)
                    rcpt_domain = rcpt_to.split("@")[-1]

                    if self.forwarded: # 这是被转发方server
                        # 校验rcpt_to
                        if rcpt_to not in ACCOUNTS:
                            self.send(421, f"Recipient refused")
                        else:
                            self.send(250, "OK")
                    
                    else: # 发件服务器
                        if mail_from_domail == rcpt_domain: # 非转发
                            if rcpt_to not in ACCOUNTS:
                                self.send(421, f"Recipient refused")
                            else:
                                self.send(250, "OK")
                        else: # 转发
                            self.forwarding = 1

                            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            rcpt_domain = rcpt_to.split("@")[-1]
                            rcpt_smtp_server = fdns_query(rcpt_domain, 'MX')
                            rcpt_smtp_port = int(fdns_query(rcpt_smtp_server, 'P'))
                            self.socket.connect(("", rcpt_smtp_port))
                            self.socket.recv(1024)

                            self.s_send(f"frwd {socket.gethostname()}")
                            self.s_send(f"mail FROM:<{mail_from}>")
                            code, _ = self.s_send(f"rcpt TO:<{rcpt_to}>")

                            if code == 421:
                                self.send(421, f"Recipient refused")
                            else:
                                self.send(250, "OK")

                elif cmd == "DATA":
                    self.send(354, "Start mail input: end with <CRLF>.<CRLF>")
                    self.recv = conn.recv(1024)
                    data = self.recv.decode("utf-8")

                    if self.forwarded or not self.forwarding:
                        # 被转发方 或 非转发状态 直接放入邮箱即可
                        MAILBOXES[rcpt_to].append(data)
                        self.send(250, "OK")
                    
                    elif self.forwarding:
                        self.s_send("data")
                        self.s_send(data)
                        self.s_send("quit")

                        self.send(250, "OK")

                elif cmd == "QUIT":
                    self.send(221, "Bye")
                    conn.close()
                    break

            except Exception as e:
                # 其他错误的处理
                print("An error occurred")
                print_exc()
                self.send(500, "Internal server error")

        if self.socket:
            self.socket.close()
    

    def send(self, code, msg):
        # !!!!!!!!!!!!!!!!!!!!!!!一定要加CRLF CRLF CRLF CRLF CRLF CRLF 
        self.request.send(f"{code} {str(msg).strip()}\r\n".encode("utf-8"))
        print(f">>> Received: {self.recv}")
        print(f">>> Response: {code} {msg}")
        print()

    def s_send(self, msg):
        self.socket.send(f"{str(msg).strip()}\r\n".encode())
        data = self.socket.recv(1024).decode()
        return int(data[:3]), data[4:]


if __name__ == '__main__':
    try:
        if student_id() % 10000 == 0:
            raise ValueError('Invalid student ID')

        smtp_server = ThreadingTCPServer(('', SMTP_PORT), SMTPServer)
        pop_server = ThreadingTCPServer(('', POP_PORT), POP3Server)
        smtp_thread = threading.Thread(target=smtp_server.serve_forever)
        smtp_thread.daemon = True
        smtp_thread.start()

        pop_thread = threading.Thread(target=pop_server.serve_forever)
        pop_thread.daemon = True
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

