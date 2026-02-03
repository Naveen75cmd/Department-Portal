import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime
import mimetypes

# -----------------------------------------------------------------------------
# Supabase Configuration
# -----------------------------------------------------------------------------
# REPLACE THESE WITH YOUR ACTUAL SUPABASE CREDENTIALS
# REPLACE THESE WITH YOUR ACTUAL SUPABASE CREDENTIALS
# url = "https://vokepxkztiqimvbplxvl.supabase.co/"
# key = "..."
# Using Streamlit Secrets for security (Best Practice)
url = st.secrets["supabase"]["url"]
key = st.secrets["supabase"]["key"]

@st.cache_resource
def init_supabase():
    """Initialize Supabase client."""
    try:
        return create_client(url, key)
    except Exception as e:
        st.error(f"Failed to connect to Supabase: {e}")
        return None

supabase = init_supabase()

# -----------------------------------------------------------------------------
# Session State Management
# -----------------------------------------------------------------------------
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_role' not in st.session_state:
    st.session_state['user_role'] = None
if 'username' not in st.session_state:
    st.session_state['username'] = None
if 'name' not in st.session_state:
    st.session_state['name'] = None

# -----------------------------------------------------------------------------
# Authentication Functions
# -----------------------------------------------------------------------------
def login_user(username, password):
    """Verify credentials against Supabase users table."""
    try:
        response = supabase.table('users').select('*').eq('username', username).eq('password', password).execute()
        if len(response.data) > 0:
            user = response.data[0]
            st.session_state['logged_in'] = True
            st.session_state['user_role'] = user['role']
            st.session_state['username'] = user['username']
            st.session_state['name'] = user['name']
            st.success(f"Welcome, {user['name']}!")
            st.rerun()
        else:
            st.error("Invalid username or password")
    except Exception as e:
        st.error(f"Login failed: {e}")

def logout_user():
    """Clear session state and logout."""
    st.session_state['logged_in'] = False
    st.session_state['user_role'] = None
    st.session_state['username'] = None
    st.session_state['name'] = None
    st.rerun()

# -----------------------------------------------------------------------------
# Database Helper Functions
# -----------------------------------------------------------------------------
def fetch_circulars(limit=5):
    """Fetch latest circulars."""
    try:
        response = supabase.table('circulars').select('*').order('date_posted', desc=True).limit(limit).execute()
        return response.data
    except Exception as e:
        st.error(f"Error fetching circulars: {e}")
        return []

def publish_new_circular(title, content):
    """Insert a new circular."""
    try:
        supabase.table('circulars').insert({'title': title, 'content': content}).execute()
        st.success("Circular published successfully!")
    except Exception as e:
        st.error(f"Error publishing circular: {e}")

def upload_file_to_storage(file, username):
    """Upload file to Supabase storage and return public URL."""
    try:
        # Create a unique filename
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        file_ext = mimetypes.guess_extension(file.type) or ".pdf"
        file_name = f"{username}_{timestamp}{file_ext}"
        
        # Upload
        file_bytes = file.getvalue()
        supabase.storage.from_('documents').upload(file_name, file_bytes, {"content-type": file.type})
        
        # Get Public URL
        public_url_response = supabase.storage.from_('documents').get_public_url(file_name)
        return public_url_response
    except Exception as e:
        st.error(f"File upload failed: {e}")
        return None

def submit_leave_request(username, name, leave_type, reason, file_url):
    """Submit a new leave request."""
    try:
        data = {
            'student_name': name, # Storing name for easier display, or could store username
            'leave_type': leave_type,
            'reason': reason,
            'file_url': file_url,
            'status': 'Pending Staff'
        }
        supabase.table('leave_requests').insert(data).execute()
        st.success("Leave request submitted successfully!")
    except Exception as e:
        st.error(f"Error submitting request: {e}")

def fetch_student_requests(student_name):
    """Fetch requests for a specific student."""
    try:
        response = supabase.table('leave_requests').select('*').eq('student_name', student_name).order('date_requested', desc=True).execute()
        return response.data
    except Exception as e:
        st.error(f"Error fetching requests: {e}")
        return []

def fetch_pending_requests(status_filter):
    """Fetch requests based on status."""
    try:
        response = supabase.table('leave_requests').select('*').eq('status', status_filter).order('date_requested', desc=True).execute()
        return response.data
    except Exception as e:
        st.error(f"Error fetching pending requests: {e}")
        return []

def update_request_status(request_id, new_status, staff_comment=""):
    """Update the status of a request."""
    try:
        update_data = {'status': new_status}
        if staff_comment:
            update_data['staff_comment'] = staff_comment
            
        supabase.table('leave_requests').update(update_data).eq('id', request_id).execute()
        st.success(f"Request updated to: {new_status}")
        st.rerun()
    except Exception as e:
        st.error(f"Error updating status: {e}")

# -----------------------------------------------------------------------------
# Dashboards
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# Main App Structure
# -----------------------------------------------------------------------------
def load_custom_css():
    st.markdown("""
        <style>
        /* General Button Styling */
        div.stButton > button {
            font-weight: bold;
            border-radius: 8px;
        }
        
        /* Secondary Button (Default) - Used for Approve/Forward -> Green Hover */
        button[kind="secondary"]:hover, 
        button[data-testid="baseButton-secondary"]:hover {
            border-color: #28a745 !important;
            color: #28a745 !important;
            background-color: rgba(40, 167, 69, 0.1) !important;
        }

        /* Primary Button - Used for Reject -> Red Hover */
        button[kind="primary"]:hover, 
        button[data-testid="baseButton-primary"]:hover {
            border-color: #dc3545 !important;
            background-color: #dc3545 !important;
            color: white !important;
        }
        
        /* Dashboard Headers */
        h1, h2, h3 {
            color: #333;
        }
        </style>
    """, unsafe_allow_html=True)

def student_dashboard():
    st.sidebar.title("🎓 Student Portal")
    st.sidebar.write(f"👋 Logged in as: **{st.session_state['name']}**")
    if st.sidebar.button("🚪 Logout"):
        logout_user()

    tab1, tab2, tab3 = st.tabs(["📢 Latest Circulars", "📝 Apply for Leave/OD", "📜 Request History"])

    with tab1:
        st.header("📢 Latest Circulars")
        circulars = fetch_circulars()
        if circulars:
            for c in circulars:
                st.subheader(f"📌 {c['title']}")
                st.write(c['content'])
                st.caption(f"📅 Posted on: {c['date_posted']}")
                st.divider()
        else:
            st.info("ℹ️ No circulars found.")

    with tab2:
        st.header("📝 Apply for Leave / On-Duty")
        with st.form("leave_form"):
            l_type = st.selectbox("📌 Type", ["Medical Leave", "OD", "Casual Leave"])
            reason = st.text_area("✍️ Reason")
            uploaded_file = st.file_uploader("📎 Upload Supporting Document", type=['pdf', 'jpg', 'png'])
            
            submitted = st.form_submit_button("✅ Submit Request")
            if submitted:
                if not reason:
                    st.warning("⚠️ Please provide a reason.")
                else:
                    file_url = None
                    if uploaded_file:
                        with st.spinner("⏳ Uploading document..."):
                            file_url = upload_file_to_storage(uploaded_file, st.session_state['username'])
                    
                    if uploaded_file and not file_url:
                         st.error("❌ Failed to upload document. Please try again.")
                    else:
                        submit_leave_request(st.session_state['name'], st.session_state['name'], l_type, reason, file_url)

    with tab3:
        st.header("📜 My Request History")
        requests = fetch_student_requests(st.session_state['name'])
        if requests:
            df = pd.DataFrame(requests)
            # Display specific columns
            st.dataframe(df[['date_requested', 'leave_type', 'status', 'staff_comment']])
        else:
            st.info("ℹ️ No request history found.")

def staff_dashboard():
    st.sidebar.title("👨‍🏫 Staff Portal")
    st.sidebar.write(f"👋 Logged in as: **{st.session_state['name']}**")
    if st.sidebar.button("🚪 Logout"):
        logout_user()

    tab1, tab2 = st.tabs(["👤 Profile", "⚡ Leave Processing"])

    with tab1:
        st.header("👤 My Profile")
        st.write(f"**Name:** {st.session_state['name']}")
        st.write(f"**Role:** {st.session_state['user_role']}")
        st.write(f"**Username:** {st.session_state['username']}")

    with tab2:
        st.header("⚡ Pending Leave Requests")
        requests = fetch_pending_requests('Pending Staff')
        
        if requests:
            for req in requests:
                with st.expander(f"📄 {req['student_name']} - {req['leave_type']} ({req['date_requested']})"):
                    st.write(f"**✍️ Reason:** {req['reason']}")
                    if req['file_url']:
                        st.markdown(f"[📎 View Document]({req['file_url']})")
                    else:
                        st.write("🚫 No document attached.")
                    
                    # Comment Section
                    staff_comment = st.text_area("💬 Add Comment (Optional)", key=f"comment_{req['id']}")

                    col1, col2 = st.columns(2)
                    with col1:
                        # Use default (secondary) button for positive action -> Green hover via CSS
                        if st.button("✅ Forward to HOD", key=f"fwd_{req['id']}"):
                            update_request_status(req['id'], "Pending HOD", staff_comment)
                    with col2:
                        # Use type="primary" for negative action -> Red hover via CSS
                        if st.button("❌ Reject", key=f"rej_{req['id']}", type="primary"):
                            update_request_status(req['id'], "Rejected by Staff", staff_comment)
        else:
            st.info("✅ No pending requests.")

def hod_dashboard():
    st.sidebar.title("🎓 HOD Portal")
    st.sidebar.write(f"👋 Logged in as: **{st.session_state['name']}**")
    if st.sidebar.button("🚪 Logout"):
        logout_user()

    tab1, tab2, tab3 = st.tabs(["👤 Profile", "📢 Publish Circular", "✅ Approvals"])

    with tab1:
        st.header("👤 My Profile")
        st.write(f"**Name:** {st.session_state['name']}")
        st.write(f"**Role:** {st.session_state['user_role']}")

    with tab2:
        st.header("📢 Publish New Circular")
        with st.form("circular_form"):
            title = st.text_input("📌 Title")
            content = st.text_area("📝 Content")
            submitted = st.form_submit_button("🚀 Publish")
            if submitted:
                if title and content:
                    publish_new_circular(title, content)
                else:
                    st.warning("⚠️ Please fill in both title and content.")

    with tab3:
        st.header("✅ Pending Approvals")
        requests = fetch_pending_requests('Pending HOD')
        
        if requests:
            for req in requests:
                with st.expander(f"📄 {req['student_name']} - {req['leave_type']} ({req['date_requested']})"):
                    st.write(f"**✍️ Reason:** {req['reason']}")
                    if req['file_url']:
                        st.markdown(f"[📎 View Document]({req['file_url']})")
                    
                    # Comment Section
                    hod_comment = st.text_area("💬 Add Comment (Optional)", key=f"comment_hod_{req['id']}")

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ Approve", key=f"app_{req['id']}"):
                            update_request_status(req['id'], "Approved", hod_comment)
                    with col2:
                        if st.button("❌ Reject", key=f"rej_hod_{req['id']}", type="primary"):
                            update_request_status(req['id'], "Rejected by HOD", hod_comment)
        else:
            st.info("✅ No requests pending approval.")

# -----------------------------------------------------------------------------
# Main App Structure
# -----------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="Dept. Management Portal", page_icon="🎓", layout="wide")
    load_custom_css()
    
    if not st.session_state['logged_in']:
        st.title("🎓 Department Portal Login")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.form("login_form"):
                username = st.text_input("👤 Username")
                password = st.text_input("🔑 Password", type="password")
                submit_button = st.form_submit_button("🚀 Login")
                
                if submit_button:
                    if username and password:
                        login_user(username, password)
                    else:
                        st.warning("⚠️ Please enter both username and password")
    else:
        role = st.session_state['user_role']
        if role == 'student':
            student_dashboard()
        elif role == 'staff':
            staff_dashboard()
        elif role == 'hod':
            hod_dashboard()
        else:
            st.error("Unknown role detected. Please contact admin.")
            if st.button("Force Logout"):
                logout_user()

if __name__ == "__main__":
    main()
