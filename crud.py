import pandas as pd
from sqlalchemy import text
from db import engine


# =====================================================
# Get all support tickets
# =====================================================
def get_all_tickets():
    """
    Returns all support tickets.
    """

    query = """
        SELECT
            ticket_id,
            title,
            status,
            created_by,
            created_at
        FROM tickets
        ORDER BY created_at DESC
    """

    return pd.read_sql(query, engine)


# =====================================================
# Get one ticket
# =====================================================
def get_ticket(ticket_id):

    query = text("""
        SELECT *
        FROM tickets
        WHERE ticket_id = :ticket_id
    """)

    with engine.connect() as conn:
        result = conn.execute(
            query,
            {"ticket_id": ticket_id}
        )

        return result.fetchone()


# =====================================================
# Get messages for a ticket
# =====================================================
def get_ticket_messages(ticket_id):

    query = text("""
        SELECT
            message_id,
            message_text,
            author,
            created_at
        FROM ticket_messages
        WHERE ticket_id = :ticket_id
        ORDER BY created_at
    """)

    with engine.connect() as conn:

        result = conn.execute(
            query,
            {"ticket_id": ticket_id}
        )

        return result.fetchall()


# =====================================================
# Create a new ticket
# =====================================================
def create_ticket(title, created_by):

    query = text("""
        INSERT INTO tickets
        (
            title,
            status,
            created_by
        )

        VALUES
        (
            :title,
            'open',
            :created_by
        )
    """)

    with engine.begin() as conn:

        conn.execute(
            query,
            {
                "title": title,
                "created_by": created_by
            }
        )


# =====================================================
# Add a message
# =====================================================
def add_message(ticket_id, message_text, author):

    query = text("""
        INSERT INTO ticket_messages
        (
            ticket_id,
            message_text,
            author
        )

        VALUES
        (
            :ticket_id,
            :message_text,
            :author
        )
    """)

    with engine.begin() as conn:

        conn.execute(
            query,
            {
                "ticket_id": ticket_id,
                "message_text": message_text,
                "author": author
            }
        )


# =====================================================
# Update ticket status
# =====================================================
def update_ticket_status(ticket_id, status):

    query = text("""
        UPDATE tickets
        SET status = :status
        WHERE ticket_id = :ticket_id
    """)

    with engine.begin() as conn:

        conn.execute(
            query,
            {
                "ticket_id": ticket_id,
                "status": status
            }
        )


# =====================================================
# Delete a ticket (optional)
# =====================================================
def delete_ticket(ticket_id):

    query = text("""
        DELETE
        FROM tickets
        WHERE ticket_id = :ticket_id
    """)

    with engine.begin() as conn:

        conn.execute(
            query,
            {
                "ticket_id": ticket_id
            }
        )


# =====================================================
# Delete a message (optional)
# =====================================================
def delete_message(message_id):

    query = text("""
        DELETE
        FROM ticket_messages
        WHERE message_id = :message_id
    """)

    with engine.begin() as conn:

        conn.execute(
            query,
            {
                "message_id": message_id
            }
        )


# =====================================================
# Count tickets by status (optional dashboard)
# =====================================================
def get_ticket_summary():

    query = """
        SELECT
            status,
            COUNT(*) AS total
        FROM tickets
        GROUP BY status
        ORDER BY status
    """

    return pd.read_sql(query, engine)


# =====================================================
# Search tickets by title (optional)
# =====================================================
def search_tickets(keyword):

    query = text("""
        SELECT *
        FROM tickets
        WHERE LOWER(title)
        LIKE LOWER(:keyword)
        ORDER BY created_at DESC
    """)

    with engine.connect() as conn:

        result = conn.execute(
            query,
            {
                "keyword": f"%{keyword}%"
            }
        )

        return result.fetchall()
