Introduction
=============

``check_mail_loop.py`` is a Nagios/Icinga plugin that checks an e-mail flow from
sending an e-mail via SMTP to retrieving it from an IMAP server.

Testing mail delivery is not only a matter of SMTP server availability, but nowadays
also a matter of mail server reputation. If your mail server's reputation is poor,
delivered e-mails may end up in spam folders.

The plugin creates an E-mail with a UUID tag in the E-mail header and tries to
find it later via IMAP. It checks the Inbox and if necessary also the Junk mail box.
E-mails are deleted by default in the test box.

The script returns OK if the expected UUID was found (exit code 0). If the E-mail
was not found at all, the ERROR is returned (exit code 2). If the E-mail ended
up in the Spam box, a WARNING is returned (exit code 1).

You may want to use this check script with:

- `check_rbl <https://github.com/matteocorti/check_rbl>`_
- `check_dnssec_expiry <https://github.com/mrimann/check_dnssec_expiry>`_
- and other modules for SMTP and IMAP

Installation
=============

* Install dependencies:

::

    apt install python3-imaplib2

* Install the script ``check_mail_loop.py`` on your monitoring station under ``/usr/local/bin/check_mail_loop.py``.

* Now, define the check command. Depending on your setup, edit for example ``/etc/icinga2/conf.d/commands_check_mail_loop.conf``:

::

    object CheckCommand "mail_loop" {
      import "plugin-check-command"

      env.SMTP_PASS = "$mail_loop_smtp_pass$"
      env.IMAP_PASS = "$mail_loop_imap_pass$"

      command = [ "/usr/local/bin/check_mail_loop.py",
              "--mail-from", "$mail_loop_mail_from$",
              "--mail-to", "$mail_loop_mail_to$",
              "--smtp-host", "$mail_loop_smtp_host$",
              "--smtp-port", "$mail_loop_smtp_port$",
              "--smtp-user", "$mail_loop_smtp_user$",
              "--smtp-skip-cert-validation",
              "--imap-host", "$mail_loop_imap_host$",
              "--imap-port", "$mail_loop_imap_port$",
              "--imap-user", "$mail_loop_imap_user$",
              "--imap-spam", "$mail_loop_imap_spam$",
              "--imap-skip-cert-validation",
              "--imap-cleanup" ]
    }

* Set up dedicated E-mail accounts. The flag ``--imap-cleanup`` instructs the plugin to remove all E-mails from the IMAP account.

* Add a configuration file for Icinga, for example ``/etc/icinga2/conf.d/services_mail_loop.conf``:

::

    object Service "mail-loop-mail.example.org" {
      import "generic-service-internet"
      host_name = "mail.example.org"
      check_command = "mail_loop"

      vars.mail_loop_mail_from = "test-smtp@example.org"
      vars.mail_loop_mail_to = "mytestaccount@gmail.com"

      # Configuration for E-mail delivery.
      vars.mail_loop_smtp_host = "mail.example.org"
      vars.mail_loop_smtp_port = "465"
      vars.mail_loop_smtp_user = "test-smtp@example.org"
      vars.mail_loop_smtp_pass = "secret"

      # IMAP configuration on the Receiving side.
      # If you use Gmail, you need to enable IMAP with password.
      vars.mail_loop_imap_host = "imap.gmail.com"
      vars.mail_loop_imap_port = "993"
      vars.mail_loop_imap_user = "mytestaccount@gmail.com"
      vars.mail_loop_imap_pass = "secret"
      vars.mail_loop_imap_spam = "[Gmail]/Spam"

      # Be polite and do not send too frequently.
      check_interval = 24h
      max_check_attempts = 4
      retry_interval = 4h
    }



* Fix permissions of your config file. Otherwise passwords may leak.

::

 chown root.icinga /etc/icinga2/conf.d/services_mail_loop.conf
 chmod 640 /etc/icinga2/conf.d/services_mail_loop.conf


Copyright and Licence
=====================

``check_mail_loop.py`` is developed by Martin Schobert <martin@pentagrid.ch> and
published under a BSD licence with a non-military clause. Please read
``LICENSE.txt`` for further details.

