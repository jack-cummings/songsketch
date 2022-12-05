import smtplib
from email.message import EmailMessage

email_address = "johnmcummings3@gmail.com"
email_password = "rejaktcirgbqtbhy"

# create email
msg = EmailMessage()
msg['Subject'] = "Song Sketch Log - success"
msg['From'] = email_address
msg['To'] = email_address
msg.set_content("This is eamil message")

# send email
with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
    smtp.login(email_address, email_password)
    smtp.send_message(msg)