import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime
import mimetypes
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# -----------------------------------------------------------------------------
# Supabase Configuration
# -----------------------------------------------------------------------------
try:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
except Exception:
    st.error("Missing Supabase credentials in .streamlit/secrets.toml")
    st.stop()

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
# Email Configuration
# -----------------------------------------------------------------------------
def send_email_notification(to_email, subject, body):
    """Send email using SMTP."""
    # Only try to send if email secrets are configured
    if "email" not in st.secrets:
        print(f"Skipping email to {to_email}: No email secrets configured.")
        return

    sender_email = st.secrets["email"]["sender_email"]
    password = st.secrets["email"]["password"]
    smtp_server = st.secrets["email"]["smtp_server"]
    smtp_port = st.secrets["email"]["smtp_port"]

    try:
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, password)
        if "@" in to_email: 
             server.send_message(msg)
        server.quit()
    except Exception as e:
        print(f"Failed to send email: {e}") 
        # We don't want to crash the UI if email fails
        pass

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
if 'section' not in st.session_state:
    st.session_state['section'] = None

# Custom CSS
def load_custom_css():
    st.markdown("""
        <style>
        div.stButton > button { font-weight: bold; border-radius: 8px; }
        .stBadge { font-size: 0.8em; padding: 4px 8px; border-radius: 4px; }
        /* Badge Colors */
        .status-pending-staff { background-color: #ffeeba; color: #856404; }
        .status-pending-hod { background-color: #bee5eb; color: #0c5460; }
        .status-pending-principal { background-color: #e2e3e5; color: #383d41; }
        .status-approved { background-color: #d4edda; color: #155724; }
        .status-rejected { background-color: #f8d7da; color: #721c24; }
        </style>
    """, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Authentication
# -----------------------------------------------------------------------------
def login_user(username, password):
    try:
        response = supabase.table('users').select('*').eq('username', username).eq('password', password).execute()
        if len(response.data) > 0:
            user = response.data[0]
            st.session_state['logged_in'] = True
            st.session_state['user_role'] = user['role']
            st.session_state['username'] = user['username']
            st.session_state['name'] = user['name']
            st.session_state['section'] = user.get('section')
            st.success(f"Welcome, {user['name']}!")
            st.rerun()
        else:
            st.error("Invalid username or password")
    except Exception as e:
        st.error(f"Login failed: {e}")

def logout_user():
    st.session_state.clear()
    st.rerun()

# -----------------------------------------------------------------------------
# Database Actions
# -----------------------------------------------------------------------------
def upload_file_to_storage(file, username):
    """Upload file to Supabase storage."""
    try:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        file_ext = mimetypes.guess_extension(file.type) or ".pdf"
        file_name = f"{username}_{timestamp}{file_ext}"
        file_bytes = file.getvalue()
        supabase.storage.from_('documents').upload(file_name, file_bytes, {"content-type": file.type})
        return supabase.storage.from_('documents').get_public_url(file_name)
    except Exception as e:
        st.error(f"File upload failed: {e}")
        return None

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------
def get_staff_emails(section):
    """Fetch emails of all staff members for a specific section."""
    try:
        response = supabase.table('users').select('email').eq('role', 'staff').eq('section', section).execute()
        return [row['email'] for row in response.data if row.get('email')]
    except Exception as e:
        print(f"Error fetching staff emails: {e}")
        return []

def get_user_email(username):
    """Fetch email of a specific user."""
    try:
        response = supabase.table('users').select('email').eq('username', username).execute()
        if response.data and response.data[0].get('email'):
            return response.data[0]['email']
        return None
    except Exception:
        return None

        return None

def submit_leave_request(username, name, section, leave_type, reason, file_url):
    try:
        data = {
            'student_username': username,
            'student_name': name,
            'student_section': section,
            'leave_type': leave_type,
            'reason': reason,
            'file_url': file_url,
            'status': 'Pending Staff'
        }
        supabase.table('leave_requests').insert(data).execute()
        st.success("Prioritizing Staff Notification...")
        
        # Email Logic: Find Staff for this section
        staff_emails = get_staff_emails(section)
        timestamp = datetime.now().strftime("%H:%M:%S")
        for email in staff_emails:
            send_email_notification(
                email, 
                f"New Leave Request from {name} - [Ref: {timestamp}]", 
                f"Hi there,\n\n"
                f"Just a quick heads-up — {name} from Section {section} has submitted a new {leave_type} leave request.\n\n"
                f"Reason: {reason}\n\n"
                f"Please log in to the portal to review and take action.\n\n"
                f"Thanks,\nDepartment Portal"
            )
            
        st.success("Leave request submitted successfully!")
    except Exception as e:
        st.error(f"Error submitting request: {e}")

def update_request_status(req_id, new_status, comment="", role_action=""):
    try:
        update_data = {'status': new_status}
        if role_action == "staff":
            update_data['staff_comment'] = comment
        elif role_action == "hod":
            update_data['hod_comment'] = comment
        elif role_action == "principal":
            update_data['principal_comment'] = comment
            
        # Get the request details to find the student
        req_res = supabase.table('leave_requests').select('student_username').eq('id', req_id).execute()
        student_username = req_res.data[0]['student_username'] if req_res.data else None
            
        supabase.table('leave_requests').update(update_data).eq('id', req_id).execute()
        
        # Trigger Email
        timestamp = datetime.now().strftime("%H:%M:%S")
        if student_username:
            student_email = get_user_email(student_username)
            if student_email:
                subject = f"Leave Update: {new_status} - [Ref: {timestamp}]"
                comment_line = f"\nYour reviewer noted: \"{comment}\"\n" if comment else "\n"
                body = (
                    f"Hi {student_username},\n\n"
                    f"We wanted to let you know that your leave request has been reviewed and the status is now: {new_status}.\n"
                    f"{comment_line}\n"
                    f"If you have any questions, feel free to reach out to your section coordinator.\n\n"
                    f"Best regards,\nDepartment Portal"
                )
                send_email_notification(student_email, subject, body)
        
        # Notify Principal if forwarded by HOD
        if new_status == "Pending Principal":
            principal_email = get_user_email('principal')
            if principal_email:
                send_email_notification(
                    principal_email,
                    f"Action Needed: Leave forwarded by HOD - [Ref: {timestamp}]",
                    f"Hello Principal,\n\n"
                    f"The HOD has forwarded a leave request from {student_username} for your review.\n"
                    f"{('HOD\'s note: "' + comment + '"') if comment else ''}\n\n"
                    f"Please log in to the portal to approve or reject.\n\n"
                    f"Regards,\nDepartment Portal"
                )
        
        st.success(f"Status updated to {new_status}")
        st.rerun()
    except Exception as e:
        st.error(f"Error updating status: {e}")

# -----------------------------------------------------------------------------
# Dashboards
# -----------------------------------------------------------------------------
def student_dashboard():
    st.sidebar.title("🎓 Student Portal")
    st.sidebar.info(f"👤 {st.session_state['name']} (Section {st.session_state['section']})")
    if st.sidebar.button("Logout"): logout_user()

    tab1, tab2 = st.tabs(["📝 Apply Leave", "📜 History"])
    
    with tab1:
        st.header("New Leave Request")
        with st.form("leave_form"):
            l_type = st.selectbox("Type", ["Medical", "OD", "Casual"])
            reason = st.text_area("Reason")
            doc = st.file_uploader("Document", type=['pdf','jpg','png'])
            if st.form_submit_button("Submit"):
                url = upload_file_to_storage(doc, st.session_state['username']) if doc else None
                submit_leave_request(st.session_state['username'], st.session_state['name'], 
                                   st.session_state['section'], l_type, reason, url)

    with tab2:
        st.header("My Requests")
        res = supabase.table('leave_requests').select('*').eq('student_username', st.session_state['username']).order('date_requested', desc=True).execute()
        if res.data:
            st.dataframe(pd.DataFrame(res.data)[['date_requested','leave_type','status','staff_comment','hod_comment','principal_comment']])
        else:
            st.info("No requests found")

def staff_dashboard():
    st.sidebar.title("👨‍🏫 Staff Portal")
    st.sidebar.info(f"👤 {st.session_state['name']}")
    
    # Identify Section based on Username (Hardcoded logic for demo)
    # staff_a -> A, staff_b -> B
    username = st.session_state['username']
    my_section = 'A' if 'a' in username else 'B'
    if st.session_state.get('section'): my_section = st.session_state['section']
    
    st.sidebar.write(f"Managing: **Section {my_section}**")
    if st.sidebar.button("Logout"): logout_user()

    st.header(f"Section {my_section} - Pending Requests")
    
    res = supabase.table('leave_requests').select('*')\
        .eq('status', 'Pending Staff')\
        .eq('student_section', my_section)\
        .execute()
        
    for req in res.data:
        with st.expander(f"{req['student_name']} ({req['leave_type']})"):
            st.write(f"Reason: {req['reason']}")
            if req['file_url']: st.markdown(f"[View Doc]({req['file_url']})")
            
            comment = st.text_input("Comment", key=f"c_{req['id']}")
            c1, c2 = st.columns(2)
            if c1.button("✅ Forward to HOD", key=f"f_{req['id']}"):
                update_request_status(req['id'], "Pending HOD", comment, "staff")
            if c2.button("❌ Reject", key=f"r_{req['id']}", type="primary"):
                update_request_status(req['id'], "Rejected by Staff", comment, "staff")

def hod_dashboard():
    st.sidebar.title("🎓 HOD Portal")
    st.sidebar.info(f"👤 {st.session_state['name']}")
    if st.sidebar.button("Logout"): logout_user()

    st.header("Leave Approvals")
    # HOD sees requests pending HOD from ALL sections
    res = supabase.table('leave_requests').select('*').eq('status', 'Pending HOD').execute()
    
    if not res.data:
        st.info("No pending requests")
    
    for req in res.data:
        with st.expander(f"{req['student_name']} (Sec {req['student_section']})"):
            st.write(f"Reason: {req['reason']}")
            st.write(f"Staff Comment: {req.get('staff_comment')}")
            if req['file_url']: st.markdown(f"[View Doc]({req['file_url']})")

            comment = st.text_input("Comment", key=f"hc_{req['id']}")
            c1, c2, c3 = st.columns(3)
            # HOD can Approve directly OR Forward to Principal
            if c1.button("✅ Approve", key=f"ha_{req['id']}"):
                update_request_status(req['id'], "Approved", comment, "hod")
            if c2.button("⏩ Fwd to Principal", key=f"hp_{req['id']}"):
                update_request_status(req['id'], "Pending Principal", comment, "hod")
            if c3.button("❌ Reject", key=f"hr_{req['id']}", type="primary"):
                update_request_status(req['id'], "Rejected by HOD", comment, "hod")

def principal_dashboard():
    st.sidebar.title("🏛️ Principal Portal")
    st.sidebar.info(f"👤 {st.session_state['name']}")
    if st.sidebar.button("Logout"): logout_user()

    st.header("Principal Actions")
    res = supabase.table('leave_requests').select('*').eq('status', 'Pending Principal').execute()
    
    if not res.data:
        st.info("No requests pending your approval.")
        
    for req in res.data:
        with st.expander(f"{req['student_name']} (Sec {req['student_section']})"):
            st.warning(f"Forwarded by HOD. Comment: {req.get('hod_comment')}")
            st.write(f"Reason: {req['reason']}")
            if req['file_url']: st.markdown(f"[View Doc]({req['file_url']})")

            comment = st.text_input("Comment", key=f"pc_{req['id']}")
            c1, c2 = st.columns(2)
            if c1.button("✅ Grand Approval", key=f"pa_{req['id']}"):
                update_request_status(req['id'], "Approved", comment, "principal")
            if c2.button("❌ Reject", key=f"pr_{req['id']}", type="primary"):
                update_request_status(req['id'], "Rejected by Principal", comment, "principal")

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="College Portal", page_icon="🏫", layout="wide")
    load_custom_css()
    
    if not st.session_state['logged_in']:
        st.title("🏫 College Portal Login")
        with st.form("login"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Login"): login_user(u, p)
    else:
        role = st.session_state['user_role']
        if role == 'student': student_dashboard()
        elif role == 'staff': staff_dashboard()
        elif role == 'hod': hod_dashboard()
        elif role == 'principal': principal_dashboard()
        else: st.error("Invalid Role")

if __name__ == "__main__":
    main()
