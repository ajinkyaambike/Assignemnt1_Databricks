import streamlit as st

from crud import (
    get_all_tickets,
    get_ticket_messages,
    create_ticket,
    add_message,
    update_status
)

st.title("🎫 Support Ticket System")

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

    update_status(
        selected_ticket,
        status
    )

    st.success("Status Updated")

    st.rerun()
