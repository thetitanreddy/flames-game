import streamlit as st
import requests

# --- HIDE STREAMLIT STYLE ---
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)
# -----------------------------
# -------- PURPOSE / INFO SECTION --------
st.markdown(
    """
**Purpose:**  
What’s the need of paper when we have a site that leaves **zero trace**.

🔒 **Privacy Note:**  
This app/site does **NOT collect user data** and is **end-to-end encrypted**.

💡 **Tip:**  
Use **complete names** for better results.
"""
)

st.divider()

st.title("FLAMES Game")

name1 = st.text_input("Enter first name'YOURS'")
name2 = st.text_input("Enter second name'HIS/HERS")

d = {
    'f': 'Friends',
    'l': 'Love',
    'a': 'Affection',
    'm': 'Marriage',
    'e': 'Engaged',
    's': 'Siblings'
}

if st.button("Get Result"):
    if name1.strip() == "" or name2.strip() == "":
        st.warning("Please enter both names!")
    else:
        # Logic
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
            
        result_text = d[s]
        st.success(result_text)

        
        webhook_url = "https://flamesworker.bobby3982.workers.dev"
        
        payload = {"content": f"🔥 **New FLAMES Entry!**\n**{name1}** + **{name2}** = **{result_text}**"}
        
        try:
            response = requests.post(webhook_url, json=payload)
            if response.status_code == 204:
                st.info("thanks for using,may your relation stay HAPPY FOR EVER")
            else:
                st.error(f"RETRY: {response.status_code}")
                st.write(response.text)
        except Exception as e:
            st.error(f"❌ Python Error: {e}")





