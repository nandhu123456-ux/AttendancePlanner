sessions = {}


def save_session(
    student_id,
    session
):

    sessions[student_id] = session



def get_session(student_id):

    return sessions.get(student_id)



def remove_session(student_id):

    if student_id in sessions:

        del sessions[student_id]


def active_sessions():
    """Snapshot of authenticated in-memory portal sessions for scheduled refreshes."""
    return list(sessions.items())
