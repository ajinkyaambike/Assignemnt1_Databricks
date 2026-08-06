import streamlit as st

from crud import (
    get_all_tickets,
    get_ticket_messages,
    create_ticket,
    add_message,
    update_ticket_status
)

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Total Tickets",
    len(tickets)
)

col2.metric(
    "Open",
    len(tickets[tickets["status"]=="open"])
)

col3.metric(
    "In Progress",
    len(tickets[tickets["status"]=="in_progress"])
)

col4.metric(
    "Resolved",
    len(tickets[tickets["status"]=="resolved"])
)

st.title("🎫 Support Ticket System")

status_filter = st.selectbox(
    "Filter by Status",
    [
        "All",
        "Open",
        "In Progress",
        "Resolved"
    ]
)

#######################################################
# Display Tickets
#######################################################

tickets = get_all_tickets()

st.subheader("All Support Tickets")

st.dataframe(tickets)

#######################################################
# Select Ticket
#######################################################

ticket_ids = tickets["ticket_id"].tolist()

selected_ticket = st.selectbox(
    "Select Ticket",
    ticket_ids
)

priority = st.selectbox(
    "Priority",
    ["Low", "Medium", "High", "Critical"]
)

category = st.selectbox(
    "Category",
    [
        "Login",
        "Infrastructure",
        "Database",
        "Application",
        "Security",
        "Other"
    ]
)

#######################################################
# Display Messages
#######################################################

st.subheader("Messages")

messages = get_ticket_messages(selected_ticket)

for msg in messages:

    st.write(f"**{msg.author}**")

    st.write(msg.message_text)

    st.write(msg.created_at)

    st.divider()

#######################################################
# Create Ticket
#######################################################

st.subheader("Create New Ticket")

title = st.text_input("Title")

created_by = st.text_input("Created By")

if st.button("Create Ticket"):

    if title.strip() == "":
        st.error("Title cannot be empty.")

    elif created_by.strip() == "":
        st.error("Created By is required.")

    else:
        create_ticket(...)
        st.success("Ticket created successfully.")
        st.rerun()
        
if title and created_by:

        create_ticket(title, created_by)

        st.success("Ticket Created")

        st.rerun()

#######################################################
# Add Message
#######################################################

st.subheader("Add Message")

message = st.text_area("Message")

author = st.text_input("Author")

if st.button("Add Message"):

    if message and author:

        add_message(
            selected_ticket,
            message,
            author
        )

        st.success("Message Added")

        st.rerun()

#######################################################
# Update Status
#######################################################

st.subheader("Update Status")

status = st.selectbox(
    "Status",
    [
        "open",
        "in_progress",
        "resolved"
    ]
)

if st.button("Update Status"):

    update_ticket_status(
        selected_ticket,
        status
    )

    st.success("Status Updated")

    st.rerun()
