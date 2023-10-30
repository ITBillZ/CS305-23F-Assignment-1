from __future__ import annotations

from argparse import ArgumentParser
from email.mime.text import MIMEText
from poplib import POP3
from smtplib import SMTP, SMTPSenderRefused, SMTPRecipientsRefused, SMTPDataError

from imaplib import IMAP4

import tomli, datetime

parser = ArgumentParser()
parser.add_argument('--email', '-e', type=str, required=True)
parser.add_argument('--password', '-p', type=str, required=True)
# ! TEST
# parser.add_argument('--email', '-e', type=str, default="usr2@mail.sustech.edu.cn")
# parser.add_argument('--password', '-p', type=str, default="pass2")
# ! TEST
parser.add_argument('--smtp', '-s', type=str)
parser.add_argument('--pop', '-P', type=str)

args = parser.parse_args()

with open('data/config.toml', 'rb') as f:
    _config = tomli.load(f)
    _domain = args.email.split('@')[-1]
    SMTP_SERVER = args.smtp or _config['agent'][_domain]['smtp']
    POP_SERVER = args.pop or _config['agent'][_domain]['pop']

with open('data/fdns.toml', 'rb') as f:
    FDNS = tomli.load(f)


def fdns_query(domain: str, type_: str) -> str | None:
    domain = domain.rstrip('.') + '.'
    return FDNS[type_][domain]


def smtp():
    SMTP.debuglevel = 1
    conn = SMTP('localhost', int(fdns_query(SMTP_SERVER, 'P')))

    # to = []
    # while True:
    #     _to = input('To: ')
    #     if _to == '':
    #         break
    #     to.append(_to)
    # subject = input('Subject: ')
    # content = input('Content: ')
    # msg = MIMEText(content, 'plain', 'utf-8')
    # msg['Subject'] = subject
    # msg['From'] = args.email

    # ! TEST
    msg = MIMEText('fixed test', 'plain', 'utf-8')
    msg['Subject'] = 'TEST' + repr(datetime.datetime.now())
    msg['From'] = 'usr1@mail.sustech.edu.cn'
    to = ['err@gmail.com', 'usr2@mail.sustech.edu.cn']
    # ! TEST

    # 发件失败退信功能
    # try:
    #     conn.sendmail(args.email, to, msg.as_string())
    # except SMTPSenderRefused:
    #     print(e)
    # except SMTPRecipientsRefused as e:
    #     print(e)
    #     conn = SMTP('localhost', int(fdns_query(SMTP_SERVER, 'P'))) # 需要再次连接
    #     conn.sendmail(args.email, [args.email], msg.as_string())
    try:
        conn.sendmail(args.email, to, msg.as_string())
    except (SMTPSenderRefused, SMTPRecipientsRefused, SMTPDataError) as e:
        print(f"agent: {repr(e)}")
    finally:
        conn.quit()


def pop():
    conn = POP3('localhost', int(fdns_query(POP_SERVER, 'P')))
    conn.set_debuglevel(1)
    print(conn.getwelcome())
    print(conn.user(args.email))
    print(conn.pass_(args.password))
    while True:
        try:
            cmd = input('[pop]>>> ').strip()
            arg = int(cmd[5:]) if len(cmd) > 4 else None
            cmd = cmd[:4].upper()

            if cmd == 'STAT':
                msg, bts = conn.stat()
                print(f'{msg} messages ({bts} bytes)')
            elif cmd == 'LIST':
                print(conn.list(arg)) if arg else print(conn.list()[1]) # 添加 LIST x功能    
            elif cmd == "RETR":
                msg = list(map(str, conn.retr(arg)[1]))
                print('\r\n'.join(msg))
            elif cmd == "DELE":
                print(conn.dele(arg))
            elif cmd == 'RSET':
                print(conn.rset())
            elif cmd == 'NOOP':
                print(conn.noop())
            elif cmd == 'QUIT':
                print(conn.quit())
                break
            else:
                print('Invalid command')
        except KeyboardInterrupt:
            conn.rset()
            raise
        except Exception as e:
            print('-ERR')
            print(repr(e))


if __name__ == '__main__':
    while True:
        try:
            cmd = input('[smtp|pop|exit]>>> ')
            if cmd == 'smtp':
                smtp()
            elif cmd == 'pop':
                pop()
            elif cmd == 'exit':
                break
            else:
                print('Invalid command')
        except KeyboardInterrupt:
            break
        except Exception as e:
            print('-ERR')
            print(repr(e))
