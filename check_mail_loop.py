#!/usr/bin/env python3
#
# -----------------------------------------------------------------------------
# Copyright (c) 2023-2025 Martin Schobert, Pentagrid AG
#
# All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
#  ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
#  WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
#  ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
#  (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
#  LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
#  ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
#  SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
#  The views and conclusions contained in the software and documentation are those
#  of the authors and should not be interpreted as representing official policies,
#  either expressed or implied, of the project.
#
#  NON-MILITARY-USAGE CLAUSE
#  Redistribution and use in source and binary form for military use and
#  military research is not permitted. Infringement of these clauses may
#  result in publishing the source code of the utilizing applications and
#  libraries to the public. As this software is developed, tested and
#  reviewed by *international* volunteers, this clause shall not be refused
#  due to the matter of *national* security concerns.
# -----------------------------------------------------------------------------

import smtplib
import imaplib
import argparse
import uuid
import sys
import os
import ssl
import time
from email.mime.text import MIMEText
from enum import Enum
from typing import Optional


class MailFound(Enum):
	UNDEFINED = 0
	FOUND = 1
	FOUND_IN_SPAM = 2
	NOT_FOUND = 3


# global flags
debug_flag = False

# time to wait
delay = 10


def debug(message: str) -> None:
	if debug_flag:
		print(message)


def email_create_message(mail_from: str, mail_to: str, _uuid: str) -> MIMEText:
	"""
	Create an E-mail.

	@param mail_from: The sender's E-mail address for the E-mail header.
	@param mail_to: The recipients E-mail address for the E-mail header.
	@param _uuid: Add this UUID as additional X-Icinga-Test-Id header.
	@return Function returns a MIMEText object.
	"""

	text = ("Dear Mail Server,\n\n"
			"This is your friendly Mail Check. It’s time for your regularly scheduled health inspection. You’ve been "
			"delivering e-mails like a champ. I hope your overall health is at its best. Today I am writing you "
			"another e-mail.\n\n"
			"Please remember, a healthy server is a happy server. Regular maintenance keeps you from joining the "
			"ghostly ranks of \"former production systems.\" Think of updates as vitamins. They might taste bad now, "
			"but they prevent those \"critical condition\" messages that make sysadmins cry in the dark.\n\n"
			"Anyway, just checking in. Stay cool, keep those ports open (the safe ones), and remember: if you ever "
			"start to feel sluggish, I'm only one alert away. I will write to you again very soon.\n\n"
			"Warm regards,\n\n"
			"Your mail check plugin\n")

	msg = MIMEText(text)

	msg["From"] = mail_from
	msg["To"] = mail_to
	msg["Subject"] = "Mail test"
	msg["X-Icinga-Test-Id"] = _uuid

	return msg


def smtp_connect(smtp_host: str, smtp_port: int, smtp_user: str, smtp_pass: str, smtp_skip_cert_validation: bool) -> smtplib.SMTP:
	"""
	Connect to an SMTPS server.

	@param smtp_host: The mail server host.
	@param smtp_port: The SMTP server port. STARTSSL or plaintext communication is not supported.
	@param smtp_user: The username for SMTP authentication.
	@param smtp_pass: The password for SMTP authentication.
	@param smtp_skip_cert_validation: Skip the validation of the SMTP Server provided certificate.
	@return Function returns a smtplib.SMTP object that represents a server connection.
	"""
	server = smtplib.SMTP_SSL(smtp_host, smtp_port, context=create_ssl_context(smtp_skip_cert_validation))
	debug(f"SMTP: Try to log in to {smtp_host} as: {smtp_user}")
	server.login(smtp_user, smtp_pass)
	debug(f"SMTP: Log in was successful.")

	return server


def imap_retrieve_mail(imap_host: str, imap_port: int, imap_user: str, imap_pass: str, imap_spambox: Optional[str],
					   expected_token: str, cleanup_flag: bool, imap_skip_cert_validation) -> MailFound:
	"""
	Retrieve an e-mail from an IMAP account. Search the INBOX and the Spambox for a specific token value.
	Retry up to three times.

	@param imap_host: The mail server host.
	@param imap_port: The SMTP server port. STARTSSL or plaintext communication is not supported.
	@param imap_user: The username for SMTP authentication.
	@param imap_pass: The password for SMTP authentication.
	@param imap_spambox: The name of the spam mailbox, where the mail is also searched. Pass None to skip.
	@param expected_token: Lookup this token in a X-Icinga-Test-Id E-mail header.
	@param cleanup_flag: Remove mails from the IMAP account.
	@param imap_skip_cert_validation: Skip the validation of the IMAP Server provided certificate.

	@return Function returns a MailFound status.
	"""

	# Establish IMAP connection
	server = imaplib.IMAP4_SSL(host=imap_host, port=imap_port, ssl_context=create_ssl_context(imap_skip_cert_validation))
	debug(f"IMAP: Try to log in to {imap_host} as: {imap_user}")
	server.login(imap_user, imap_pass)
	debug(f"IMAP: Log in was successful.")

	status = MailFound.NOT_FOUND

	# Check which mailboxes to lookup. Start with the spam box (if enabled) to clean it up.
	mailboxes = []
	if imap_spambox:
		debug(f"IMAP: Will also check spambox \"{imap_spambox}\".")
		mailboxes.append(imap_spambox)
	mailboxes.append("INBOX")

	for i in range(0, 3):

		curr_delay = delay * pow(i+1, 2)
		if curr_delay > 0:
			debug(f"IMAP: Waiting for {curr_delay} seconds.")
			time.sleep(curr_delay)

		for mailbox in mailboxes:
			status = imap_search_server(server, mailbox, expected_token, cleanup_flag)
			if status != MailFound.NOT_FOUND:
				server.logout()
				return status

	server.logout()
	return status


def imap_search_server(server: imaplib.IMAP4, mailbox: str, expected_token: str, cleanup_flag: bool) -> MailFound:
	"""
	Lookup token on IMAP server.

	@param server: An imaplib.IMAP4 object that represents the sever connection.
	@param mailbox: Name of the mailbox, such as INBOX or Junk.
	@param expected_token: Lookup this token in a "X-Icinga-Test-Id" E-mail header.
	@param cleanup_flag: Remove mails from the IMAP account.
	@return Function returns a MailFound status.
	"""

	class Email:
		def __init__(self, _data):
			self.data = _data.decode()
			self.header = "\r\n\r\n".join(self.data.split("\r\n\r\n")[0:1])

	token_found = MailFound.NOT_FOUND
	token = ""

	debug(f"IMAP: Check mail in mailbox {mailbox}.")
	select_status, num_msg_in_mbox = server.select(mailbox)
	num_msg_in_mbox = int(num_msg_in_mbox[0])
	debug(f"IMAP: Mailbox selection status: {select_status}")
	debug(f"IMAP: Mailbox {mailbox} contains {num_msg_in_mbox} messages.")

	typ, data_mlist = server.search(None, 'ALL')

	if typ != "OK":
		return MailFound.UNDEFINED

	for num in data_mlist[0].split():

		num_str = num.decode('utf-8')

		if token_found == MailFound.NOT_FOUND:

			typ, data_mail = server.fetch(num_str, '(RFC822)')
			debug(f"IMAP: [{mailbox}]:{num_str} Check mail {num_str}.")
			email = Email(data_mail[0][1])
			for line in email.header.splitlines():

				if line.startswith("X-Icinga-Test-Id"):
					token = line.split("X-Icinga-Test-Id: ")[1].strip()
					debug(f"IMAP: [{mailbox}]:{num_str} A token was found: {token}")

			if token == expected_token:
				debug(f"IMAP: [{mailbox}]:{num_str} Expected token {token} found in {mailbox}.")
				if mailbox == "INBOX":
					token_found = MailFound.FOUND
				else:
					token_found = MailFound.FOUND_IN_SPAM
				break
			else:
				debug(f"IMAP: [{mailbox}]:{num_str} Expected token was not found in this e-mail.")

		if cleanup_flag:
			debug(f"IMAP: [{mailbox}]:{num_str} Mark mail {num_str} as deleted.")
			server.store(num, '+FLAGS', '\\Deleted')

	if cleanup_flag:
		server.expunge()
	server.close()

	return token_found

def create_ssl_context(skip_validation: bool) -> ssl.SSLContext:
	"""
	Create the SSL Context used for the connection to the SMTP or IMAP server.

	@param skip_validation: Whether or not to validate server certificate.
	@return ssl.SSLContext
	"""
	context = ssl.create_default_context()
	if skip_validation:
		context.check_hostname = False
		context.verify_mode = ssl.CERT_NONE
	return context

def main():
	global debug_flag, delay

	parser = argparse.ArgumentParser(description='Check SMTP to IMAPS health status.')

	parser.add_argument('--debug', action='store_true', help="Enable verbose output.")

	parser.add_argument('--mail-from', metavar='MAIL_FROM', help='Mail: Use this sender address.', required=True)
	parser.add_argument('--mail-to', metavar='MAIL_TO', help='Mail: Use this recipient address.', required=True)

	parser.add_argument('--smtp-host', metavar='SMTP_HOST', help='SMTP: Hostname of the SMTP server.', required=True)
	parser.add_argument('--smtp-port', metavar='SMTP_PORT',
						help='SMTP: Deliver mail via this port. STARTTLS or plaintext communication is not supported.',
						type=int, default=465)
	parser.add_argument('--smtp-user', metavar='SMTP_USER', help='SMTP: User name for login.', required=True)
	parser.add_argument('--smtp-pass', metavar='SMTP_PASS',
						help='SMTP: Passwort for login. Alternatively, set environment variable SMTP_PASS.',
						default=os.getenv("SMTP_PASS"))
	parser.add_argument('--smtp-skip-cert-validation', action='store_true', help="Do not validate SMTP Server Certificate")

	parser.add_argument('--imap-host', metavar='IMAP_HOST', help='IMAP: Hostname of the IMAP server.', required=True)
	parser.add_argument('--imap-port', metavar='IMAP_PORT', help='IMAP: Fetch mail via this port.', type=int,
						default=993)
	parser.add_argument('--imap-user', metavar='IMAP_USER', help='IMAP: User name for login.', required=True)
	parser.add_argument('--imap-pass', metavar='IMAP_PASS',
						help='IMAP: Passwort for login. Alternatively, set environment variable IMAP_PASS.',
						default=os.getenv("IMAP_PASS"))
	parser.add_argument('--imap-spam', metavar='IMAP_SPAM', help='IMAP: Name of the spam box.')
	parser.add_argument('--imap-cleanup', action='store_true', help="Delete processed mails on the IMAP account.")
	parser.add_argument('--imap-skip-cert-validation', action='store_true', help="Do not validate IMAP Server Certificate")

	parser.add_argument('--delay', metavar='SECONDS', help=f"Delay between sending and retrieving (default {delay} s).",
						type=int, default=delay)
	args = parser.parse_args()

	debug_flag = args.debug
	delay = args.delay

	_uuid = str(uuid.uuid4())
	email = email_create_message(args.mail_from, args.mail_to, _uuid)
	smtp_server = smtp_connect(args.smtp_host, args.smtp_port, args.smtp_user, args.smtp_pass, args.smtp_skip_cert_validation)
	smtp_server.sendmail(args.mail_from, args.mail_to, email.as_string())
	debug(f"SMTP: Sent e-mail with ID {_uuid} to {args.mail_to}.")

	status = imap_retrieve_mail(args.imap_host, args.imap_port, args.imap_user, args.imap_pass, args.imap_spam, _uuid,
								args.imap_cleanup, args.imap_skip_cert_validation)

	if status == MailFound.FOUND:
		print("OK")
		return 0
	elif status == MailFound.FOUND_IN_SPAM:
		debug("WARNING - Message found in Spam folder")
		return 1
	elif status == MailFound.NOT_FOUND:
		print("ERROR - Message not found")
		return 2
	else:
		print("UNDEFINED - Undefined state")
		return 3


if __name__ == "__main__":
	sys.exit(main())
