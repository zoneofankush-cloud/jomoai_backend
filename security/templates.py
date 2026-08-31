import datetime as dt

def get_otp_html(otp: str) -> str:
    """Returns a premium, modern SaaS HTML string for the OTP email (Responsive Light Mode)."""
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            /* Base Styles (Desktop-first approach) */
            body {{
                margin: 0;
                padding: 0;
                font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                background-color: #F4F4F5;
                color: #27272A;
                -webkit-font-smoothing: antialiased;
            }}
            .wrapper {{
                width: 100%;
                background-color: #F4F4F5;
                padding: 40px 16px; /* Added horizontal padding so it doesn't touch screen edges on mobile */
                box-sizing: border-box;
            }}
            .container {{
                max-width: 520px;
                width: 100%;
                margin: 0 auto;
                background-color: #FFFFFF;
                border-radius: 12px;
                padding: 48px;
                box-sizing: border-box;
                box-shadow: 0 4px 24px rgba(0, 0, 0, 0.04);
            }}
            .header {{
                text-align: center;
                margin-bottom: 32px;
            }}
            .logo {{
                font-size: 28px;
                font-weight: 800;
                letter-spacing: -1px;
                color: #18181B;
                margin: 0;
            }}
            .logo span {{
                color: #E07A5F;
            }}
            .greeting {{
                font-size: 20px;
                font-weight: 600;
                color: #18181B;
                margin-bottom: 12px;
                text-align: center;
            }}
            .text {{
                font-size: 15px;
                line-height: 1.6;
                color: #52525B;
                text-align: center;
                margin-bottom: 32px;
            }}
            .otp-container {{
                background-color: #FFF1EE;
                border: 1px solid #FADED5;
                border-radius: 8px;
                padding: 24px;
                text-align: center;
                margin-bottom: 32px;
            }}
            .otp-code {{
                font-size: 42px;
                font-weight: 700;
                letter-spacing: 12px;
                color: #E07A5F;
                margin: 0;
                padding-left: 12px; 
            }}
            .divider {{
                height: 1px;
                background-color: #E4E4E7;
                margin: 32px 0;
            }}
            .security-notice {{
                font-size: 13px;
                line-height: 1.5;
                color: #71717A;
                text-align: center;
            }}
            .footer {{
                text-align: center;
                margin-top: 32px;
            }}
            .copyright {{
                font-size: 12px;
                color: #A1A1AA;
                margin: 0;
            }}

            /* Mobile Responsive Styles */
            @media only screen and (max-width: 600px) {{
                .wrapper {{
                    padding: 20px 12px;
                }}
                .container {{
                    padding: 32px 24px;
                    border-radius: 10px;
                }}
                .logo {{
                    font-size: 24px;
                }}
                .greeting {{
                    font-size: 18px;
                }}
                .text {{
                    font-size: 14px;
                    margin-bottom: 24px;
                }}
                .otp-container {{
                    padding: 20px 16px;
                    margin-bottom: 24px;
                }}
                .otp-code {{
                    font-size: 32px; /* Smaller font for mobile */
                    letter-spacing: 6px; /* Less spacing so it fits 1 line */
                    padding-left: 6px;
                }}
                .divider {{
                    margin: 24px 0;
                }}
            }}
            
            /* Extra small screens (e.g., iPhone SE) */
            @media only screen and (max-width: 360px) {{
                .otp-code {{
                    font-size: 28px;
                    letter-spacing: 4px;
                    padding-left: 4px;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="wrapper">
            <div class="container">
                <div class="header">
                    <h1 class="logo">JOMO<span>.</span>AI</h1>
                </div>
                
                <div class="greeting">Login Verification</div>
                
                <div class="text">
                    You are trying to sign in to your Jomo AI account. Please enter the verification code below to confirm your identity.
                </div>
                
                <div class="otp-container">
                    <p class="otp-code">{otp}</p>
                </div>
                
                <div class="security-notice">
                    🔒 This code will expire in <strong>5 minutes</strong>.<br>
                    If you did not request this, please ignore this email.
                </div>
                
                <div class="divider"></div>
                
                <div class="footer">
                    <p class="copyright">© {dt.datetime.now().year if 'dt' in globals() else 2026} Jomo AI Inc.</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return html
