# 1xx — Positive Preliminary
R_125 = "125 Data connection already open (Transfer starting)"
R_150 = "150 File status okay, opening data connection"

# 2xx — Positive Completion
R_200 = "200 Command OK"
R_211 = "211 System status, or system help reply"
R_215 = "215 UNIX Type: L8"
R_220 = "220 Service ready for new user"
R_221 = "221 Goodbye"
R_226 = "226 Closing data connection Transfer complete"
R_230 = "230 Login successful, proceed"
R_250 = "250 Requested file action OK"
R_257 = "257 \"{path}\" is current directory"  # Use .format(path=...) when sending

# 3xx — Positive Intermediate
R_331 = "331 Username OK, need password"
R_350 = "350 Requested file action pending RNTO"

# 4xx — Transient Negative
R_421 = "421 Service unavailable, closing control connection"
R_425 = "425 Cannot open data connection"
R_426 = "426 Connection closed; transfer aborted"
R_450 = "450 File unavailable"

# 5xx — Permanent Negative
R_500 = "500 Syntax error"
R_501 = "501 Syntax error in parameters"
R_502 = "502 Command not implemented"
R_503 = "503 Bad sequence of commands"
R_530 = "530 Not logged in"
R_550 = "550 File unavailable"
